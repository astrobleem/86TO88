# Optional headless verification (not browser QA)

These original MIT tools use the **official PCjs source core**, pinned to commit
`9e5409ab6ef706c6fc676ae1985978ad0eb0daee`, without browser or network sockets.
They are an independent diagnostic path, **not** proof that the browser UI
works. The browser uses a committed compiled bundle; source-core execution is not
proof of behavioral identity with that bundle. They use 80286 / 640 KiB / EGA / AT type-2 disk, not an 8088.

Prerequisites: Node.js (tested v24.22.1), Python 3; Pillow only for PNG rendering.
Prepare the private fixture using the parent PCjs guide first. From repo root:

```sh
python3 emulator/pcjs/verification/fetch_runtime.py ../pcjs-runtime
node emulator/pcjs/verification/headless.mjs ../pcjs-runtime ../private-fixture ../pcjs-evidence gameplay > ../pcjs-gameplay.log 2>&1
node emulator/pcjs/verification/headless.mjs ../pcjs-runtime ../private-fixture ../pcjs-evidence control > ../pcjs-control.log 2>&1
python3 emulator/pcjs/verification/render_vram.py ../pcjs-evidence/*-ega.json
```

For rendering, pass only `*-initial.json`, `*-position.json`, `*-reveal.json`,
`*-flag-timer.json`, and `*-ega.json` snapshots, **not** `*-report.json`.
For example, use `../pcjs-evidence/*-ega.json` for final frames.

`fetch_runtime.py` downloads 55 hash-locked MIT source modules plus the PCjs
license into a directory outside this repo. No OS disk or ROM is downloaded by
that helper. The source runtime is unmodified. The harness supplies Node's
filesystem adapter, official JSON machine initialization, and observational
interrupt hooks. It adds the official debugger component for CPU access.
Guest input uses PCjs's serial-mouse and keyboard methods. Host mouse scale is
explicitly 1; Windows then doubles those deltas in this particular fixture.

Each run ends after 35 seconds and writes console output, EGA VRAM snapshots,
and a report containing loaded-disk SHA-256, CPU/real-mode state, and INT F8
count. `gameplay` attempts a first-cell reveal, a rightmost-cell flag, then F2.
This timing is calibrated to the reference fixture; a slow host or different
media may not reach the expected states. **Inspect the captures**, rather than
interpreting process exit zero or trap counts as a gameplay pass.

`control` changes only AUTOEXEC.BAT in a temporary **in-memory** disk to launch
Windows without the TSR. It never writes the source disk. This is the
negative-control path; the reference specimen displays “requires a newer
version of Microsoft Windows.” It does not uninstall the shim from the image.

The renderer reconstructs 640×350 pixels from all four EGA memory planes and
the live attribute palette. It rejects unsupported display-start/stride values.
These PNGs are labeled reconstructed VRAM, not browser screenshots.

## Exact compiled bundle startup check

The source-core tests above are distinct from the delivered minified bundle.
To execute that exact hash-checked bundle in Node (still **not browser QA**):

```sh
node emulator/pcjs/verification/compiled_boot.cjs ../private-fixture ../compiled-evidence > ../compiled-boot.log 2>&1
python3 emulator/pcjs/verification/render_vram.py ../compiled-evidence/compiled-ega.json
```

This helper needs Node only, not the downloaded source runtime. It uses the
bundle's resource cache, JSON component initialization and save-state API,
then decodes the EGA state. A 15-second run reached the original game window
on the final reference disk. Node initialization printed undefined-JSON
warnings; retain the complete log. This does not exercise browser DOM,
click/focus, pointer lock, full screen or file-URL policy.

## Observed limitations

- The original TEST88 reported case 10 failure because it compared undefined
  IMUL SF/ZF flags. The corrected test excludes undefined SF/ZF/AF/PF for
  IMUL, while checking defined CF/OF and unaffected flags. Retain older failure output as historical evidence; do not
  describe the original test as passed. Check the current run output explicitly.
- RTEST2 prints `0123456789ABCDERT2PASS` in the reference run.
- Initial window, flood reveal, flag appearance, and F2 reset were observed.
- The original dark-red digit artwork is dithered by the stock EGA driver.
  Exact original-bitmap matching verified the digits, counter 010→009 on flag,
  counter 010/timer 000 after F2, and ~1 timer second per host second at 1×.
  Earlier 4× runs intentionally advanced emulated time faster.
- This is not a physical Tandy test, 8088 Windows-startup proof, browser UI test,
  or automated win/loss test.

## Artificial failure-path check

Run mode `failure` to replace TEST88.COM **only in memory** with a five-byte
DOS program returning ERRORLEVEL 1. This artificial fault tests the launcher
gate, not instruction emulation. Expect `VALIDATION FAILED` with no subsequent
Windows launch. The source disk remains unchanged. Read the console/report;
the graphics renderer deliberately rejects the resulting DOS text mode.

## Optional timing-mode measurements

`timing` mode uses the same 1× clock profile and records host-monotonic
milliseconds, BIOS ticks and CPU cycles with each snapshot. It pauses the
emulated CPU for two host seconds, resumes it, flags a square, and resets via
F2. It runs for 38 seconds (other modes run for 35 seconds).

```sh
node emulator/pcjs/verification/headless.mjs ../pcjs-runtime ../private-fixture ../pcjs-evidence timing > ../pcjs-timing.log 2>&1
python3 emulator/pcjs/verification/render_vram.py ../pcjs-evidence/timing-initial.json ../pcjs-evidence/timing-position.json ../pcjs-evidence/timing-second-*.json ../pcjs-evidence/timing-before-pause.json ../pcjs-evidence/timing-paused.json ../pcjs-evidence/timing-resumed.json ../pcjs-evidence/timing-flag.json ../pcjs-evidence/timing-question.json ../pcjs-evidence/timing-blank.json ../pcjs-evidence/timing-reset.json
python3 emulator/pcjs/verification/analyze_timing.py ../private-fixture ../pcjs-evidence > ../pcjs-timing-analysis.json
```

The analyzer requires a unique **zero-mismatch** active-red digit-mask match
against the original pinned WINMINE bitmap resource. It reports measured rates
and pause-state equality rather than inferring digits from a visually dense
EGA screenshot. Slow hosts may not achieve the requested clock speed.

To verify our renderer against the official source renderer (224,000 pixels):

```sh
node emulator/pcjs/verification/renderer_parity.mjs ../pcjs-runtime ../pcjs-evidence/gameplay-initial.json
```

To decode counters from existing reconstructed captures, without OCR guessing:

```sh
python3 emulator/pcjs/verification/read_counters.py ../private-fixture ../pcjs-evidence/gameplay-*.png
```
