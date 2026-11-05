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
  clamped to 2–32 KB (about 8 KB for this library).

The whole library for the ten games below is four modules (`ABOUTWEP`, `TETRAVEX`, `WEP4UTIL`, `WEPUTIL`), 9,912 bytes of images.

## Verification

* `tools/wep/unittest_sites3.py` runs every site against a reference implementation under
  Unicorn (tens of thousands of executions per module set: zero differences for
  `WINMINE`, `TETRAVEX` + `WEPUTIL`, and `VBRUN100`).
* `tools/wep/unittest_io3.py` exercises the file-read patching, including conflict eviction.
* End to end in MartyPC, below.

Dependencies: Python 3, `capstone`, `unicorn`. The tools take the original files as input;
no Microsoft files are in this repository. The source disk used here is the
*Best of Microsoft Entertainment Pack* image at <https://archive.org/details/wep_best-of>.

## Results (MartyPC, 8088, CGA unless noted)

| game | result |
| --- | --- |
| TetraVex | plays, bridged from the library |
| Golf | deals and plays |
| Tut's Tomb | deals and plays |
| FreeCell | starts empty by design; F2 deals |
| JezzBall | plays (its time counter runs in real time) |
| TriPeaks | reaches the player-name dialog |
| Pipe Dream, Taipei | reach the splash screen; not driven further |
| Tetris | needs no bridge, only a 16-colour 640x480 display driver ([windows-3-vga-8088](https://github.com/astrobleem/windows-3-vga-8088)); reaches About box and game window |
| Blackjack, Chips, Rodent | **do not run**, see below |

Not tested: Ski.

### What does not run

These games are flagged as protected-mode-only in their NE headers or their runtime DLL,
so real-mode Windows 3.0 refuses them. Clearing the flag and the `GetWinFlags` gate does
not make them work, and it is not a bridge problem:

* **Blackjack** contains no 80186 code at all. With the gate patched it exits quietly on a V20
  with no bridge; with the module loaded it corrupts memory, so it is not shipped.
* **Chips** ("Insufficient memory to run this application") fails the same way on a V20
  with no bridge.
* **Rodent** needs VBRUN100.DLL, which is flagged protected-mode-only. With the flag cleared
  it hangs on both an 8088 and a V20.

## Reproducing

1. Extract the games from the disk image into one directory.
2. `python3 tools/wep/w8lib.py auto LIB TETRAVEX.EXE GOLF.EXE ...` and copy `LIB` into the guest.
3. Add `WM88X3.COM <libdir>` to `AUTOEXEC.BAT` before starting Windows
   (`artifacts/WM88X3.COM`, built by `src/build_tsr3.py`).

The test-disk and emulator-runner scripts are not included: they are tied to a local
MartyPC setup.
