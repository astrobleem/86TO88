// Minimal PCjs v1 media codec and conservative FAT12/16 image editor.
// JavaScript port of tools/pcjs_media.py. SPDX-License-Identifier: MIT
// Copyright (c) 2026 Chad Doebelin
//
// Only in-memory byte buffers are edited. Unsupported disk layouts are
// rejected rather than guessed. Behavior is kept identical to the Python
// original; site/test/parity.mjs proves byte-identical output.

export const MAX_BYTES = 64 * 1024 * 1024;

function number(value, lo, hi, label) {
  if (!Number.isInteger(value) || value < lo || value > hi) throw new Error('Invalid ' + label);
  return value;
}

export function decodePcjs(text) {
  const disk = JSON.parse(text);
  if (!Array.isArray(disk) || !disk.length || !Array.isArray(disk[0]) || !disk[0].length) throw new Error('Expected nonempty PCjs cylinder array');
  if (!Array.isArray(disk[0][0]) || !disk[0][0].length) throw new Error('Empty PCjs track');
  const c = disk.length, h = disk[0].length, s = disk[0][0].length;
  if (c * h * s * 512 > MAX_BYTES) throw new Error('Disk exceeds size limit');
  const raw = new Uint8Array(c * h * s * 512);
  const dv = new DataView(raw.buffer);
  let pos = 0;
  for (const cyl of disk) {
    if (!Array.isArray(cyl) || cyl.length !== h) throw new Error('Inconsistent heads');
    for (const track of cyl) {
      if (!Array.isArray(track) || track.length !== s) throw new Error('Inconsistent sectors');
      track.forEach((sec, i) => {
        if (sec === null || typeof sec !== 'object' || Array.isArray(sec) || !Number.isInteger(sec.sector) || sec.sector !== i + 1) throw new Error('Invalid sector ordering');
        const length = 'length' in sec ? sec.length : 512;
        if (!Number.isInteger(length) || length !== 512) throw new Error('Unsupported sector size');
        if ('data' in sec && 'bytes' in sec) throw new Error('Ambiguous sector encoding');
        const dwords = 'data' in sec;
        const values = sec[dwords ? 'data' : 'bytes'] ?? [];
        const [width, count] = dwords ? [4, 128] : [1, 512];
        if (!Array.isArray(values) || values.length > count) throw new Error('Invalid sector payload');
        const [lo, hi] = dwords ? [-2147483648, 4294967295] : [0, 255];
        const fill = number('pattern' in sec ? sec.pattern : 0, lo, hi, 'fill');
        for (let k = 0; k < count; k++) {
          const val = k < values.length ? number(values[k], lo, hi, 'sector value') : fill;
          if (width === 4) dv.setUint32(pos + k * 4, val >>> 0, true); else raw[pos + k] = val & 0xff;
        }
        pos += 512;
      });
    }
  }
  return { raw, geometry: { cylinders: c, heads: h, sectors_per_track: s } };
}

export function encodePcjs(raw, geometry) {
  const c = number(geometry.cylinders, 1, 65535, 'cylinders');
  const h = number(geometry.heads, 1, 255, 'heads');
  const s = number(geometry.sectors_per_track, 1, 255, 'sectors');
  if (raw.length !== c * h * s * 512 || raw.length > MAX_BYTES) throw new Error('Geometry does not match raw image');
  const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
  const disk = [];
  let pos = 0;
  for (let i = 0; i < c; i++) {
    const cylinder = [];
    for (let j = 0; j < h; j++) {
      const track = [];
      for (let n = 1; n <= s; n++) {
        const words = new Array(128);
        for (let k = 0; k < 128; k++) words[k] = dv.getInt32(pos + k * 4, true);
        pos += 512;
        const fill = words[127];
        while (words.length && words[words.length - 1] === fill) words.pop();
        track.push({ sector: n, length: 512, data: words, pattern: fill });
      }
      cylinder.push(track);
    }
    disk.push(cylinder);
  }
  return JSON.stringify(disk) + '\n';
}

