"""Specimen-free codec/editor tests. Run: python3 -m unittest discover -s tools -p test_pcjs_media.py"""
import json
import struct
import unittest
from pcjs_media import FatDisk, decode_pcjs, encode_pcjs


def fixture(bits=16):
    sectors = 5000 if bits == 16 else 300
    fatsz = 20 if bits == 16 else 1
    raw = bytearray((sectors+1)*512)
    raw[510:512] = b'\x55\xaa'
    raw[446], raw[450] = 128, 4 if bits == 16 else 1
    struct.pack_into('<II', raw, 454, 1, sectors)
    struct.pack_into('<HBHBHH', raw, 523, 512, 1, 1, 2, 32, sectors)
    struct.pack_into('<H', raw, 534, fatsz)
    for i in range(2):
        off = 1024+i*fatsz*512
        if bits == 16:
            raw[off:off+8] = b'\xf8\xff\xff\xff\xff\xff\xff\xff'
        else:
            raw[off:off+6] = b'\xf8\xff\xff\xff\xff\xff'
    root = 1024+2*fatsz*512
    raw[root:root+11] = b'WINDOWS    '
    raw[root+11] = 16
    struct.pack_into('<H', raw, root+26, 2)
    data = root+1024
    raw[data:data+11] = b'SYSTEM     '
    raw[data+11] = 16
    struct.pack_into('<H', raw, data+26, 3)
    return bytes(raw)


class MediaTests(unittest.TestCase):
    def test_codec_roundtrip(self):
        raw = bytes(range(256))*4 + bytes(512) + b'\xff'*512
        g = dict(cylinders=1, heads=2, sectors_per_track=2)
        encoded = encode_pcjs(raw, g)
        self.assertEqual(decode_pcjs(encoded), (raw, g))
        self.assertEqual(encode_pcjs(raw, g), encoded)

    def test_byte_encoding_and_fill(self):
        source = [[ [{'sector': 1, 'bytes': [1, 2], 'pattern': 7}] ]]
        raw, _ = decode_pcjs(json.dumps(source))
        self.assertEqual(raw, b'\x01\x02'+b'\x07'*510)

    def test_reject_codec(self):
        for sec in ({'sector': 2}, {'sector': 1, 'length': 128}, {'sector': 1, 'bytes': [256]}, {'sector': 1, 'bytes': [], 'data': []}, {'sector': 1, 'data': [True]}):
            with self.assertRaises(ValueError):
                decode_pcjs(json.dumps([[[sec]]]))
        with self.assertRaises(ValueError):
            encode_pcjs(bytes(512), dict(cylinders=2, heads=1, sectors_per_track=1))

    def test_edits_both_fats_and_preserves_files(self):
        for bits in (12, 16):
            with self.subTest(bits=bits):
                original = fixture(bits)
                disk = FatDisk(original)
                disk.write_file('WINDOWS/KEEP.TXT', b'unchanged')
                disk.write_file('WINDOWS/WINMINE.EXE', b'game'*1000)
                disk.write_file('WINDOWS/SYSTEM/SHELL.DLL', b'shim')
                disk.write_file('AUTOEXEC.BAT', b'boot')
                before = disk.to_bytes()
                disk.write_file('WINDOWS/WINMINE.EXE', b'replacement')
                reread = FatDisk(disk.to_bytes())
                self.assertEqual(reread.read_file('WINDOWS/KEEP.TXT'), b'unchanged')
                self.assertEqual(reread.read_file('WINDOWS/WINMINE.EXE'), b'replacement')
                self.assertEqual(reread.read_file('WINDOWS/SYSTEM/SHELL.DLL'), b'shim')
                self.assertEqual(reread.read_file('AUTOEXEC.BAT'), b'boot')
                self.assertEqual(disk.to_bytes()[:1024], original[:1024])
                disk.write_file('AUTOEXEC.BAT', b'')
                self.assertEqual(FatDisk(disk.to_bytes()).read_file('AUTOEXEC.BAT'), b'')
                self.assertNotEqual(before, disk.to_bytes())

    def test_invalid_path_and_missing_parent_are_atomic(self):
        disk = FatDisk(fixture())
        original = disk.to_bytes()
        for path in ('../X', '/X', 'WINDOWS/TOOLONGNAME.EXE', 'MISSING/X', 'WINDOWS'):
            with self.assertRaises(ValueError):
                disk.write_file(path, b'no')
            self.assertEqual(disk.to_bytes(), original)
        with self.assertRaises(ValueError):
            disk.write_file('LARGE.BIN', bytes(4_000_000))
        self.assertEqual(disk.to_bytes(), original)

    def test_full_directory_fails_without_mutation(self):
        disk = FatDisk(fixture())
        # One 512-byte SYSTEM directory cluster contains 16 short entries.
        for n in range(16):
            disk.write_file('WINDOWS/SYSTEM/F%d.TXT' % n, b'')
        before = disk.to_bytes()
        with self.assertRaisesRegex(ValueError, 'Directory full'):
            disk.write_file('WINDOWS/SYSTEM/EXTRA.TXT', b'')
        self.assertEqual(before, disk.to_bytes())
        disk.write_file('WINDOWS/SYSTEM/F0.TXT', b'replace even when full')
        self.assertEqual(disk.read_file('WINDOWS/SYSTEM/F0.TXT'), b'replace even when full')

    def test_overlap_partition_rejected(self):
        raw = bytearray(fixture())
        raw[466] = 4
        struct.pack_into('<II', raw, 470, 2, 100)
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            FatDisk(raw)

    def test_fat_corruption(self):
        raw = bytearray(fixture())
        raw[1024+20*512+8] = 1
        with self.assertRaisesRegex(ValueError, 'copies'):
            FatDisk(raw)
        raw = bytearray(fixture())
        for off in (1024, 1024+20*512):
            struct.pack_into('<H', raw, off+4, 2)
        with self.assertRaisesRegex(ValueError, 'chain'):
            FatDisk(raw)


if __name__ == '__main__':
    unittest.main()
