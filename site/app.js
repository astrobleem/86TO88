// One-click hosted runner. SPDX-License-Identifier: MIT
// Fetches public reference media in the visitor's browser, verifies every hash,
// builds the guest disk in memory, then hands it to PCjs via window.resources.
import { compose, specimenFromWin31, checked, sha256hex, PINS } from './compose.js';

const FOXLUM = 'https://raw.githubusercontent.com/Foxlum/pcjs-wiki/d2a82f69c9cbfe028020ff7d1cf3679638c5cf9d/disks/pcx86/fixed/20mb/';
const PCJS = 'https://raw.githubusercontent.com/jeffpar/pcjs/9e5409ab6ef706c6fc676ae1985978ad0eb0daee/machines/pcx86/';
const SRC = {
  win30: { url: FOXLUM + 'PCDOS320-WIN300-EGA.json', sha: PINS.windows30Json },
  win31: { url: FOXLUM + 'PCDOS330-WIN310-VGA.json', sha: PINS.windows31Json },
  romBios: { url: PCJS + 'ibm/5170/rom/bios/1985-11-15/ATBIOS-REV3.json5', sha: '7977701c277a8a02b7341b261c3d0fc4dc65306c1ad432be6aa539a073cae5ea', key: 'vendor/ATBIOS-REV3.json5' },
  romEga: { url: PCJS + 'ibm/video/ega/1984-09-13/IBM-EGA.json5', sha: '0eba1177dfbe939ccd1c05c44dbdc3fa34dfa2e5ce4de5fb9bf21bb50d47bd6f', key: 'vendor/IBM-EGA.json5' },
};
const OURS = ['WM88TSR.COM', 'SHELL.DLL', 'WM88.BAT', 'TEST88.COM', 'RTEST2.COM', 'CONFIG.SYS', 'AUTOEXEC.BAT'];

const $ = (id) => document.getElementById(id);
const stepEl = (s) => document.querySelector(`#steps li[data-s="${s}"]`);
function step(s, state, extra) {
  const li = stepEl(s); li.className = state;
  const base = li.dataset.base ?? (li.dataset.base = li.textContent);
  li.textContent = extra ? `${base} (${extra})` : base;
}
const mb = (n) => (n / 1048576).toFixed(1) + ' MB';

async function download(src, label, stepName) {
  step(stepName, 'active');
  const res = await fetch(src.url, { cache: 'force-cache' });
  if (!res.ok) throw new Error(`${label}: HTTP ${res.status} from ${new URL(src.url).host}`);
  const reader = res.body.getReader(); const chunks = []; let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); got += value.length; step(stepName, 'active', mb(got));
  }
  const out = new Uint8Array(got); let o = 0; for (const c of chunks) { out.set(c, o); o += c.length; }
  await checked(out, src.sha, label);
  step(stepName, 'done', mb(got) + ', hash OK');
  return out;
}

function fail(stepName, err) {
  if (stepName) step(stepName, 'fail');
  const box = $('fail');
  box.style.display = 'block';
  box.textContent = 'VALIDATION FAILED. Windows was NOT launched. ' + (err && err.message ? err.message : err);
  $('go').disabled = false; $('goown').disabled = false;
}

async function run(own) {
  $('go').disabled = true; $('goown').disabled = true; $('fail').style.display = 'none';
  document.querySelectorAll('#steps li').forEach((li) => (li.className = ''));
  let current = 'roms';
  try {
    const td = new TextDecoder();
    const resources = { parms: '{}' };
    for (const k of ['romBios', 'romEga']) { current = 'roms'; resources[SRC[k].key] = td.decode(await download(SRC[k], SRC[k].key, 'roms')); }
    step('roms', 'done', 'hash OK');

    let win30, specimen;
    if (own) {
      current = 'win30'; step('win30', 'active');
      win30 = new Uint8Array(await own.win30.arrayBuffer()); step('win30', 'done', 'your file');
      specimen = new Uint8Array(await own.mine.arrayBuffer()); step('win31', 'done', 'your WINMINE.EXE');
    } else {
      current = 'win30'; win30 = await download(SRC.win30, 'Windows 3.0 disk', 'win30');
      current = 'win31'; const win31 = await download(SRC.win31, 'Windows 3.1 disk', 'win31');
      current = 'build'; step('build', 'active');
      specimen = specimenFromWin31(td.decode(win31));
    }
    current = 'build'; step('build', 'active');
    const ours = {};
    for (const n of OURS) { const r = await fetch('ours/' + n); if (!r.ok) throw new Error('Missing site file ' + n); ours[n] = new Uint8Array(await r.arrayBuffer()); }
    await new Promise((r) => setTimeout(r, 30));  // let the UI paint before the CPU-heavy part
    const { diskText } = await compose(win30, specimen, ours);
    step('build', 'done', 'WINMINE.EXE hash OK');
    resources['disk.json'] = diskText;

    current = 'boot'; step('boot', 'active');
    window.resources = resources;
    $('emulator-wrap').hidden = false;
    await new Promise((res, rej) => {
      const s = document.createElement('script'); s.src = 'vendor/pcx86.js'; s.onload = res; s.onerror = () => rej(new Error('Could not load the PCjs runtime'));
      document.body.appendChild(s);
    });
    // PCjs initializes on window load; it has already fired, so re-fire it once.
    window.dispatchEvent(new Event('load'));
    step('boot', 'done', 'running');
    $('emulator-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) { fail(current, err); }
}

$('go').addEventListener('click', () => run(null));
$('goown').addEventListener('click', () => {
  const a = $('own30').files[0], b = $('ownmine').files[0];
  if (!a || !b) { fail(null, new Error('Choose both files.')); return; }
  run({ win30: a, mine: b });
});
window.__86to88 = { SRC, run };  // for the headless test
