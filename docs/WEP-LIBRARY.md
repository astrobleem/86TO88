# Entertainment Pack games on a stock 8088: the module library

Technical notes. The README links here; nothing in it depends on this file.

The WM88 bridge started as one hard-coded patch table for `WINMINE.EXE`. This work
generalises it: an offline analyzer finds every 80186 instruction in a Windows 3.x NE file,
writes a small per-file **module**, and a second, much smaller TSR (`WM88X3.COM`) loads
modules on demand while Windows reads files. All of it was tested only in MartyPC (cycle-accurate
8088 and V20 cores). None of it has been run on physical hardware.

## Why static patching

On a true 8088 the 80186 opcodes do not fault, they alias (`6A` runs as a conditional jump,
`C1` as `RET`, `0F` as `POP CS`). A trap-on-invalid-opcode design cannot work, so the
instructions have to be removed from the code before it executes. The TSR hooks the DOS
read call, and when Windows reads a known file it rewrites each site in the read buffer to
`INT F8h`..`FEh` (or `INT 3`). The handler performs the operation for the caller and
resumes after it.

The hard part is knowing which bytes are code. `analyze_ne.py` does a recursive-descent
census per code segment from the entry table and relocation targets, so ASCII data and
jump tables are never mistaken for instructions. Jump-table targets are decoded in a
second, lower-confidence pass that may not overlap instructions already reached by
direct flow (this removed a false `shr cl,0` inside a `mov ax,imm` in one game).

## Site types

| type | instruction | notes |
| --- | --- | --- |
| 0 | `push imm` | |
| 1 / 2 / 3 | `shl` / `shr` / `sar` by immediate | word form `C1`, byte-register form `C0` |
| 4 | `imul r,r,imm` | |
| 5 / 6 | calling-convention push / leave | `INT 3` key, ctx-aware |
| 7 | `imul reg,[ea],imm8` | |
| 9 | `imul reg,[ea],imm16` | the immediate is read from the code stream by the handler |
| 8 | static byte patch | never trapped; used for the version stamp and similar |

Immediates that are covered by a relocation fix-up are resolved by the generator rather
than copied from the file.

## The library

A module is `BASE.W8x` (x is the first letter of the file extension): a 66-byte header
(`W8M1`, site count, conflict count, the vector table, the file name, size and CRC, the
read window), then 12 bytes per site, then a list of conflicting modules.

* `tools/wep/w8lib.py auto LIB GAME.EXE...` analyzes each EXE and the helper DLLs it imports
  (found beside it), adds the modules and records the game's module set in `GAMES.TXT`.
  `list` and `check` report and verify it.
* Trap vectors are allocated **per site**, not per segment. Two modules of one game must be
  collision-free. Modules of different games may collide; the pair is recorded as a
  conflict and the TSR evicts the resident one when the other loads.
* The TSR looks a file up by name and size on open, reads `LIB\BASE.W8x` into an arena,
  validates it and keeps up to six modules resident. The terminating process's modules
  are freed on exit. The library directory is the TSR's command-line argument (default `C:\W8X`).
* Footprint: about 3.1 KB of resident code. The arena is twice the largest image,
  clamped to 2–32 KB .

A pack's library is a handful of modules, 7-17 KB of images in total (Pack 1: 16.9 KB, Pack 3: 10.9 KB).

## Verification

* `tools/wep/unittest_sites3.py` runs every site against a reference implementation under
  Unicorn (tens of thousands of executions per module set: zero differences for
  `WINMINE`, `TETRAVEX` + `WEPUTIL`, and `VBRUN100`).
* `tools/wep/unittest_io3.py` exercises the file-read patching, including conflict eviction.
* End to end in MartyPC, below.

Dependencies: Python 3, `capstone`, `unicorn`. The tools take the original files as input;
no Microsoft files are in this repository. The source disk used here is the
*Best of Microsoft Entertainment Pack* image at <https://archive.org/details/wep_best-of>.

## Results (MartyPC, 8088 + CGA, each game with its own pack's library)

Each pack gets its own library, because the same file name can be a different build in different
releases (`TETRAVEX.EXE` differs between the 1994 disk and Pack 3).

| pack | runs | does not run |
| --- | --- | --- |
| Pack 1 (1991) | Cruel, Idlewild (a screen saver, it blanks the display), Pegged, TicTactics, Taipei (splash), WinMine (the Windows 3.0 build) | |
| Pack 2 (1991) | FreeCell (empty until F2), Pipe Dream (title and board), Tut's Tomb | Stones, Jigsawed, Rattler, Rodent |
| Pack 3 (1991) | Fuji Golf, Klotski, LifeGenesis, Ski, TetraVex, TriPeaks (name dialog), WordZap | |
| Best of (1994) | TetraVex, Golf, Tut's Tomb, FreeCell, JezzBall, TriPeaks, Pipe Dream and Taipei (splash); Tetris with the 16-colour driver | Blackjack, Chips, Rodent |

"Runs" means the game window came up and, where I looked, dealt or drew; I did not play any game
through. Pipe Dream and Taipei were only taken as far as their opening screens. Tetris needs no
bridge, only the 640x480 16-colour display driver
([windows-3-vga-8088](https://github.com/astrobleem/windows-3-vga-8088)). Fuji Golf also needs
`FUJIGOLF.DAT`, which the disk stores packed as `FUJIGOLF.DA$`.

### What does not run

These are real-mode limits, not bridge faults. Each was checked on a V20 with no bridge and fails the same way
(or, for Blackjack, behaves worse with the module).

* **Blackjack** is flagged protected-mode-only and contains no 80186 code at all. With the flag and the
  `GetWinFlags` gate patched it exits quietly; with the module loaded it corrupts memory, so it is not shipped.
* **Chips** ("Insufficient memory to run this application").
* **Rodent, Rattler, Jigsawed** use VBRUN100.DLL, which is flagged protected-mode-only. With the flag cleared Rodent hangs
  on an 8088 and on a V20. Rattler and Jigsawed also hang on the hourglass.
* **Stones**: its style DLLs (`STONE00`..`STONEE03`) carry the protected-mode flag and the game reports that they
  are corrupted or missing; clearing the flag does not change that.

## Reproducing

1. Get the game files. The 1994 disk (<https://archive.org/details/wep_best-of>) is a normal installable disk. The 1991 packs
   keep everything in `BIN\` as packed `*.EX$`, `*.DL$` and `*.DA$` files; the disk's own `EXPAND.EXE` (Pack 1)
   unpacks them under DOS (`EXPAND GOLF.EX$ GOLF.EXE`). I ran it inside MartyPC and read the results back from the disk image.
2. `python3 tools/wep/w8lib.py auto LIB TETRAVEX.EXE GOLF.EXE ...` per pack. Games that load DLLs by name rather than by import
   (Stones) need `w8lib.py add LIB FILE 1` for each DLL.
3. Copy `LIB` into the guest and add `WM88X3.COM <libdir>` to `AUTOEXEC.BAT` before starting Windows
   (`artifacts/WM88X3.COM`, built by `src/build_tsr3.py`).

The test-disk and emulator-runner scripts are not included: they are tied to a local
MartyPC setup. MartyPC's CGA card crashes with turbo on; use normal speed.

## Bug found by testing

Idlewild contains two `imul reg,[bp-4],imm16` instructions (opcode `69`). The first version of the loader only
handled the `6B` (imm8) form, so those two ran unpatched on the 8088 and Idlewild hung on the hourglass.
Type 9 fixes that; its differential test passes. Running a game on a V20 with no bridge, as a reference, is what
separated bridge faults from real-mode limits.
