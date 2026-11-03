# PCjs fixture validation — 2026-11-02

**Status: preparation, actual PCjs headless execution, and Chrome browser
boot/basic gameplay and loss/restart verified. Fullscreen and complete wins remain
unverified. Not an 8088 validation.**

Base repository commit: `570e776eb2845688013d267574f3ead06171791d`.
Final generated disk SHA-256:
`de9ec058a44090f13f7b6e47c647f09390fe0ee39c2333998a87281f402eb6aa`.

## Windows preparation check - 2026-11-03

### Chrome browser follow-up - authorized extension connected

The documented loopback server (`python -m http.server 8080 --bind 127.0.0.1`)
served the private fixture to the installed Chrome browser. The actual page
initialized the compiled PCjs bundle, loaded the pinned disk/ROMs and reached
the original Minesweeper window. A reload booted a fresh covered board.

Normal trusted browser mouse events revealed numbered/empty cells, placed a
flag (counter 010 to 009), and cycled it to a question mark (counter 010) and
blank. The timer advanced during play. Keyboard Alt+G opened the guest Game
menu; Escape closed it. F2 cleared the board and reset the timer to 000 and
mine counter to 010. No direct emulator-state mutation or headless input was
used for these browser gameplay checks.

Halt changed the control to Run and printed `CPU: Stopped`; Run resumed the
CPU and changed the control back to Halt. This checks the browser controls,
not a fresh calibrated pause/timer measurement.

The standalone `judge.html` initially exposed a browser-blocking startup bug:
PCjs reads optional settings from `window.resources.parms`, which was absent.
Its attempted `JSON.parse(undefined)` produced repeated alert dialogs. The
builder and exact-compiled-bundle verifier now include `parms: '{}'`. The
corrected standalone page reached Minesweeper without those alerts through the
same loopback server; its captured warning/error log was empty. Normal clicks
revealed a numbered cell and then a mine, producing the red exploded mine,
exposed mines and loss face. F2 restarted with a covered board and zero timer.
The ordinary `index.html` path had already booted and passed
the gameplay checks above. Disk, specimen, runtime bundle and ROM bytes are
unchanged by this fix.

The mouse is relative, so browser coordinates do not directly select the same
guest pixel. The first focus can scroll the page. The normal in-page display
remained usable; this behavior is now explained in the page/README.
Temporary DOM input diagnostics confirmed trusted browser mouse events and
were removed from the generated fixture after diagnosis; they are not part
of this patch.

Full screen did not activate through the extension: Chrome logged
`TypeError: not granted` on both attempts. No browser permissions/settings
were bypassed or changed. This is a limitation of this tested automation path,
not proof that a human fullscreen click fails. The file:// route and complete
winning sessions were not verified. The earlier browser-connection blocker
below is historical and was resolved by the user's extension authorization.
Opening the manifest link through automation returned `net::ERR_BLOCKED_BY_CLIENT`;
it was not retried or bypassed. The generated PREPARED.json was inspected
locally during the Windows preparation check.

The patch applied to the exact base commit in a clean Windows clone. All 16
host tests passed, and the documented automatic reference-media preparation
completed with every pinned input/runtime hash verified. No browser startup
or gameplay is claimed from this host check.

Windows Git checkout converted `deliverable/WM88.BAT` to CRLF, initially
producing disk hash `7ad8cf8f3240946a1270fa11e7bf5373ed5db8dcb127a347b92b0c8061296684`.
Normalizing only that file to its canonical LF bytes reproduced the validated
disk hash above exactly. The builder now normalizes this input so checkout
line-ending preferences do not change the disk.

Chrome, Edge and Firefox are installed on this Windows host, but the available
browser-control inventory is empty. Chrome and Edge connection attempts both
returned `Browser is not available`; native desktop control is disabled in
this session. Browser layout, startup, mouse/focus, right-click, F2, full
screen, reload and full win/loss experience therefore remain unverified.

## Passed

* 16 host unit tests: codec, FAT12/16 editing, matching FAT copies, malformed
  inputs, atomic failure, source/output guards, asset pins, CPU profile and
  DOS error-level gates.
* Actual automatic `--reference-media` download/preparation path was run;
  final iterations used the identical hash-checked local source media.
* Every runtime/ROM download matched its pinned SHA-256. Original inputs were
  not edited. The private disk retains all 107 original files other than its
  deliberately replaced AUTOEXEC.BAT and CONFIG.SYS, byte-for-byte.
* Offline HTML has two syntactically valid JavaScript blocks, no external
  script sources, and embedded disk/ROM bytes matching the generated files.
* TSR and shim rebuilt byte-identically to the published binaries. The
  supported builders no longer depend on the original developer's absolute
  checkout path.
  The optional Capstone opcode audit was **skipped** (not installed), not
  represented as passing.
* On the pinned official **PCjs source core**, the final disk emitted
  `T88PASS` and `0123456789ABCDERT2PASS`, then started original Minesweeper.
* Actual serial-mouse input revealed numbered cells and placed a flag;
  keyboard F2 reset the board and removed the flag. These were visually
  inspected in EGA VRAM reconstructions, not inferred from process exit.
* No-bridge control (only the in-memory AUTOEXEC changed) produced the
  expected newer-Windows-version refusal. The original on-disk source stayed
  unchanged.
* Artificial failure control substituted a five-byte DOS `exit(1)` TEST88
  in memory. It left a visible `VALIDATION FAILED` message and DOS prompt;
  Windows was not launched. The real TEST88 was not claimed to fail in this run.
* Final 1× source-core gameplay report: 2,032 INT F8 traps, CPU 80286,
  640 KiB RAM, EGA mode 10h, MSW `FFF0h` (PE clear). This distinguishes CPU
  model from sampled real-mode state; it is not a Tandy timing benchmark.