const NAME_RE = /^[A-Z0-9_$~!#%&'()@^`{}-]{1,8}(?:\.[A-Z0-9_$~!#%&'()@^`{}-]{1,3})?$/;
const u16 = (a, o) => a[o] | (a[o + 1] << 8);
const u32 = (a, o) => (a[o] | (a[o + 1] << 8) | (a[o + 2] << 16) | (a[o + 3] << 24)) >>> 0;
const same = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const ascii = (a) => String.fromCharCode(...a);

export class FatDisk {
  constructor(rawIn) {
    const raw = rawIn;
    if (raw.length < 1024 || raw.length > MAX_BYTES || raw.length % 512 || raw[510] !== 0x55 || raw[511] !== 0xaa) throw new Error('Invalid MBR image');
    this.raw = new Uint8Array(raw);
    const partitions = [], extents = [];
    for (let i = 0; i < 4; i++) {
      const e = raw.subarray(446 + 16 * i, 462 + 16 * i);
      if (e[0] !== 0 && e[0] !== 128) throw new Error('Invalid partition status');
      const pstart = u32(e, 8), pcount = u32(e, 12);
      if (e[4]) {
        if (!pstart || !pcount || pstart + pcount > raw.length / 512) throw new Error('Partition extent outside image');
        if (extents.some(([b, en]) => pstart < en && b < pstart + pcount)) throw new Error('Overlapping partitions');
        extents.push([pstart, pstart + pcount]);
      } else if (pstart || pcount || e[0]) throw new Error('Inconsistent unused partition');
      if (e[0] === 128) partitions.push([e[4], pstart, pcount]);
    }
    if (partitions.length !== 1 || ![1, 4, 6].includes(partitions[0][0])) throw new Error('Expected one active FAT12/16 partition');
    const [ptype, start, sectors] = partitions[0];
    if (!start || !sectors || start + sectors > raw.length / 512) throw new Error('Partition outside image');
    this.base = start * 512;
    const b = this.base;
    const bps = u16(raw, b + 11), spc = raw[b + 13], reserved = u16(raw, b + 14), fats = raw[b + 16], roots = u16(raw, b + 17), total16 = u16(raw, b + 19);
    const fatSectors = u16(raw, b + 22);
    const total = total16 || u32(raw, b + 32);
    if (bps !== 512 || ![1, 2, 4, 8, 16, 32, 64, 128].includes(spc) || !reserved || ![1, 2].includes(fats) || !roots || !fatSectors) throw new Error('Unsupported FAT BPB');
    if (!total || total > sectors) throw new Error('Invalid volume length');
    this.clusterBytes = spc * 512;
    this.fatSize = fatSectors * 512;
    this.fatOffsets = Array.from({ length: fats }, (_, i) => b + (reserved + i * fatSectors) * 512);
    this.rootOffset = b + (reserved + fats * fatSectors) * 512;
    this.rootSize = roots * 32;
    this.dataOffset = this.rootOffset + Math.floor((this.rootSize + 511) / 512) * 512;
    const dataSectors = total - (this.dataOffset - b) / 512;
    if (dataSectors <= 0) throw new Error('Empty data region');
    this.clusters = Math.floor(dataSectors / spc);
    this.bits = this.clusters < 4085 ? 12 : this.clusters < 65525 ? 16 : 0;
    if (!this.bits || (ptype === 1) !== (this.bits === 12)) throw new Error('Partition type disagrees with FAT');
    if ((this.clusters + 2) * this.bits > this.fatSize * 8) throw new Error('FAT too short');
    this.eoc = this.bits === 12 ? 0xff8 : 0xfff8;
    this.reservedCluster = this.bits === 12 ? 0xff0 : 0xfff0;
    const first = this.raw.subarray(this.fatOffsets[0], this.fatOffsets[0] + this.fatSize);
    for (const o of this.fatOffsets.slice(1)) if (!same(this.raw.subarray(o, o + this.fatSize), first)) throw new Error('FAT copies disagree');
    this._index();
  }
  _fat(cluster) {
    const offset = this.bits === 16 ? cluster * 2 : cluster + (cluster >> 1);
    const word = u16(this.raw, this.fatOffsets[0] + offset);
    return this.bits === 16 ? word : (cluster & 1 ? word >> 4 : word & 0xfff);
  }
  _setFat(cluster, value) {
    for (const f of this.fatOffsets) {
      const o = f + (this.bits === 16 ? cluster * 2 : cluster + (cluster >> 1));
      let w;
      if (this.bits === 12) {
        const old = u16(this.raw, o);
        w = cluster & 1 ? (old & 0xf) | (value << 4) : (old & 0xf000) | value;
      } else w = value;
      this.raw[o] = w & 0xff; this.raw[o + 1] = (w >> 8) & 0xff;
    }
  }
  _offset(cluster) { return this.dataOffset + (cluster - 2) * this.clusterBytes; }
  _chain(start, name) {
    const chain = [], seen = new Set();
    if (start === 0) return chain;
    while (start < this.eoc) {
      if (!(start >= 2 && start < Math.min(this.clusters + 2, this.reservedCluster)) || seen.has(start) || this.owners.has(start)) throw new Error('Invalid/cyclic/cross-linked chain: ' + name);
      seen.add(start); this.owners.set(start, name); chain.push(start);
      start = this._fat(start);
    }
    return chain;
  }
  static _path(path) {
    if (typeof path !== 'string') throw new Error('Expected DOS path');
    const parts = path.replace(/\\/g, '/').toUpperCase().split('/');
    if (!parts.length || parts.some((p) => !NAME_RE.test(p))) throw new Error('Expected relative ASCII 8.3 path');
    return parts.join('/');
  }
  _index() {
    this.files = new Map(); this.directories = new Map(); this.owners = new Map();
    const visit = (prefix, positions, depth) => {
      if (depth > 32) throw new Error('Directory nesting too deep');
      this.directories.set(prefix, positions);
      const names = new Set();
      for (const o of positions) {
        const e = this.raw.subarray(o, o + 32);
        if (e[0] === 0) break;
        if (e[0] === 0xe5) continue;
        const attr = e[11];
        if (attr === 15) throw new Error('Long file names unsupported');
        if (attr & 8) continue;
        const base = ascii(e.subarray(0, 8)).replace(/\s+$/, '');
        const ext = ascii(e.subarray(8, 11)).replace(/\s+$/, '');
        if (base === '.' || base === '..') continue;
        const name = FatDisk._path(base + (ext ? '.' + ext : ''));
        if (names.has(name)) throw new Error('Duplicate directory entry');
        names.add(name);
        const path = prefix + (prefix ? '/' : '') + name;
        const start = u16(e, 26), size = u32(e, 28);
        const chain = this._chain(start, path);
        if (attr & 16) {
          if (!chain.length || size) throw new Error('Invalid directory');
          const positions2 = [];
          for (const c of chain) for (let a = this._offset(c); a < this._offset(c) + this.clusterBytes; a += 32) positions2.push(a);
          visit(path, positions2, depth + 1);
        } else {
          if (size > chain.length * this.clusterBytes || (chain.length && size <= (chain.length - 1) * this.clusterBytes)) throw new Error('File size disagrees with chain');
          this.files.set(path, [o, chain, size]);
        }
      }
    };
    const rootPositions = [];
    for (let o = this.rootOffset; o < this.rootOffset + this.rootSize; o += 32) rootPositions.push(o);
    visit('', rootPositions, 0);
  }
  listFiles() { return [...this.files.keys()].sort(); }
  readFile(path) {
    const [, chain, size] = this.files.get(FatDisk._path(path)) ?? (() => { throw new Error('No such file: ' + path); })();
    const out = new Uint8Array(chain.length * this.clusterBytes);
    chain.forEach((c, i) => out.set(this.raw.subarray(this._offset(c), this._offset(c) + this.clusterBytes), i * this.clusterBytes));
    return out.slice(0, size);
  }
  writeFile(pathIn, dataIn) {
    const path = FatDisk._path(pathIn);
    const data = new Uint8Array(dataIn);
    const i = path.lastIndexOf('/');
    const parent = i < 0 ? '' : path.slice(0, i), leaf = i < 0 ? path : path.slice(i + 1);
    if (!this.directories.has(parent)) throw new Error('Parent directory does not exist: ' + parent);
    if (this.directories.has(path)) throw new Error('Cannot replace directory');
    const previous = this.files.get(path);
    const oldchain = previous ? previous[1] : [];
    let slot;
    if (previous) slot = previous[0];
    else {
      slot = this.directories.get(parent).find((o) => this.raw[o] === 0 || this.raw[o] === 0xe5);
      if (slot === undefined) throw new Error('Directory full');
    }
    const count = Math.ceil(data.length / this.clusterBytes);
    const available = oldchain.slice();
    for (let c = 2; c < Math.min(this.clusters + 2, this.reservedCluster) && available.length < count; c++) {
      if (this._fat(c) === 0 && !this.owners.has(c)) available.push(c);
    }
    if (available.length < count) throw new Error('Insufficient disk space');
    const allocated = available.slice(0, count);
    const snapshot = this.raw.slice();
    try {
      for (const c of oldchain) this._setFat(c, 0);
      allocated.forEach((c, k) => {
        this._setFat(c, k + 1 < count ? allocated[k + 1] : this.eoc);
        const o = this._offset(c);
        const chunk = data.subarray(k * this.clusterBytes, (k + 1) * this.clusterBytes);
        this.raw.fill(0, o, o + this.clusterBytes);
        this.raw.set(chunk, o);
      });
      if (!previous) {
        const wasEnd = this.raw[slot] === 0;
        this.raw.fill(0, slot, slot + 32);
        const dot = leaf.indexOf('.');
        const name = dot < 0 ? leaf : leaf.slice(0, dot), ext = dot < 0 ? '' : leaf.slice(dot + 1);
        const field = name.padEnd(8, ' ') + ext.padEnd(3, ' ');
        for (let k = 0; k < 11; k++) this.raw[slot + k] = field.charCodeAt(k);
        this.raw[slot + 11] = 32;
        const positions = this.directories.get(parent);
        const ix = positions.indexOf(slot);
        if (wasEnd && ix + 1 < positions.length) this.raw[positions[ix + 1]] = 0;
      }
      const first = allocated.length ? allocated[0] : 0;
      this.raw[slot + 26] = first & 0xff; this.raw[slot + 27] = (first >> 8) & 0xff;
      this.raw[slot + 28] = data.length & 0xff; this.raw[slot + 29] = (data.length >>> 8) & 0xff;
      this.raw[slot + 30] = (data.length >>> 16) & 0xff; this.raw[slot + 31] = (data.length >>> 24) & 0xff;
      this._index();
      if (!same(this.readFile(path), data)) throw new Error('Write verification failed');
    } catch (err) {
      this.raw = snapshot; this._index();
      throw err;
    }
  }
  toBytes() { return this.raw.slice(); }
}
