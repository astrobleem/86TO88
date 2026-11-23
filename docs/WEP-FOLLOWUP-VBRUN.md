# PR #4 follow-up: VB entries, Chess, Best of Rodent

Emulator results only: MartyPC (the repo's trace-hook build), IBM XT machine, 640 KB unless
stated, XT-IDE, IBM CGA, Windows 3.0 real mode. **No real hardware was tested. No game was
played through**; "played" means the brief inputs listed. "8088 core" is MartyPC's Intel 8088;
V20 runs are diagnostics (they allow tracing) and are labelled V20.

Runtime: `wip/vbrun100-realmode` at 4df6ab9 (notes up to f521d4b), `vbrun/build.sh` from the supplied originals. Default
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
| Pack 4 Go Figure! | default build: "Property or control 'uGameNewMatch' not found" (8088 ~200M instructions). With `VBLHEAP88=0x1000 VBLHEAP71=0x4000`: game window, Game menu opened and closed (8088, as shell). **Beside the Executive, default build (8088): window, Game menu, F2 starts a puzzle (digits dealt, score and timer running), Alt+F4 to the Executive, End Session, DOS prompt.** Larger heaps beside the Executive: hang from memory corruption (see below); **with opt-in `CTXMIRROR=1` the same sequence passes, larger heaps and default sizes (8088)** | gofigure-default-beside-executive-newgame-exit-8088.png, gofigure-heaps-ctxmirror-beside-executive-exit-8088.png, gofigure-default-ctxmirror-beside-executive-exit-8088.png, gofigure-heaps-menu-8088.png, gofigure-default-576k-640k.png, gofigure-heaps-beside-executive-hang-8088.png |
| Pack 4 Tic Tac Drop | Hercules, as shell, 8088 (current build): game window and Game menu. CGA: the game's own error (see below). Earlier: "Invalid property value" (error 380) at ~460-490M, default and larger heaps; traced to a combo box selection with index -2 | tictacdrop-converted-splash-8088.png, tictacdrop-converted-error-8088.png |
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
block's old segment. The holder is DGROUP word 2E28: VB copies the main context record's
segment there (VBRUN seg 5) and seg 4:1609 returns it as the segment of the name strings
that seg 73 copies. In the V20 trace the first moving grow moved 5803 to 59CB and updated
only the record; 2E28 still held 5803. The new opt-in `CTXMIRROR=1` makes the converter's
grow stub update 2E28/2E2A when they hold the moved block's old segment. With it, on the
8088 core beside the Executive, Go Figure with the larger heaps and with the default sizes
both pass (window, Game menu, F2 starts a puzzle, Alt+F4, End Session, DOS prompt), and
Pack 2 Jigsawed, RattleRace and Rodent pass their exit sequences
(pack2-*-exit-ctxmirror-8088.png). Without the switch the runtime is byte-identical to the
earlier default.

## Tic Tac Drop: invalid property value

No LocalAlloc failure; four in-place GlobalReAlloc failures (VBRUN seg 105, 0x470 bytes)
that VB retries. The larger heaps do not change the error, so the low-memory explanation does
not hold here. V20 instruction trace before VB's raiser (entry 106, seg 7:0294, BX=0x17C =
380, at 487.95M): VBRUN seg 83 passes message 0x040E (CB_SETCURSEL) with index -2 to a combo
box's original window procedure; USER returns -1 (CB_ERR) and VB reports error 380. Where the
-2 comes from is not established. Beside the Executive (default build, 8088) the same error
appears (tictacdrop-default-beside-executive-error-8088.png), so it does not depend on being
the shell. With the converted COMMDLG and the original CMDIALOG/THREED/GAUGE (V20, diagnostic)
VB still stops at load with "Custom control 'CommonDialog' not found", so the original
controls cannot be compared at the point of the error.

