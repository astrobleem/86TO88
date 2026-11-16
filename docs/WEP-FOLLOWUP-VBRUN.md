# PR #4 follow-up: VB entries, Chess, Best of Rodent

Emulator results only: MartyPC (the repo's trace-hook build), IBM XT machine, 640 KB unless
stated, XT-IDE, IBM CGA, Windows 3.0 real mode. **No real hardware was tested. No game was
played through**; "played" means the brief inputs listed. "8088 core" is MartyPC's Intel 8088;
V20 runs are diagnostics (they allow tracing) and are labelled V20.

Runtime: `wip/vbrun100-realmode` at e4a47e1, `vbrun/build.sh` from the supplied originals. Default
VBRUN100.DLL / FIELD100.DLL / WEPUTIL.DLL are byte-identical to the builds tested before
(298976 / 14992 / 20544 bytes). Game files: the supplied archives (Pack 2 JIGSAWED, RATTLER,
RODENT identical to the copies tested earlier; Best of RODENT byte-identical to Pack 2's).

## Results

| entry | result | screenshots |
| --- | --- | --- |
| Pack 2 Jigsawed | 8088, beside MS-DOS Executive: About, Game>Open of C:\PUZ.BMP, scrambled puzzle, Alt+F4 to the Executive, End Session, DOS prompt | pack2-jigsawed-exit-8088.png |
| Pack 2 RattleRace | 8088, beside the Executive: F2, steering, Alt+F4, End Session, DOS prompt | pack2-rattler-exit-8088.png |
| Pack 2 Rodent's Revenge | 8088, beside the Executive: F2, blocks pushed, Alt+F4, End Session, DOS prompt | pack2-rodent-exit-8088.png |
| Best of Rodent's Revenge | separate launch, runtime built from the Best of files: same sequence passes | bestof-rodent-exit-8088.png |
| Pack 4 Go Figure! | default build: "Property or control 'uGameNewMatch' not found" (8088 ~200M instructions). With `VBLHEAP88=0x1000 VBLHEAP71=0x4000`: game window, Game menu opened and closed (8088, as shell). **Beside the Executive, default build (8088): window, Game menu, F2 starts a puzzle (digits dealt, score and timer running), Alt+F4 to the Executive, End Session, DOS prompt.** Larger heaps beside the Executive: hang from memory corruption (see below) | gofigure-default-beside-executive-newgame-exit-8088.png, gofigure-heaps-menu-8088.png, gofigure-default-576k-640k.png, gofigure-heaps-beside-executive-hang-8088.png |
| Pack 4 Tic Tac Drop | splash and credits; "Invalid property value" (error 380) at ~460-490M, default and larger heaps; traced to a combo box selection with index -2 | tictacdrop-converted-splash-8088.png, tictacdrop-converted-error-8088.png |
| Pack 4 Chess | three COMMDLG variants compared; none gives a usable game; see below | chess-commdlg-original-flagcleared-converted-8088.png |

With the larger heaps the Pack 2 regressions pass the same Executive sequence on the 8088
core (Jigsawed, RattleRace, Rodent).

## Go Figure!: missing control

V20 trace with GlobalAlloc/GlobalReAlloc/LocalAlloc/MessageBox watched. 44 LocalAlloc
calls fail between 16.67M and 17.07M instructions, all in one VB local heap (VBRUN seg 88's
heap, created 0x400+0x210 bytes, locked). KERNEL's LocalGrow asked GlobalReAlloc to grow it
to 0x840 in place and that failed; nothing else failed before the error. The failed
allocations were not matched one by one to control names. With 576 KB instead of 640 KB
(8088, not traced) the error comes at the same time and names a different control
('uLevelBeginner'). About 100 KB was free at the error, so total free memory is not what
fails; the locked heap cannot grow where it sits. Creating the seg
88 heap with 0x1000 (and seg 71's with 0x4000, the next heap that failed to grow) removes
every allocation failure. These sizes are opt-in; the default build is unchanged.
Beside the Executive the default build works (above). With the larger heaps it hangs, and
that is memory corruption, not exhaustion: VBRUN seg 73 copies a "counted string" from a
stale pointer (it points into a block that now holds p-code; its length byte 0xDD is
sign-extended), so ~64 KB is written over the stack segment and the next heap arenas. The
pointer comes from VB's module-context table; with the converter's moving context grow
(`CTXGROW`) disabled the window appears (V20). So that grow leaves another holder of a
block's old segment; the holder is not yet identified.

## Tic Tac Drop: invalid property value

No LocalAlloc failure; four in-place GlobalReAlloc failures (VBRUN seg 105, 0x470 bytes)
that VB retries. The larger heaps do not change the error, so the low-memory explanation does
not hold here. V20 instruction trace before VB's raiser (entry 106, seg 7:0294, BX=0x17C =
380, at 487.95M): VBRUN seg 83 passes message 0x040E (CB_SETCURSEL) with index -2 to a combo
box's original window procedure; USER returns -1 (CB_ERR) and VB reports error 380. Where the
-2 comes from is not established.

## Chess

Common: original CHESS.EXE, original WEP4UTIL.DLL, WM88X3.COM 3,991 bytes from PR #4, a
module library built with `tools/wep/w8lib.py auto` (CHESS 1698 sites including 80 ENTER,
WEP4UTIL 219), OPENING.BK/OPENING.TXT in C:\ (Chess opens "opening.bk" in the current
directory), beside the Executive, CGA. Chess imports COMMDLG (ordinals 1, 2, 20); the copy
loaded is C:\WINDOWS\SYSTEM\COMMDLG.DLL. The converted COMMDLG contains no INT 3 and no
80186 instruction, so it does not depend on VBRUN's INT 3 handler.

| COMMDLG | 8088 result | last successful operation |
| --- | --- | --- |
| original | "Cannot run C:\GAME\CHESS.EXE" | COMMDLG header read (protected-only flag) |
| original, flag cleared by the library (as PR #4) | runs off to 00FF:0003 at ~47M; counter stops | opening.bk opened |
| converted | runs off to A600 at ~22M | ENTPACK.INI reads, before opening.bk |

V20 trace of the converted case: a USER routine returns far into Chess code at its old
address after the Chess code segment (movable) moved; the stack then wraps. The flag-cleared
case (V20) also ends with SP wrapped and a jump to E000; it was not traced further. COMMDLG changes the timing; it was not shown to be on the
failing path. Separately, a LEAVE at Chess 1:64DB is not in the module library (its function
has no static reference); it executes before the failure and would run as RETF on an 8088.

## Tests

`python3 -m pytest vbrun/tests`: 107 passed. `python3 vbrun/tests/test_tools.py`: 91 tests
including the four ordinal-reference tests. `vbrun/i186test.py` per-site differential: VBRUN
2974 sites / FIELD100 89 / WEPUTIL 223 (default and larger-heap builds), GAUGE 112, THREED
742, CMDIALOG 98: no difference. Lower-case control names build identical outputs.

## Original-control comparison (V20 only, diagnostic)

With the unconverted controls on the V20 (which runs 80186 code natively) VB stops at load:
Go Figure "Custom control 'SSPanel' not found", Tic Tac Drop "Custom control 'CommonDialog'
not found" (gofigure-original-controls-v20.png, tictacdrop-original-controls-v20.png). These
are not 8088 results.

## Screenshots

All in [evidence/pr4-followup](../evidence/pr4-followup/). Heap-variant regressions:
pack2-jigsawed-exit-heapvariant-8088.png, pack2-rattler-exit-heapvariant-8088.png,
pack2-rodent-exit-heapvariant-8088.png. Each image is a grid of the frames in run order.
