# Follow-up of the eleven remaining Entertainment Pack entries

These are follow-up execution results for the [44-entry audit](WEP-CLEAN-8088.md), not an all-games compatibility claim. All eleven entries received further investigation. The verified total remains **33/44**: the other eleven have the failures or partial results below. Maxwell's Maniac is the additional verified game from this resumed work.

## Environment and edition identity

MartyPC `05c0d088e84ad6bbfac9b3f0d051e7eadefd9f44`, stock **Intel8088** CPU, 640 KiB conventional memory, XT-IDE, Windows 3.0 real mode. CGA uses the stock Windows driver. VGA uses VGA88 from `427ff8db22fdb60b59d40ab847fd513e36bc2a0f`. The headless frontend accepts input and captures the guest framebuffer; no CPU instruction implementation was changed. Native V20 controls mentioned below are diagnostics and do not count toward the 8088 result.

Original game files were taken from the supplied editions. File lengths identify the tested copies without treating different editions as one test:

| Edition | Executable | Bytes |
| --- | --- | ---: |
| Pack 2 | JIGSAWED.EXE | 66904 |
| Pack 2 | RATTLER.EXE | 70226 |
| Pack 2 | RODENT.EXE | 56424 |
| Pack 4 | BLAKJAK.EXE | 136768 |
| Pack 4 | CHESS.EXE | 232656 |
| Pack 4 | CHIPS.EXE | 267776 |
| Pack 4 | GOFIGURE.EXE | 70663 |
| Pack 4 | TICTACDP.EXE | 120864 |
| Best of | BLAKJAK.EXE | 136768 |
| Best of | CHIPS.EXE | 267776 |
| Best of | RODENT.EXE | 56424 |

Pack 4/Best of Blackjack and Chips, and Pack 2/Best of Rodent, were compared directly and are byte-identical. Their execution results are nevertheless separate edition launches.

## Observations, input and exit attempts

| Edition / game | Further execution result | Exit attempt and classification | Evidence |
| --- | --- | --- | --- |
| Pack 2 Jigsawed | Current converted runtime, stock CGA, game as shell: reached the game frame and scrollbars. Enter, Ctrl+O and Game-menu input did not produce an inspected open dialog or puzzle. A 640-by-200-or-smaller control bitmap was installed as C:\PUZ.BMP. | Alt+F4 followed by 250 million further cycles did not establish return to DOS or Executive. **Partial; no puzzle interaction or clean exit verified.** | [game frame](../evidence/wep-resume/pack2-jigsaw-loaded.png), [exit attempt](../evidence/wep-resume/pack2-jigsaw-exit-attempt.png) |
| Pack 2 RattleRace | Current converted runtime, VGA, game as shell: F2 started Level 1. Held direction keys changed the green snake's path near the top of the playfield. Pause overlays appeared during the sequence; this is not proof of a completed level. VGA removes the CGA viewport clipping. | After Alt+F4/resume and Game-menu input, the game window disappeared into a gray Windows screen. Additional execution and Ctrl+Esc did not establish a responsive recovery to DOS/Executive. A separate launch beside Executive corrupted CPU state and halted. **Input observed; clean exit unverified.** | [started](../evidence/wep-resume/pack2-rattler-started.png), [direction response](../evidence/wep-resume/pack2-rattler-direction.png), [exit attempt](../evidence/wep-resume/pack2-rattler-exit-attempt.png) |
| Pack 2 Rodent's Revenge | Current converted runtime, VGA, game as shell: F2 and held numeric-keypad 6 moved the mouse right and pushed a row of blocks out from the central block field. | Alt+F4 closed the game window. Additional execution and Ctrl+Esc left a gray Windows screen; no responsive DOS/Executive recovery was verified. A separate Executive configuration also failed. **Gameplay input observed; clean exit unverified.** | [before](../evidence/wep-resume/pack2-rodent-started.png), [pushed blocks](../evidence/wep-resume/pack2-rodent-push.png), [exit attempt](../evidence/wep-resume/pack2-rodent-exit-attempt.png) |
| Pack 4 Blackjack | With only the generated mode-check bypass removed, the original game explicitly requires Standard or Enhanced Mode Windows. The bypassed version still corrupts the timer vector; details below. | Enter dismissed the original refusal and returned to Executive. **Startup refusal, not gameplay.** | [original refusal](../evidence/wep-resume/pack4-blackjack-original-mode-refusal.png), [dismissed](../evidence/wep-resume/pack4-blackjack-refusal-exit.png) |
| Pack 4 Chess | The host-tested zero-nesting ENTER handler does not establish a working game. The earlier original-file run failed after opening-book loading. A private alternative replacing ENTER with inline 8086 sequences was rejected by the loader; it is not a fix. A fresh original-file follow-up also included the COMMDLG module's protected-mode metadata patch; it still escaped into invalid CPU state (CS=CA00, BP=FFFF) without a usable game window. | Alt+F4 after the corrupted follow-up did not establish clean recovery. **No played chess move or clean game exit verified.** | [earlier failure](../evidence/wep-clean-8088/pack4-chess-enter-runaway.png), [fresh follow-up](../evidence/wep-resume/pack4-chess-original-runaway.png), [exit attempt](../evidence/wep-resume/pack4-chess-original-exit-attempt.png) |
| Pack 4 Chip's Challenge | Reduced the private patch library substantially; the loader still reported insufficient memory. A private dump during a failure showed roughly 188 KB free, with a roughly 181 KB largest block. Clearing fast-load metadata did not fix it. Lossless recompression of the two large RLE4 bitmap resources below 64 KB also did not fix it. | Enter dismissed the error and returned to Executive. As-shell trials did not establish gameplay. **Loader failure; the precise allocation/resource failure is not isolated.** | [memory error](../evidence/wep-clean-8088/p4-chips-limitation.png), [dismissed](../evidence/wep-resume/pack4-chips-error-dismissed.png) |
| Pack 4 Go Figure! | Retried with converted VBRUN100 and translated GAUGE/THREED controls, without WM88X3. The application remained at a blank/hourglass screen after 2.2 billion cycles. Samples were concentrated in KERNEL's memory movement/compaction routines. | Alt+F4 plus 200 million cycles did not recover a usable game or Executive. **Startup failure with converted dependencies too.** | [converted controls](../evidence/wep-resume/pack4-gofigure-converted.png), [exit attempt](../evidence/wep-resume/pack4-gofigure-exit-attempt.png) |
| Pack 4 Tic Tac Drop | Converted runtime and controls first produced an explicit CMDIALOG.VBX load error, then “Unexpected error; quitting.” COMMDLG itself has the protected-only flag; a further private conversion clearing that flag progressed to a blank/hourglass screen. | The first quitting path escaped into invalid CPU state. The COMMDLG follow-up remained unusable after more than 2.1 billion cycles and an Alt+F4 attempt. **Dependency/startup failure; no game interaction.** | [control error](../evidence/wep-resume/pack4-tictacdrop-control-error.png), [quitting error](../evidence/wep-resume/pack4-tictacdrop-quitting-error.png), [COMMDLG follow-up](../evidence/wep-resume/pack4-tictacdrop-commdlg-converted.png) |
| Best of Blackjack | Independently reproduced the original Standard/Enhanced Mode refusal using the Best of executable and helpers. | Enter returned to Executive. **Startup refusal, not gameplay.** | [refusal](../evidence/wep-resume/bestof-blackjack-original-mode-refusal.png), [dismissed](../evidence/wep-resume/bestof-blackjack-refusal-exit.png) |
| Best of Chip's Challenge | Fresh original Best of files, matching module library, WM88X3, VGA: independently reproduced “Not enough memory to run C:\GAME\CHIPS.EXE.” | Enter dismissed the error; Executive remained visible. **Loader failure.** | [error](../evidence/wep-resume/bestof-chips-memory-error.png), [dismissed](../evidence/wep-resume/bestof-chips-error-dismissed.png) |
| Best of Rodent's Revenge | Independent Best of launch with converted runtime and VGA: F2 and held keypad 6 moved the mouse and pushed the central row right. | Alt+F4 closed the window, but gray-screen recovery and a separate Executive trial did not establish clean exit. **Gameplay input observed; clean exit unverified.** | [before](../evidence/wep-resume/bestof-rodent-started.png), [pushed blocks](../evidence/wep-resume/bestof-rodent-push.png), [exit attempt](../evidence/wep-resume/bestof-rodent-exit-attempt.png) |