**Reference runs in DOSBox 0.74-3** (another emulator, 386 core, same Windows 3.0 disk
image, MS-DOS Executive as shell; tictacdrop-dosbox-reference-*.png, top row then bottom):
the original, unconverted Tic Tac Drop in standard mode shows the same "Invalid property
value" on CGA and works on VGA and Hercules; the converted files in real mode show the error
on CGA and work on Hercules; the original files in real mode cannot run (protected-only
COMMDLG). So the CGA error belongs to the game on a 640x200 display, not to the conversion.
What remains is MartyPC-specific: with Hercules the converted game stops at "Control array
element '8224' does not exist" (8088, beside the Executive,
tictacdrop-hercules-default-beside-executive-8088.png); with the 8088 VGA88 driver
"Property or control 'OptPlayersSubMenu' not found" (tictacdrop-vga-default-beside-executive-8088.png),
and with larger heaps "Can't create AutoRedraw image". Not yet explained.

**"System Error / Terminating current application" (as the shell with Hercules or VGA88):
found and fixed.** V20 ring trace: COMMDLG raises INT 3F to reload its discarded segment 6;
KERNEL reopens C:\WINDOWS\SYSTEM\COMMDLG.DLL and DOS answers "file not found", because
real-mode KERNEL sized COMMDLG's module block up to the last path character and the path's
NUL fell on the next arena header (the open log shows the name followed by garbage). It
happens when the path ends on a paragraph boundary, which the converted COMMDLG's header
layout produced for C:\WINDOWS\SYSTEM. The converter now pads the imported-names table
(`NEPATHS`, default C:\WINDOWS\SYSTEM\ and C:\WINDOWS\) so the NUL stays inside;
COMMDLG gets 1 byte, WEP4UTIL some, default VBRUN100/FIELD100/WEPUTIL are unchanged
(`wip/vbrun100-realmode` 8a405c1). With it the dump shows the NUL intact and the System
Error is gone; Tic Tac Drop with Hercules on the 8088 (as shell and beside the Executive)
now stops later with "Illegal function call" (tictacdrop-hercules-padded-8088.png).

**Missed 80186 sites in VBRUN: found and fixed.** As the shell with Hercules on the V20 the
same build shows the Tic Tac Drop game window (tictacdrop-hercules-shell-window-v20.png),
while the 8088 shows "Illegal function call". A V20 run with MartyPC's 80186-opcode report
found PUSH 0 executing at VBRUN 2:489C/489E (46 times by 526M): p-code escape handlers
reached only through the runtime's word jump tables (MOV BX,table then JMP 2:3B9D, or
JMP CS:[BX-2]), which the converter's code discovery did not follow. On an 8088 those
bytes run as a conditional jump. The converter now takes those tables' entries as candidate
code (`wip/vbrun100-realmode` 0507e8e); that adds exactly 10 sites (2:489C..48F0), the
per-site differential test passes (2984 sites, 8937 runs, 0 failures), and **VBRUN100.DLL
is no longer byte-identical to the earlier build** (FIELD100 and WEPUTIL are). With it,
on the 8088 beside the Executive, Pack 2 Jigsawed (About, Open, scramble), RattleRace and
Rodent pass the exit sequence again (pack2-*-exit-tables-8088.png), Go Figure (default
sizes) passes window, Game menu, F2 puzzle, Alt+F4, End Session, DOS, and Tic Tac Drop on
CGA still shows the game's own "Invalid property value"
(gofigure-default-exit-and-tictacdrop-cga-tables-8088.png). Tic Tac Drop with
Hercules beside the Executive then gets past the point of the earlier errors and ends in
"System Error" at ~800M with 43 KB free in pieces (largest 19 KB) and all module paths
intact; consistent with a segment that no longer fits, not traced. (The driver script had sent Alt+G/Esc at 701M before it was stopped.) **As the shell (more free memory) the 8088 now shows the Tic Tac Drop game window with
Hercules at ~450M and its Game menu opens** (tictacdrop-hercules-shell-window-gamemenu-8088.png;
Alt+F4 then ends Windows, as for any shell). Beside the Executive with BUFFERS=10 it still
ends in "System Error" (tictacdrop-hercules-beside-executive-buffers10-syserror-8088.png). Windows' global heap on this MartyPC setup spans 0F4C-A000 (~580 KB); in DOSBox
(632 KB free) the converted game runs with Hercules, and fails with "System Error" when
48 or 64 KB are taken away first (works at 16-44 and at 56), so it is close to the memory
limit; that DOSBox failure was not traced.

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

