"""Minimal PCjs v1 media codec and conservative FAT12/16 image editor.

SPDX-License-Identifier: MIT
Copyright (c) 2026 Chad Doebelin

Only in-memory byte buffers are edited. No OS media is downloaded here. Paths
are ASCII DOS 8.3 names; existing directories are required. Unsupported disk
layouts are rejected rather than guessed. This module is not a disk repair tool.
"""
import json
import re
import struct

MAX_BYTES = 64 * 1024 * 1024


def _number(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('Invalid ' + label)
    return value


def decode_pcjs(data):
    """Decode legacy cylinder/head/sector JSON into raw bytes and geometry."""
    disk = json.loads(data)
    if not isinstance(disk, list) or not disk or not isinstance(disk[0], list) or not disk[0]:
        raise ValueError('Expected nonempty PCjs cylinder array')
    if not isinstance(disk[0][0], list) or not disk[0][0]:
        raise ValueError('Empty PCjs track')
    c, h, s = len(disk), len(disk[0]), len(disk[0][0])
    if c * h * s * 512 > MAX_BYTES:
        raise ValueError('Disk exceeds size limit')
    result = bytearray()
    for cyl in disk:
        if not isinstance(cyl, list) or len(cyl) != h:
            raise ValueError('Inconsistent heads')
        for track in cyl:
            if not isinstance(track, list) or len(track) != s:
                raise ValueError('Inconsistent sectors')
            for i, sec in enumerate(track, 1):
                if not isinstance(sec, dict) or type(sec.get('sector')) is not int or sec['sector'] != i:
                    raise ValueError('Invalid sector ordering')
                if type(sec.get('length', 512)) is not int or sec.get('length', 512) != 512:
                    raise ValueError('Unsupported sector size')
                if 'data' in sec and 'bytes' in sec:
                    raise ValueError('Ambiguous sector encoding')
                dwords = 'data' in sec
                values = sec.get('data' if dwords else 'bytes', [])
                width, count = (4, 128) if dwords else (1, 512)
                if not isinstance(values, list) or len(values) > count:
                    raise ValueError('Invalid sector payload')
                low, high = (-2147483648, 4294967295) if dwords else (0, 255)
                fill = _number(sec.get('pattern', 0), low, high, 'fill')
                for val in values + [fill] * (count - len(values)):
                    val = _number(val, low, high, 'sector value')
                    result.extend((val & (2 ** (width * 8) - 1)).to_bytes(width, 'little'))
    return bytes(result), {'cylinders': c, 'heads': h, 'sectors_per_track': s}


def encode_pcjs(raw, geometry):
    """Encode 512-byte sectors deterministically, compressing repeated tails."""
    c = _number(geometry['cylinders'], 1, 65535, 'cylinders')
    h = _number(geometry['heads'], 1, 255, 'heads')
    s = _number(geometry['sectors_per_track'], 1, 255, 'sectors')
    if len(raw) != c * h * s * 512 or len(raw) > MAX_BYTES:
        raise ValueError('Geometry does not match raw image')
    disk, position = [], 0
    for _ in range(c):
        cylinder = []
        for _ in range(h):
            track = []
            for n in range(1, s + 1):
                words = list(struct.unpack_from('<128i', raw, position))
                position += 512
                fill = words[-1]
                while words and words[-1] == fill:
                    words.pop()
                track.append({'sector': n, 'length': 512, 'data': words, 'pattern': fill})
            cylinder.append(track)
        disk.append(cylinder)
    return (json.dumps(disk, separators=(',', ':')) + '\n').encode('ascii')


class FatDisk:
    """Single active MBR FAT12/16 partition, with strict whole-tree validation."""
    def __init__(self, raw):
        if len(raw) < 1024 or len(raw) > MAX_BYTES or len(raw) % 512 or raw[510:512] != b'\x55\xaa':
            raise ValueError('Invalid MBR image')
        self.raw = bytearray(raw)
        partitions = []
        extents = []
        for i in range(4):
            e = raw[446 + 16*i:462 + 16*i]
            if e[0] not in (0, 128):
                raise ValueError('Invalid partition status')
            pstart, pcount = struct.unpack_from('<II', e, 8)
            if e[4]:
                if not pstart or not pcount or pstart+pcount > len(raw)//512:
                    raise ValueError('Partition extent outside image')
                if any(pstart < end and begin < pstart+pcount for begin, end in extents):
                    raise ValueError('Overlapping partitions')
                extents.append((pstart, pstart+pcount))
            elif pstart or pcount or e[0]:
                raise ValueError('Inconsistent unused partition')
            if e[0] == 128:
                partitions.append((e[4], pstart, pcount))
        if len(partitions) != 1 or partitions[0][0] not in (1, 4, 6):
            raise ValueError('Expected one active FAT12/16 partition')
        ptype, start, sectors = partitions[0]
        if not start or not sectors or start + sectors > len(raw) // 512:
            raise ValueError('Partition outside image')
        self.base = start * 512
        b = self.base
        bps, spc, reserved, fats, roots, total16 = struct.unpack_from('<HBHBHH', raw, b+11)
        fat_sectors = struct.unpack_from('<H', raw, b+22)[0]
        total = total16 or struct.unpack_from('<I', raw, b+32)[0]
        if bps != 512 or spc not in (1, 2, 4, 8, 16, 32, 64, 128) or not reserved or fats not in (1, 2) or not roots or not fat_sectors:
            raise ValueError('Unsupported FAT BPB')
        if not total or total > sectors:
            raise ValueError('Invalid volume length')
        self.cluster_bytes = spc * 512
        self.fat_size = fat_sectors * 512
        self.fat_offsets = [b + (reserved + i*fat_sectors)*512 for i in range(fats)]
        self.root_offset = b + (reserved + fats*fat_sectors)*512
        self.root_size = roots*32
        self.data_offset = self.root_offset + ((self.root_size+511)//512)*512
        data_sectors = total - (self.data_offset-b)//512
        if data_sectors <= 0:
            raise ValueError('Empty data region')
        self.clusters = data_sectors // spc
        self.bits = 12 if self.clusters < 4085 else 16 if self.clusters < 65525 else 0
        if not self.bits or (ptype == 1) != (self.bits == 12):
            raise ValueError('Partition type disagrees with FAT')
        if (self.clusters+2)*self.bits > self.fat_size*8:
            raise ValueError('FAT too short')
        self.eoc = 0xff8 if self.bits == 12 else 0xfff8
        self.reserved_cluster = 0xff0 if self.bits == 12 else 0xfff0
        first = self.raw[self.fat_offsets[0]:self.fat_offsets[0]+self.fat_size]
        if any(self.raw[o:o+self.fat_size] != first for o in self.fat_offsets[1:]):
            raise ValueError('FAT copies disagree')
        self._index()

    def _fat(self, cluster):
        offset = cluster*2 if self.bits == 16 else cluster+cluster//2
        word = struct.unpack_from('<H', self.raw, self.fat_offsets[0]+offset)[0]
        return word if self.bits == 16 else (word >> 4 if cluster & 1 else word & 0xfff)

    def _set_fat(self, cluster, value):
        for f in self.fat_offsets:
            o = f + (cluster*2 if self.bits == 16 else cluster+cluster//2)
            if self.bits == 12:
                old = struct.unpack_from('<H', self.raw, o)[0]
                value_to_write = (old & 0xf) | (value << 4) if cluster & 1 else (old & 0xf000) | value
            else:
                value_to_write = value
            struct.pack_into('<H', self.raw, o, value_to_write)

    def _offset(self, cluster):
        return self.data_offset + (cluster-2)*self.cluster_bytes

    def _chain(self, start, name):
        chain, seen = [], set()
        if start == 0:
            return chain
        while start < self.eoc:
            if not 2 <= start < min(self.clusters+2, self.reserved_cluster) or start in seen or start in self.owners:
                raise ValueError('Invalid/cyclic/cross-linked chain: '+name)
            seen.add(start)
            self.owners[start] = name
            chain.append(start)
            start = self._fat(start)
        return chain

    @staticmethod
    def _path(path):
        if not isinstance(path, str):
            raise ValueError('Expected DOS path')
        parts = path.replace('\\', '/').upper().split('/')
        if not parts or any(not re.fullmatch(r"[A-Z0-9_$~!#%&'()@^`{}-]{1,8}(?:\.[A-Z0-9_$~!#%&'()@^`{}-]{1,3})?", p) for p in parts):
            raise ValueError('Expected relative ASCII 8.3 path')
        return '/'.join(parts)

    def _index(self):
        self.files, self.directories, self.owners = {}, {}, {}
        def visit(prefix, positions, depth):
            if depth > 32:
                raise ValueError('Directory nesting too deep')
            self.directories[prefix] = positions
            names = set()
            for o in positions:
                e = self.raw[o:o+32]
                if e[0] == 0:
                    break
                if e[0] == 0xe5:
                    continue
                attr = e[11]
                if attr == 15:
                    raise ValueError('Long file names unsupported')
                if attr & 8:
                    continue
                base = bytes(e[:8]).decode('ascii').rstrip()
                ext = bytes(e[8:11]).decode('ascii').rstrip()
                if base in ('.', '..'):
                    continue
                name = self._path(base + ('.'+ext if ext else ''))
                if name in names:
                    raise ValueError('Duplicate directory entry')
                names.add(name)
                path = prefix + ('/' if prefix else '') + name
                start, size = struct.unpack_from('<HI', e, 26)
                chain = self._chain(start, path)
                if attr & 16:
                    if not chain or size:
                        raise ValueError('Invalid directory')
                    positions2 = [a for c in chain for a in range(self._offset(c), self._offset(c)+self.cluster_bytes, 32)]
                    visit(path, positions2, depth+1)
                else:
                    if size > len(chain)*self.cluster_bytes or (chain and size <= (len(chain)-1)*self.cluster_bytes):
                        raise ValueError('File size disagrees with chain')
                    self.files[path] = (o, chain, size)
        visit('', list(range(self.root_offset, self.root_offset+self.root_size, 32)), 0)

    def list_files(self):
        return sorted(self.files)

    def read_file(self, path):
        _, chain, size = self.files[self._path(path)]
        return b''.join(bytes(self.raw[self._offset(c):self._offset(c)+self.cluster_bytes]) for c in chain)[:size]

    def write_file(self, path, data):
        """Add/replace file atomically in memory; never grow a directory."""
        path = self._path(path)
        data = bytes(data)
        parent, _, leaf = path.rpartition('/')
        if parent not in self.directories:
            raise ValueError('Parent directory does not exist: '+parent)
        if path in self.directories:
            raise ValueError('Cannot replace directory')
        previous = self.files.get(path)
        oldchain = previous[1] if previous else []
        if previous:
            slot = previous[0]
        else:
            slots = self.directories[parent]
            slot = next((o for o in slots if self.raw[o] in (0, 0xe5)), None)
            if slot is None:
                raise ValueError('Directory full')
        count = (len(data)+self.cluster_bytes-1)//self.cluster_bytes
        available = oldchain + [c for c in range(2, min(self.clusters+2, self.reserved_cluster)) if self._fat(c) == 0 and c not in self.owners]
        if len(available) < count:
            raise ValueError('Insufficient disk space')
        allocated = available[:count]
        snapshot = self.raw[:]
        try:
            for c in oldchain:
                self._set_fat(c, 0)
            for i, c in enumerate(allocated):
                self._set_fat(c, allocated[i+1] if i+1 < count else self.eoc)
                o = self._offset(c)
                chunk = data[i*self.cluster_bytes:(i+1)*self.cluster_bytes]
                self.raw[o:o+self.cluster_bytes] = chunk.ljust(self.cluster_bytes, b'\0')
            if not previous:
                was_end = self.raw[slot] == 0
                self.raw[slot:slot+32] = bytes(32)
                name, _, ext = leaf.partition('.')
                self.raw[slot:slot+11] = (name.ljust(8)+ext.ljust(3)).encode('ascii')
                self.raw[slot+11] = 32
                # Preserve the directory end marker when consuming a blank slot.
                positions = self.directories[parent]
                ix = positions.index(slot)
                if was_end and ix+1 < len(positions):
                    self.raw[positions[ix+1]] = 0
            struct.pack_into('<HI', self.raw, slot+26, allocated[0] if allocated else 0, len(data))
            self._index()
            if self.read_file(path) != data:
                raise ValueError('Write verification failed')
        except Exception:
            self.raw = snapshot
            self._index()
            raise

    def to_bytes(self):
        return bytes(self.raw)