The gray screen after closing a game used as shell does not by itself prove a crash: sampled execution includes the kernel's scheduler idle path. It also does not meet this audit's stronger verified-exit evidence. These three rows therefore remain partial. The separate Executive attempts do not demonstrate the same usable input sequence and cannot substitute for a successful exit test.

## Blackjack diagnosis

The original mode-check result is independent of the generated bridge bypass. With the bypass enabled, instruction/vector tracing caught KERNEL.OpenFile writing error code 2 through an invalid OFSTRUCT pointer at physical address 0x72. That changes INT 1Ch from F000:FF53 to 0002:FF53; the next timer interrupt escapes into the wrong code. No unpatched 80186 candidate was detected before that write in the audited attempt.

The corruption also reproduced with the game as shell and approximately 100 KB free. A V20 control failed as well, including a private gate-only patch without the resident TSR. Clearing fast-load fields did not solve it. Replacing one private WinMain instance argument with DS did not produce a game. These experiments are negative controls, not a compatibility patch. The WEP4UTIL instruction-site and Blackjack/helper loader-read checks passed separately.

## Converted dependency trials

The normal current `vbrun/build.sh` outputs were rebuilt from the supplied originals: VBRUN100.DLL 298976 bytes, FIELD100.DLL 14992, WEPUTIL.DLL 20544. The original rig builder installed converted runtime DLLs in SYSTEM, with no duplicate copies beside the games and no resident WM88X3. Tests beside Executive and as shell were kept separate.

Private control conversions used the existing converter's 8088 instruction pass. THREED's data segment 6 and CMDIALOG's data segment 7 were fixed for control-model pointers. GAUGE used fixed segments and preserved internal-ordinal selector references; COMMDLG similarly preserved internal-ordinal references while clearing its protected-only metadata. The normal movable-selector conversion otherwise raises an IndexError on these ordinal references. These special private settings are not a released or verified generic control conversion recipe. [Conversion output](../evidence/wep-resume/converted-controls-trials.txt) and [diagnostic state](../evidence/wep-resume/follow-up-state.txt) are retained. Instruction checks for THREED, GAUGE, CMDIALOG and the private COMMDLG output reported OK, which does not prove their Windows API or lifetime behavior.

An older reference VBRUN/FIELD pair was also tried with Jigsawed. It did not yield a usable puzzle in this rig, so the current failure is not established as a new converter regression. Samples from the current Jigsawed and Go Figure failures cluster around KERNEL:20B9/20F6/211E and nearby memory management routines. That is an observation, not an isolated cause.

## Scope of the result

The audit covers launch attempts and brief interaction where a usable game can be reached; complete playthroughs were not requested. All 44 edition entries have actual execution evidence, and the remaining eleven now have the additional investigations above. **Compatibility remains incomplete.** Failed dependencies, loader failures, unusable startup, and unverified exits remain visible rather than being counted as passes. Microsoft files, private disks, memory dumps and ROMs are excluded from this repository.
