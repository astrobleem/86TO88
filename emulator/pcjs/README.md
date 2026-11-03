# PCjs judge fixture (local / self-hosted)

This prepares the **original Windows 3.1 Minesweeper binary under Windows 3.0
real mode**, using PCjs' **80286** core. It is a 286 compatibility/gameplay
fixture, **not an 8088 proof**. Nothing is hosted for you, and no Microsoft
media is committed to this repository.

## Quick start

Requirements: Python **3.9+**, a current desktop browser, and internet access
during preparation. No npm install, VM application, or compiler is required.

From the repository root:

```sh
python3 tools/prepare_pcjs.py --reference-media --out ../86to88-private-judge
```

On Windows, use `py -3` instead of `python3` if necessary. The output directory
must be new and outside the repository. The script never edits the inputs or
makes backup copies.

**Recommended, verified launch: serve the generated folder on loopback.**
Leave this command running in a terminal:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory ../86to88-private-judge
```

Then open **<http://127.0.0.1:8080/judge.html>** in a normal desktop browser.
On Windows, `py -3 -m http.server ...` or `python -m http.server ...` works
with the same arguments. This route was tested in Chrome on Windows. Judges
do not need a browser-control extension, GitHub sign-in, file-access permission,
fullscreen, or changed browser security settings. Keep `--bind 127.0.0.1`:
do not expose DOS/Windows media on a network or publish the generated folder.
Stop the local server with Ctrl+C when finished.

`judge.html` embeds its emulator, ROMs and guest disk, so the emulated machine
makes no disk/ROM requests after the page loads. The separate-assets page at
<http://127.0.0.1:8080/> was also tested. Keep the generated directory private.

Directly opening `../86to88-private-judge/judge.html` as a `file://` URL is an
**optional, unverified alternative**, not the required judge route. Browser
local-file policies vary. If it fails, use the loopback route above; do not
disable browser restrictions. Full screen is optional and did not activate
through the tested automation path; playing within the page works.

`PREPARED.json` in the generated directory records the input/output hashes.
Its page link is optional: browser-client blocking of that navigation does
not prevent the game from running. The file can be inspected locally as text.

The guest boots DOS, loads `WM88TSR.COM`, runs `TEST88.COM` and `RTEST2.COM`,
then invokes `WIN /R WINMINE.EXE`. Expected DOS success markers are `T88PASS`
and `0123456789ABCDERT2PASS` (15 read-test cases); their absence is not a pass. Click inside the emulated screen
to focus it. Left-click reveals, right-click flags, and F2 restarts a game.
If the TSR or a test exits with an error, startup stops at a visible
`VALIDATION FAILED` message instead of hiding the failure by opening Windows.

**Display/timing:** the original dark-red digit artwork is dithered by the
stock EGA driver, not corrupted. Exact bitmap matching verified the counter
010→009 on a flag and timer progression/reset. The default 1× speed produced
five timer increments over 4.995 host seconds; changing Speed also changes
emulated time. Chrome browser boot, reveal, flag/question cycling and F2 reset
were exercised on Windows. The guest uses a relative mouse: steer its visible
arrow to the cell before clicking. Full screen returned `TypeError: not granted`
through browser automation; the in-page display remained usable. See the
validation record for limits, including untested complete winning sessions.

## Your own media instead

```sh
python3 tools/prepare_pcjs.py \
  --disk-json /path/to/PCDOS320-WIN300-EGA.json \
  --winmine /path/to/WINMINE.EXE \
  --out ../86to88-private-judge
```

The Windows 3.0 disk must be the pinned reference below; arbitrary installed
disk layouts are intentionally refused rather than silently modified. The
specimen must be 27,776 bytes, SHA-256
`633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b`.
The runtime/ROM download is still required. `--win31-json` optionally supplies
an offline pinned 3.1 reference JSON when using `--reference-media`.

## Provenance and redistribution

`--reference-media` explicitly downloads archival reference images from the
public [Foxlum PCjs archive](https://github.com/Foxlum/pcjs-wiki/tree/d2a82f69c9cbfe028020ff7d1cf3679638c5cf9d/disks/pcx86/fixed/20mb).
It extracts only the matching WINMINE specimen from the 3.1 image; the 3.0
disk remains the actual DOS/Windows system executed by the fixture. These are
the same pinned sources documented by the earlier Windows XT project.

| Input | SHA-256 |
| --- | --- |
| `PCDOS320-WIN300-EGA.json` | `ee96645f9e9bb629c2250f11c06b72c86b31f24b164c32efef28d89ffb90a4e2` |
| `PCDOS330-WIN310-VGA.json` | `abcf3297ae3adde213d96363448c88a709febc817692aa17a677d7b0d4fe0112` |

Runtime assets are pinned to PCjs commit
`9e5409ab6ef706c6fc676ae1985978ad0eb0daee`, with per-file hashes in
[`assets.json`](assets.json). **PCjs software's MIT license does not cover
third-party DOS/Windows disks or ROMs. Public availability is not a grant of
redistribution rights.** Only use media you are entitled to use. Generated
media is local/private, excluded from the public repository, and should not be
uploaded to GitHub, Pages, or another public host. A public setup script is not
a license for the media it references.

## Reproducibility and scope

* The builder checks every source/download hash, the exact specimen, matching
  FAT copies and chains, and disk geometry (615 cylinders × 4 heads × 17 sectors).
* It adds the current bridge, shim, launcher, specimen and DOS test programs.
  Only the private output's `AUTOEXEC.BAT` and `CONFIG.SYS` are replaced.
  Windows executables and display drivers are unchanged.
* It verifies the output files, preserves every other original file's hash,
  and round-trips the PCjs sector encoding. `PREPARED.json` records hashes and
  explicitly says host preparation is **not** guest execution.
* The AT profile uses CPU model 80286 at 8 MHz, 640 KiB conventional RAM,
  EGA 128 KiB, no extended RAM, a serial mouse, and `WIN /R`. CPU model and
  Windows operating mode are distinct. This does not reproduce Tandy hardware.
* The default CPU speed multiplier is 1× for normal timer pace, not an
  accelerated boot/game. This is still not a physical-hardware timing benchmark.
* Browser XSLT is not used. `machine.html` was pre-rendered from `machine.xml`
  using the pinned PCjs `machines/pcx86/xsl/components.xsl`; the runtime directly
  initializes the resulting component markup. The PCjs license is retained.
* Session writes stay in emulator memory. Reset reboots that memory; reload
  starts from the original prepared disk. Automatic resume is disabled.

The project's earlier 8088 PCjs startup hang remains a separate historical
result, not a universal claim about current PCjs. Do not report this 286
fixture as confirming or refuting the physical Tandy 1000 EX result.

## Validation

```sh
python3 -m unittest discover -s tools -p 'test_pcjs*.py' -v
python3 src/build_tsr.py
python3 src/build_shell.py
```

See [`VALIDATION.md`](VALIDATION.md) for what was actually exercised, including
environment-specific browser-test blockers. Do not infer successful gameplay
from a generated disk or passing host tests alone.
