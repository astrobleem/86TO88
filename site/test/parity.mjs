// Parity test: the JS composer must produce a disk byte-identical to the Python builder.
// Usage: node site/test/parity.mjs <win30.json> <win31.json> <python-built disk.json>
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { compose, specimenFromWin31, sha256hex } from '../compose.js';

const [w30, w31, expected] = process.argv.slice(2);
const load = (p) => { const b = readFileSync(p); return b[0] === 0x1f && b[1] === 0x8b ? gunzipSync(b) : b; };
const ours = {};
for (const n of ['WM88TSR.COM', 'SHELL.DLL', 'WM88.BAT', 'TEST88.COM', 'RTEST2.COM', 'CONFIG.SYS', 'AUTOEXEC.BAT']) ours[n] = new Uint8Array(readFileSync(new URL('../ours/' + n, import.meta.url)));
const win30 = new Uint8Array(load(w30));
const t0 = Date.now();
const win31Text = new TextDecoder().decode(load(w31));
const specimen = specimenFromWin31(win31Text);
console.log('specimen', specimen.length, await sha256hex(specimen));
const { diskText, changed } = await compose(win30, specimen, ours);
console.log('composed in', Date.now() - t0, 'ms; changed/added:', changed.length);
const got = createHash('sha256').update(diskText).digest('hex');
const want = createHash('sha256').update(readFileSync(expected)).digest('hex');
console.log('js    ', got);
console.log('python', want);
if (got !== want) { console.error('PARITY FAILED'); process.exit(1); }
console.log('PARITY OK (byte-identical)');