* Separately, the **exact delivered compiled bundle** (SHA-256
  `724c396d9bf602554194bd118a5c164e739447080d487161af375bb9a4d5de4a`)
  ran in Node using PCjs' resource cache and JSON component initialization.
  Its saved EGA state after 15 seconds visibly contains Minesweeper; MSW is
  `FFF0h`, mode 10h. This establishes compiled-core startup, not browser DOM
  initialization or input handling. That Node initialization printed
  `"undefined" is not valid JSON` warnings; these are retained, not hidden.

## Inspectable evidence

All captures below are **reconstructed EGA VRAM**, not browser screenshots.

| Stage | Capture |
| --- | --- |
| Original game window | [Initial](../../evidence/pcjs-headless/gameplay-initial.png) |
| Numbered reveal | [Reveal](../../evidence/pcjs-headless/gameplay-reveal.png) |
| Flag appears | [Flag](../../evidence/pcjs-headless/gameplay-flag-timer.png) |
| F2 clears board/flag | [Reset](../../evidence/pcjs-headless/gameplay-ega.png) |
| No-bridge refusal | [Control](../../evidence/pcjs-headless/control-ega.png) |
| Exact compiled bundle, Node boot | [Compiled core](../../evidence/pcjs-headless/compiled-ega.png) |

Reports: [gameplay](../../evidence/pcjs-headless/gameplay-report.json),
[control](../../evidence/pcjs-headless/control-report.json),
[artificial failure](../../evidence/pcjs-headless/failure-report.json).
The [optional headless tooling](verification/README.md) reproduces these runs.
Compiled run: [report](../../evidence/pcjs-headless/compiled-report.json),
[full log, including warnings](../../evidence/pcjs-headless/compiled-boot.log).

## Counter/timer concern resolved — original artwork, normal speed

The initial “malformed glyph” suspicion was disproved. Our reconstructed
renderer matches the official PCjs EGA renderer across **224,000 pixels with
zero channel differences**. The stock palette has bright red but lacks the
bitmap's dark red, so Windows' original EGA driver approximates inactive
segments with dithering. This is not damaged game logic or invented display.

A decoder reads the original digit bitmap from the pinned private WINMINE
specimen and requires a unique **zero-mismatch active-red pixel mask** for
every displayed glyph. It does not use approximate OCR or alter the guest.

The final **1×** profile (rather than the earlier accelerated 4× profile) verified:

* Mine counter 010→009 on a flag; second right-click gives question mark and
  counter 010; third right-click clears the question mark with counter 010.
* Timer 002→007 over **4.995241299 host seconds**, with 91 BIOS ticks. Each
  successive one-second capture advances exactly one displayed second.
* A 2.00269-second **emulator CPU pause** holds timer 008, BIOS ticks and CPU
  cycles unchanged; resume advances the timer.
* F2 resets the board, mine counter 010 and timer 000.

See [exact timing readings](../../evidence/pcjs-headless/timing-analysis.json),
[timing run metadata](../../evidence/pcjs-headless/timing-report.json),
[gameplay counter readings](../../evidence/pcjs-headless/counter-readings.json),
and [renderer parity](../../evidence/pcjs-headless/renderer-parity.json).
All digits in these reports matched their original-resource templates exactly.
This is a bounded emulator observation, not a calibrated hardware benchmark.

## TEST88 correction, not a bridge change

The old TEST88 compared the entire FLAGS word after IMUL. In PCjs, cases 9/10
had correct results/registers/stack but SF/ZF differed from the separate native
reference calculation. Those two bits, along with AF/PF, are undefined after
IMUL in [Intel's original 80286 manual, section 3.3.3](https://bitsavers.org/components/intel/80286/210498-005_80286_and_80287_Programmers_Reference_Manual_1987.pdf).

The bounded correction compares `(got ^ expected) & FF2Bh` for IMUL only:
CF/OF and unaffected control flags remain checked, as do result/register/stack
and other cases. The uninstrumented corrected suite emitted `T88PASS`.
[Exact diagnosis and old failure states](../../evidence/pcjs-headless/TEST88-DIAGNOSIS.md)
are retained (diagnostic log trailing whitespace normalized for the patch). WM88TSR, SHELL.DLL and WINMINE.EXE are unchanged by this correction.

Corrected TEST88: 13,696 bytes, SHA-256
`3231096590db8230cdd8739b383cf1b2b681e0942c2a047fb9268cb0f3810645`.
Other existing multibit-shift assertions also include undefined AF/OF values;
they passed this run but are not claimed universally portable.

## Earlier execution-environment limitations (historical)

* The dark-red inactive digit segments are authentically dithered by the stock
  EGA driver, not corrupt. Native-size digits have low contrast; enlargement or
  full screen can help. The game bitmap and driver were not patched.
* Browser click/focus/right-click, full screen, page layout, reload/session
  behavior and offline-file browser compatibility have not been exercised.
  Headless serial/keyboard input does not validate browser event handling.
* Chromium launch against the local fixture could not create its Unix socket
  inside the execution sandbox (`Operation not permitted`). The permitted
  escalation attempt failed before launch because environment setup could
  not create its protected read-only sessions path. That path was not read
  or changed.
* The independent pre-existing cloud browser could not reach the isolated
  loopback server. Opening the private offline file was explicitly denied by
  its URL policy, which allows only HTTP/HTTPS. No workaround was attempted
  after that denial.
* No Windows startup/gameplay was validated on PCjs 8088, no physical hardware
  was tested here, and no complete win/loss session was performed here.
* Microsoft media/ROM output is intentionally outside the public repository
  and remains local/private. The source setup and validation evidence contain
  no guest disk or ROM image.
