# Fresh Entertainment Pack diagnostics — 14 November 2026

**Incomplete.** These are new attempts, not a complete compatibility pass. No
fresh card move or complete gameplay was established. Golf and Cruel accepted
new-deal commands and exited to Windows. All eight Pack 1 entries were also
attempted. The remaining
entries in the [edition inventory](WEP-COVERAGE.md) have not been freshly run
in this session. Historical MartyPC results remain separate.

## Configuration

DOSBox-X 2025.02.01, `cputype=8086_prefetch`, CGA, 640 KiB conventional
memory, Windows 3.0 real mode, MS-DOS Executive, and 20,000 emulator cycles/ms.
This is an **emulated 8086**, not an emulated or physical 8088, and it is not a
speed measurement. Windows reached MS-DOS Executive without the bridge before
game testing. The Pack 4 runs loaded current `WM88X3.COM` and a freshly
generated Pack 4 module library. The conversion was generated from the current
merged repository for VBRUN100, FIELD100 and WEPUTIL; the Go Figure and Tic Tac
Drop attempts had the converted VBRUN100 in Windows SYSTEM, with the original
copy removed from GAME. The earlier Pack 4 attempts had an original VBRUN100
in GAME as well, a potential search-order confounder. Pack 4 uses its own
WEP4UTIL, for which the module library was generated.

The separate Best of RODENT run used the freshly converted DLLs without the
WM88X3 library. Its original EXE and VBRUN100 were byte-for-byte equal to the
Pack 2 versions in the recovered fixture. The Best of EXE was still launched
independently. No proprietary binaries or disk images are committed here.

Some Pack 4 module generation reported unsupported instructions, including
`ENTER` in Chess and memory IMUL in CMDIALOG.VBX. A generated module is not
proof that all code was translated. In particular, the following single-run
observations have not yet been repeated or isolated enough to call them
reproducible game defects.

## Pack 1 follow-up

Same DOSBox-X 8086-prefetch/CGA configuration, with a Pack 1-specific WM88X3
module library and the Pack 1 files. Windows reached MS-DOS Executive before
launches. These are single attempts and are not 8088 claims.

| Executable | Observation | Input / exit | Evidence |
| --- | --- | --- | --- |
| GOLF.EXE | Dealt board, clipped by the CGA display | Game > New dealt a different board; exited to Windows. No card move verified. | [screen](../evidence/wep-20261114/pack1-golf-8086-cga.png) |
| CRUEL.EXE | Dealt board, clipped by the CGA display | Game > New dealt a different board; exited to Windows. No card move verified. | [screen](../evidence/wep-20261114/pack1-cruel-8086-cga.png) |
| TETRIS.EXE | Reported insufficient monitor resolution | No gameplay | [screen](../evidence/wep-20261114/pack1-tetris-8086-cga.png) |
| PEGGED.EXE | ROM BASIC message loop after launch | No gameplay or exit observed | [screen](../evidence/wep-20261114/pack1-pegged-8086-cga.png) |
| WINMINE.EXE | ROM BASIC message after launch | No gameplay or exit observed | [screen](../evidence/wep-20261114/pack1-winmine-8086-cga.png) |
| TIC.EXE | ROM BASIC message after launch | No gameplay or exit observed | [screen](../evidence/wep-20261114/pack1-tictactics-8086-cga.png) |
| TP.EXE | ROM BASIC message loop after launch | No gameplay or exit observed | [screen](../evidence/wep-20261114/pack1-taipei-8086-cga.png) |
| IDLEWILD.EXE | ROM BASIC message after launch | No saver operation or exit observed | [screen](../evidence/wep-20261114/pack1-idlewild-8086-cga.png) |

[Pack 1 contact sheet](../evidence/wep-20261114/pack1-contact-sheet.png).

The ROM BASIC messages are emulator outcomes, not diagnoses of the specific
cause. In particular, the runs need repetition on MartyPC and examination of
module and memory behavior before being treated as reproducible failures.

## Observed results

| Edition / executable | Fresh observation | Input / exit | Evidence |
| --- | --- | --- | --- |
| Pack 4 JEZZBALL.EXE | Board drawn; no change observed after click, F2 or Alt+F4 | No successful input or exit verified; partial | [screen](../evidence/wep-20261114/pack4-jezzball-8086-cga.png) |
| Pack 4 CHESS.EXE | Windows reported “Cannot run” | No game input or exit | [screen](../evidence/wep-20261114/pack4-chess-8086-cga.png) |
| Pack 4 BLAKJAK.EXE | After launch attempt, emulator displayed “IBM ROM BASIC NOT IMPLEMENTED”; no game screen | No game input or exit | [screen](../evidence/wep-20261114/pack4-blackjack-8086-cga.png) |
| Pack 4 CHIPS.EXE | Windows reported insufficient memory | No game input or exit | [screen](../evidence/wep-20261114/pack4-chips-8086-cga.png) |
| Pack 4 GOFIGURE.EXE | “Custom control 'Gauge' not found” | Error dismissed back to Windows; no gameplay | [screen](../evidence/wep-20261114/pack4-gofigure-8086-cga.png) |
| Pack 4 MAXWELL.EXE | After launch attempt, emulator displayed “IBM ROM BASIC NOT IMPLEMENTED”; no game screen | No game input or exit | [screen](../evidence/wep-20261114/pack4-maxwell-8086-cga.png) |
| Pack 4 TICTACDP.EXE | Could not load CMDIALOG.VBX | No gameplay or clean game exit verified | [screen](../evidence/wep-20261114/pack4-tictacdrop-8086-cga.png) |
| Best of RODENT.EXE | Screen corrupted after launch | No game input or exit verified | [screen](../evidence/wep-20261114/bestof-rodent-8086-cga.png) |

[Contact sheet](../evidence/wep-20261114/contact-sheet.png). Images are direct
DOSBox-X capture output from these attempts. They do not show 8088 execution.
Results are limited to this configuration and do not invalidate earlier MartyPC
results or prove that another configuration fails. Repeat each failed case,
correct dependency loading and separate bridge interactions before assigning a
reproducible failure status.
