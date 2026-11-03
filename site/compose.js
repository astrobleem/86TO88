// Builds the guest disk in memory. Port of compose() in tools/prepare_pcjs.py.
// SPDX-License-Identifier: MIT
import { decodePcjs, encodePcjs, FatDisk } from './pcjs_media.js';

export const PINS = {
  windows30Json: 'ee96645f9e9bb629c2250f11c06b72c86b31f24b164c32efef28d89ffb90a4e2',
  windows31Json: 'abcf3297ae3adde213d96363448c88a709febc817692aa17a677d7b0d4fe0112',
  specimen: '633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b',
  specimenBytes: 27776,
  tsr: 'c04950d38ca03a209a898e16029260211e0b538c65ee3a99f3ac90e285c469f7',
  shim: '2d7532ae8ac73b957b5fb423449168c7b8f976b150155a42ac37d4b0139ddd1b',
};

export async function sha256hex(bytes) {
  const d = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function checked(bytes, digest, label) {
  if ((await sha256hex(bytes)) !== digest) throw new Error(`${label}: SHA-256 mismatch; refusing changed input`);
  return bytes;
}

const same = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);

// Extract WINMINE.EXE from the Windows 3.1 reference disk (text of the PCjs JSON).
export function specimenFromWin31(win31Text) {
  const { raw } = decodePcjs(win31Text);
  return new FatDisk(raw).readFile('WINDOWS/WINMINE.EXE');
}

// win30Bytes: raw bytes of the Windows 3.0 reference JSON (hash already checked by caller or here).
// ours: { name: Uint8Array } with WM88TSR.COM, SHELL.DLL, WM88.BAT, TEST88.COM, RTEST2.COM, CONFIG.SYS, AUTOEXEC.BAT
export async function compose(win30Bytes, specimen, ours, { check = true } = {}) {
  if (check) {
    await checked(win30Bytes, PINS.windows30Json, 'Windows 3.0 reference JSON');
    await checked(specimen, PINS.specimen, 'WINMINE.EXE');
    await checked(ours['WM88TSR.COM'], PINS.tsr, 'WM88TSR.COM');
    await checked(ours['SHELL.DLL'], PINS.shim, 'SHELL.DLL');
  }
  if (specimen.length !== PINS.specimenBytes) throw new Error('Unexpected WINMINE.EXE length');
  const text = new TextDecoder('utf-8').decode(win30Bytes);
  const { raw, geometry } = decodePcjs(text);
  if (geometry.cylinders !== 615 || geometry.heads !== 4 || geometry.sectors_per_track !== 17) throw new Error('Expected 615/4/17 reference disk geometry');
  const disk = new FatDisk(raw);
  const before = new Map();
  for (const n of disk.listFiles()) before.set(n, await sha256hex(disk.readFile(n)));
  const changes = {
    'WINDOWS/WM88TSR.COM': ours['WM88TSR.COM'],
    'WINDOWS/SYSTEM/SHELL.DLL': ours['SHELL.DLL'],
    'WINDOWS/WINMINE.EXE': specimen,
    'WINDOWS/WM88.BAT': ours['WM88.BAT'],
    'WINDOWS/TEST88.COM': ours['TEST88.COM'],
    'WINDOWS/RTEST2.COM': ours['RTEST2.COM'],
    'CONFIG.SYS': ours['CONFIG.SYS'],
    'AUTOEXEC.BAT': ours['AUTOEXEC.BAT'],
  };
  for (const [name, data] of Object.entries(changes)) disk.writeFile(name, data);
  const result = disk.toBytes();
  const reread = new FatDisk(result);
  for (const [name, data] of Object.entries(changes)) if (!same(reread.readFile(name), data)) throw new Error('Written file verification failed: ' + name);
  for (const [name, digest] of before) {
    if (name in changes) continue;
    if ((await sha256hex(reread.readFile(name))) !== digest) throw new Error('An unrelated guest file changed');
  }
  return { diskText: encodePcjs(result, geometry), changed: Object.keys(changes), unchanged: before.size - Object.keys(changes).filter((n) => before.has(n)).length };
}