Since then (the V20 runs above loaded WM88X3 without /V, so its 8088 rewriting was active
there too; a /V comparison was not run): the Chess function whose call returns to the stale address
(1:9F18) has an ENTER prolog; only 19 of Chess's far prologs carry the real-mode
`inc bp` marking that KERNEL's stack walk uses to fix far returns when a code segment
moves. That fits the stale return but was not proven. A first test-only copy of CHESS.EXE with
code segment 1 marked FIXED ran off at ~26M, but that run is invalid: the module library
keys each image by size and checksum, so the changed copy got none of its Chess patches. Rerun with a library built for the
changed copy (PR #4's `w8lib.py auto`, 1698 sites as before): it stops at exactly the same
point (A0A2:D2CE, same registers, ~26M, before the Executive repaints), so marking the code
segment FIXED breaks the start itself and says nothing about the stale return. Case B on the V20
with `WM88X3 /V` (80186 code left native): hourglass, CPU at 4A00:8C75-8C76 from 26M to
51M; not traced.

**Chess reference runs in DOSBox 0.74-3** (386 core, no WM88X3 needed;
chess-dosbox-reference-*.png): the original files in standard mode on CGA give the Chess
board. In real mode, with the protected-only flag cleared in a test copy of COMMDLG (case B)
the screen fills with fragments and the hourglass stays; with the converted COMMDLG (case C)
only the hourglass. So Chess fails in Windows 3.0 real mode even on a 386 with no 8088
rewriting and either COMMDLG: the failure is Chess in real mode, not the 8088 bridge and not
COMMDLG. Which Chess construct fails is not established (the ENTER-prolog frames above remain
the candidate).

## Replacement COMMDLG.DLL and 80186 coverage runs

Runtime for this section: `wip/vbrun100-realmode` at 1e039f6 (notes 86bfb13). The Tic Tac Drop
8088 runs used the COMMDLG of 1d937b0 with a since-dropped 70-byte directory buffer (8441
bytes; 1e039f6 builds 8403 bytes and adds selecting the name box after a directory change).

`wip/vbrun100-realmode` now has `vbrun/commdlg/`: a COMMDLG.DLL written for Windows 3.0 real
mode in 8086 assembly (nasm `cpu 8086`), about 8.4 KB on disk (one fixed 5 KB code segment, 2 KB
data, 2 KB local heap), in place of the converted Microsoft DLL (89 KB, 64 KB of code in eight
discardable segments). It covers GetOpenFileName/GetSaveFileName, ChooseColor (16 basic
colours), ChooseFont, PrintDlg (printer from WIN.INI, copies, DEVNAMES, DC/IC),
CommDlgExtendedError, GetFileTitle and hooks; FindText/ReplaceText return failure; no custom
templates, custom colours, DEVMODE or page ranges. `vbrun/build.sh` uses it unless
`COMMDLG=convert`. Microsoft's file is not modified or shipped.

| run | result | screenshots |
| --- | --- | --- |
| CDTEST.EXE (test program, opens every dialog), V20, real mode, CGA | Open: c:\ -> windows\system -> c:\windows typed into the name box; Color (result 00008000), Font (Helv, Bold, 20 pt, lfHeight -13, weight 700), PrintDlg with no printer: FALSE, error 1008; Save As | commdlg-replacement-cdtest-v20.png |
| Tic Tac Drop as shell, Hercules, **8088** | Game > Save As shows the dialog with the game's file type; Escape | tictacdrop-hercules-shell-saveas-replacement-top-converted-bottom-8088.png (top) |
| same with the converted COMMDLG, 8088 | 60M instructions after the key no dialog on screen yet; after the Escape the game is minimized | same file (bottom) |
| original files, DOSBox standard mode, Hercules | Save As, Escape: the game minimizes itself, so the minimized window above is the game's own reaction to Cancel | tictacdrop-dosbox-reference-original-std-herc-saveas-cancel.png |

Memory on the 8088 run (global arena walked in 1 MB dumps; same disk except COMMDLG):
game window idle, the replacement holds 9.3 KB (code and data, both fixed); the converted
COMMDLG holds 4.4 KB (its data segment; all code discarded). So while no dialog is open the
replacement costs about 5 KB more. While a dialog is open the converted DLL must bring in
discardable code segments of 2.9 to 23 KB each; that was not measured (its dialog had not
appeared at the dump). Free memory at the dumps (14 to 50 KB) moves with VBRUN's discardable
segments and does not compare the two.

Chess in DOSBox real mode with the replacement: hourglass only, as with the converted COMMDLG
(Chess section above); the Chess failure is unchanged.

`vbrun/rig/coverage.sh` runs a game as the shell on the V20 core with every executed 80186
opcode reported (`MARTY_W186=1`) and maps each to module:segment:offset. With the current
build, Jigsawed (About, Open, scramble, Fast Solve, menus), Go Figure (menus, New Game, Options,
Skill), Tic Tac Drop (Hercules; menus, New Game), RattleRace (start, play, menus), Rodent's
Revenge (start, arrow keys, menus) and CDTEST with the replacement executed none. These cover
the scripted steps only, not whole games.

DOSBox note: DOSBox's DOS accepts `CD *.*` on a FAT image (checked at its prompt) and USER's
DlgDirList tries such a change, so in DOSBox the file dialogs' directory line grows
(`c:\windows\*.*\*.*`). MS-DOS on MartyPC refuses it and the line stays right. Directory
navigation was therefore checked on MartyPC.

## Tic Tac Drop beside MS-DOS Executive (memory)

Runtime: `wip/vbrun100-realmode` 13fd86d (notes 4a85196) against 86bfb13. Hercules, game started with
`WIN /R C:\GAME\TICTACDP.EXE` beside MS-DOS Executive. MartyPC only.

| run | 86bfb13 | 13fd86d |
| --- | --- | --- |
| V20, first launch (no input; same result each run) | "Property or control 'Label2' not found" at 52.7M | game window by 300M |
| 8088: first launch, Alt+F4, File > Run the game again | first launch fine; second launch "Label2" error | second launch: window, Game menu |

Screenshot: tictacdrop-beside-executive-herc-before-left-after-right.png (top V20, bottom
8088 second launch; left 86bfb13, right 13fd86d).

Cause, as far as traced: memory. Between the last name lookup and the error the PC samples
(every 2000 instructions) are almost all KERNEL heap code and disk reads, i.e. segments being
discarded and reloaded; 10 KB free at the error, largest block 6.3 KB. The failing allocation
itself was not identified. An opt-in pass (CTXMIRROR) also made the V20 run pass, but the trace
showed its store wrote a value already there, so that was a layout difference and it was not
adopted.

Change: CMDIALOG.VBX declares a 16 KB local heap that KERNEL adds to its data segment (FIXED
after conversion), but it imports no local-heap function and its heap is never initialized
(DS:6 stays 0; the 16 KB stay zero in every dump, also with Save As open). The converter now
drops such heaps (`HEAPTRIM`, default for controls: CMDIALOG 16 KB, GAUGE and THREED 1 KB each).
The replacement COMMDLG's code is now discardable (heap 512 bytes). Resident with the game
idle: CMDIALOG 3.2 KB (was 19.6 KB), COMMDLG 2.7 KB (was 9.3 KB).

Checked with 13fd86d: Tic Tac Drop Save and Open in DOSBox real mode (file saved and listed);
CDTEST on V20 with the discardable COMMDLG (all dialogs, no 80186 opcode executed); Go Figure!
beside the Executive (uses GAUGE and THREED): 8088, Game menu, F2 deals a puzzle (digits, target, timer and level gauge running),
Alt+F4, End Session to the DOS prompt (gofigure-beside-executive-heaptrim-8088.png).

## Tests

`python3 -m pytest vbrun/tests`: 107 passed; `python3 vbrun/tests/stubtest.py`: 69 passed, including three `CtxMirror` tests. `python3 vbrun/tests/test_tools.py`: 91 tests
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
