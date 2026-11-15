# Clean Entertainment Pack interaction tests on MartyPC 8088

This continues the preliminary [first-pass attempts](WEP-MARTY-8088.md). Results below are restricted to the uploaded edition and the described interactions. They do not claim complete game playthroughs or physical hardware validation.

## Configuration

MartyPC source `05c0d088e84ad6bbfac9b3f0d051e7eadefd9f44`, IBM XT 8088 core, 640 KiB conventional RAM, CGA, XT-IDE and Windows 3.0 real mode beside MS-DOS Executive. The headless runner was changed to accept stepwise commands, including mouse movement/button transitions and keyboard sequences, and to report cycle/instruction counters and CPU errors after each command. Captures are actual emulator front-framebuffer dumps converted to PNG, not desktop screenshots. The [local frontend patch](../emulator/martypc/headless-wep-test.patch) applies to that MartyPC revision; it is a test harness, not a change to the 86TO88 bridge.

Each game disk starts from the private Windows fixture. GAME is cleared of previous executables, only the selected original game executable is copied in, and its edition's original DLLs and resources are copied beside it. Original VBRUN100/FIELD100/WEPUTIL copies are removed from SYSTEM, and no converted VB runtime is installed in these WM88X3-only tests. Module libraries were generated from the same original pack files. The only resident bridge is WM88X3. No proprietary executable, ROM, or disk image is included here.

## Verified interaction and exit

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 1 Pegged | Dragged the central peg horizontally over its right neighbor into the empty hole two positions to the right. After release and moving the cursor away, both original holes were empty and the destination held the moved peg. This is one legal move, not a completed puzzle. | Alt+F4 returned to MS-DOS Executive. No CPU error was reported. | [before](../evidence/wep-clean-8088/pack1-pegged-before.png), [after move](../evidence/wep-clean-8088/pack1-pegged-move.png), [exit](../evidence/wep-clean-8088/pack1-pegged-exit.png) |

Pegged was launched through Executive's Run dialog. The emulator booted for 300 million emulated cycles, then used short runs between typed keys. Once the board appeared, mouse deltas reset the cursor to the top left and placed it on the central peg. A left-button press, horizontal movement while held, and release performed the move; the cursor was then moved off the board. The legal move and exit were individually inspected rather than inferred from a fixed-time startup capture. Final counters: 423,046,507 emulated cycles, 21,819,016 instructions; reported CPU error: none. These are execution counters, not performance measurements.

The previous mixed-fixture Pegged mouse attempts produced black frames. This clean attempt did not reproduce that behavior, but changing the disk setup and input timing together does not isolate the original cause.

## Module lookup bug found and fixed

The first clean WinMine and TetraVex attempts still failed. Instruction tracing found execution had escaped into segment 0000; inspecting the private memory dump showed original 80186 instructions were still present, and the TSR had loaded no module tables. This was not merely a long startup wait.

`build_lpath` scanned backward from the end of the opened path to find the basename. After that scan, CX held the directory-prefix length, but the forward filename-copy loop used it as the basename length. With a short directory such as `C:\GAME`, the counter could expire before the extension was processed. The resulting library filename was incomplete, so the game read was not patched. A bare filename also failed. The fix converts the remaining prefix length to the actual basename length before copying. The rebuilt WM88X3 is 3,835 bytes (previously 3,826); the module format is unchanged.

The regression uses a fresh Unicorn instance for every directory prefix so a table cached by a previous open cannot hide the failure. Before the fix, the `C:\GAME\WINMINE.EXE` test found 909 mismatched bytes in its code-segment read. After the fix, `C:\G`, `C:\GAME`, a bare filename, and `C:\WINDOWS\SYSTEM` all produce the expected patched reads for WINMINE and ABOUTWEP. Loader-read comparisons now assert on mismatch rather than only printing a warning. Pack 3 TetraVex/WEPUTIL reads and the install-command tests also pass. [Before log](../evidence/wep-clean-8088/short-path-before.txt), [path regression log](../evidence/wep-clean-8088/short-path-after.txt), [install log](../evidence/wep-clean-8088/install-after.txt), [Pack 3 read log](../evidence/wep-clean-8088/pack3-read-after.txt).

The fixture also contained a different WINMINE.EXE in WINDOWS. The follow-up removed it and explicitly launched `C:\GAME\WINMINE.EXE`; the directory-counter bug was reproduced even with that exact path before the bridge fix. This avoids confusing executable selection with the confirmed path-building defect.

## After the bridge fix

These runs still use the stock emulated Intel 8088 CPU core and CGA, with the rebuilt WM88X3 and original files matching their generated module libraries. No converted VB helpers are installed. Final frames were inspected for each interaction and exit.

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 1 WinMine | Clicking the top-left covered square revealed the number 1 and started the timer. Cursor moved away for the final capture. | Alt+F4 returned to Executive; no reported CPU error. | [before](../evidence/wep-clean-8088/pack1-winmine-before.png), [revealed square](../evidence/wep-clean-8088/pack1-winmine-reveal.png), [exit](../evidence/wep-clean-8088/pack1-winmine-exit.png) |
| Pack 3 TetraVex | Dragged the top-left tile from the right tray into the top-left empty board square; the source tray position became empty. | Alt+F4 returned to Executive; no reported CPU error. | [before](../evidence/wep-clean-8088/pack3-tetravex-before.png), [tile moved](../evidence/wep-clean-8088/pack3-tetravex-move.png), [exit](../evidence/wep-clean-8088/pack3-tetravex-exit.png) |

Pegged's legal move and exit were also repeated successfully from another fresh boot before the bridge fix: [repeated move](../evidence/wep-clean-8088/pack1-pegged-repeat-move.png), [repeated exit](../evidence/wep-clean-8088/pack1-pegged-repeat-exit.png). None of these observations claims a completed game or validates a different pack's executable.

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 1 TicTactics | A click placed a playing piece in the top board plane. Lower planes extend beyond the CGA viewport. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack1-tictactics-before.png), [piece placed](../evidence/wep-clean-8088/pack1-tictactics-move.png), [exit](../evidence/wep-clean-8088/pack1-tictactics-exit.png) |
| Pack 4 JezzBall | A click built a wall, cleared the right part of the field and increased the score from 0 to 2,100. The bottom of the field is clipped on CGA. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack4-jezzball-before.png), [wall and score](../evidence/wep-clean-8088/pack4-jezzball-move.png), [exit](../evidence/wep-clean-8088/pack4-jezzball-exit.png) |

Pack 1 Taipei reached a dealt board after F2 with the fixed bridge, but no tile pair or clean exit was verified in this CGA run. Its menu and some of the board extend beyond the viewport; it remains partial.

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 3 LifeGenesis | A mouse click added a live cell; the cell count changed from 0 to 1. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack3-lifegen-before.png), [live cell](../evidence/wep-clean-8088/pack3-lifegen-move.png), [exit](../evidence/wep-clean-8088/pack3-lifegen-exit.png) |
| Pack 3 SkiFree | The down key started skiing. Distance reached 953 m, speed 13 m/s, and the slope/character moved. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack3-skifree-before.png), [skiing](../evidence/wep-clean-8088/pack3-skifree-move.png), [exit](../evidence/wep-clean-8088/pack3-skifree-exit.png) |
| Pack 2 Pipe Dream | A mouse click placed a pipe in the play field and advanced the pipe queue. The lower field is clipped on CGA. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack2-pipe-before.png), [pipe placed](../evidence/wep-clean-8088/pack2-pipe-move.png), [exit](../evidence/wep-clean-8088/pack2-pipe-exit.png) |

## VGA follow-up for a game that rejects CGA

Pack 1 Tetris 2.00 runs with the existing source-built VGA88.DRV from `astrobleem/windows-3-vga-8088` at revision `427ff8db22fdb60b59d40ab847fd513e36bc2a0f`. This remains MartyPC's stock Intel 8088 CPU core, 640 KiB and Windows 3.0 real mode. The video configuration is VGA plus the bundled open Bochs VGA ROM; original Windows 3.0 VGA fonts and the real-mode grabber are installed. The headless frontend must be built with `--features marty_frontend_common/vga` and configured with the `ibm_vga` overlay. CGA results above use the CGA driver instead.

VGA framebuffers are native 32-bit RGBA, so the capture helper exports their RGB bytes directly; CGA uses its 16-color palette. The Tetris PNGs crop only the hardware-defined active VGA aperture at (96,32), 640x480; the complete raw framebuffer includes blanking/debug margins. They are not generated or reconstructed game scenes.

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 1 Tetris | Left-arrow input shifted the falling T piece left. Space dropped it into the stack; score increased from 108 to 142. | In a fresh repeat, Alt+F4 opened the confirmation; Enter accepted Yes and returned to Executive. | [before](../evidence/wep-clean-8088/pack1-tetris-vga-before.png), [moved left](../evidence/wep-clean-8088/pack1-tetris-vga-left.png), [drop and score](../evidence/wep-clean-8088/pack1-tetris-vga-drop.png), [confirmed exit](../evidence/wep-clean-8088/pack1-tetris-vga-exit.png) |

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 2 FreeCell (VGA) | Moved the ten of diamonds from a tableau column to the first free cell. The exposed ace of hearts also moved automatically to a foundation; Cards Left changed from 52 to 51. | Alt+F4 displayed “You resign”; Enter dismissed it and returned to Executive. | [before](../evidence/wep-clean-8088/pack2-freecell-vga-before.png), [card moved](../evidence/wep-clean-8088/pack2-freecell-vga-move.png), [exit](../evidence/wep-clean-8088/pack2-freecell-vga-exit.png) |
| Pack 2 Tut's Tomb (VGA) | Clicking the stock dealt three face-up waste cards. This is a stock draw during play, not a new deal; no tableau pair was removed. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack2-tutstomb-vga-before.png), [stock drawn](../evidence/wep-clean-8088/pack2-tutstomb-vga-move.png), [exit](../evidence/wep-clean-8088/pack2-tutstomb-vga-exit.png) |

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 3 Klotski (CGA) | Selected Level 1 / Daisy, entered a test name, and dragged a small block downward into an empty bottom-center square. The old square became empty. | A fresh repeat used Game > Exit and returned to Executive. The earlier Alt+F4 attempt did not close the game. | [before](../evidence/wep-clean-8088/pack3-klotski-before.png), [block moved](../evidence/wep-clean-8088/pack3-klotski-move.png), [menu exit](../evidence/wep-clean-8088/pack3-klotski-exit.png) |

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 3 TriPeaks (VGA) | Played the exposed three of diamonds onto the waste four of diamonds. The tableau card disappeared, the waste became three of diamonds, and Won increased from $0 to $1. | Alt+F4 opened its penalty confirmation; accepting Yes returned to Executive. | [before](../evidence/wep-clean-8088/pack3-tripeaks-vga-before.png), [card played](../evidence/wep-clean-8088/pack3-tripeaks-vga-move.png), [confirmed exit](../evidence/wep-clean-8088/pack3-tripeaks-vga-exit.png) |

## Independent Best of edition checks

The Best of executables were launched separately with that edition's original helpers and generated module library. A result from an earlier pack was not reused as its execution result.

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Best of TetraVex (CGA) | Moved the top-left right-tray tile into the top-left empty board square. Its tray position became empty. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-tetravex-before.png), [tile moved](../evidence/wep-clean-8088/bestof-tetravex-move.png), [exit](../evidence/wep-clean-8088/bestof-tetravex-exit.png) |
| Best of SkiFree (CGA) | The down key started skiing; the scene moved and distance reached 979 m at 9 m/s. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-skifree-before.png), [skiing](../evidence/wep-clean-8088/bestof-skifree-move.png), [exit](../evidence/wep-clean-8088/bestof-skifree-exit.png) |
| Best of JezzBall (CGA) | A click completed a vertical wall and increased the score from 0 to 140. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-jezzball-before.png), [wall and score](../evidence/wep-clean-8088/bestof-jezzball-move.png), [exit](../evidence/wep-clean-8088/bestof-jezzball-exit.png) |

| Best of Pipe Dream (VGA) | Placed a curved pipe in an empty upper-left board cell; the pipe queue advanced. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-pipe-vga-before.png), [action](../evidence/wep-clean-8088/bestof-pipe-vga-action.png), [exit](../evidence/wep-clean-8088/bestof-pipe-vga-exit.png) |

| Best of FreeCell (VGA) | Moved the ten of diamonds to the first free cell. An ace moved to its foundation and Cards Left changed from 52 to 51. | Alt+F4 returned to Executive; Enter dismissed the resignation message. | [before](../evidence/wep-clean-8088/bestof-freecell-vga-before.png), [action](../evidence/wep-clean-8088/bestof-freecell-vga-action.png), [exit](../evidence/wep-clean-8088/bestof-freecell-vga-exit.png) |

| Best of Tut's Tomb (VGA) | Drew three face-up waste cards from the stock during play. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-tutstomb-vga-before.png), [action](../evidence/wep-clean-8088/bestof-tutstomb-vga-action.png), [exit](../evidence/wep-clean-8088/bestof-tutstomb-vga-exit.png) |

| Pack 3 Fuji Golf (VGA) | Started a round, activated Backswing/Hit Ball, and registered strokes. The shot counter advanced to fourth shot; distance to cup stayed 460 yards. Ball travel and completion of a hole were not verified. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack3-fujigolf-vga-before.png), [action](../evidence/wep-clean-8088/pack3-fujigolf-vga-action.png), [exit](../evidence/wep-clean-8088/pack3-fujigolf-vga-exit.png) |

| Pack 1 Golf (VGA) | Played the exposed ten of hearts onto the waste nine of diamonds. Its tableau column then exposed the ten of diamonds. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack1-golf-vga-before.png), [move](../evidence/wep-clean-8088/pack1-golf-vga-move.png), [exit](../evidence/wep-clean-8088/pack1-golf-vga-exit.png) |

| Pack 1 Cruel (VGA) | Dragged the two of spades onto the ace-of-spades foundation. The foundation became two of spades and its source exposed the queen of clubs. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/pack1-cruel-vga-before.png), [move](../evidence/wep-clean-8088/pack1-cruel-vga-move.png), [exit](../evidence/wep-clean-8088/pack1-cruel-vga-exit.png) |

| Pack 1 Taipei (VGA) | Requested a hint, then clicked the matching highlighted bamboo pair on the upper-right side. Both tiles disappeared, revealing the tiles below. | Game > Exit returned to Executive. | [before](../evidence/wep-clean-8088/pack1-taipei-vga-before.png), [move](../evidence/wep-clean-8088/pack1-taipei-vga-move.png), [exit](../evidence/wep-clean-8088/pack1-taipei-vga-exit.png) |

| Best of Golf (VGA) | Drew from the stock; the visible waste changed and the stock count decreased from 16 to 15. | Alt+F4 returned to Executive. | [before](../evidence/wep-clean-8088/bestof-golf-vga-before.png), [move](../evidence/wep-clean-8088/bestof-golf-vga-move.png), [exit](../evidence/wep-clean-8088/bestof-golf-vga-exit.png) |

| Best of TriPeaks (VGA) | Drew a card from the stock; Cards Left decreased from 23 to 22 and the waste became seven of hearts. | Alt+F4 returned to Executive; Enter accepted the confirmation. | [before](../evidence/wep-clean-8088/bestof-tripeaks-vga-before.png), [move](../evidence/wep-clean-8088/bestof-tripeaks-vga-move.png), [exit](../evidence/wep-clean-8088/bestof-tripeaks-vga-exit.png) |

| Best of Tetris (VGA) | Sent left-arrow input and a space drop during an active game. The dropped piece joined the stack and score reached 178. | Alt+F4 returned to Executive; Enter accepted the confirmation. | [before](../evidence/wep-clean-8088/bestof-tetris-vga-before.png), [move](../evidence/wep-clean-8088/bestof-tetris-vga-move.png), [exit](../evidence/wep-clean-8088/bestof-tetris-vga-exit.png) |


## Screen-saver operation

These are saver selection, activation, wake and termination checks, not game tests.

| Edition / saver | Observed | Exit | Evidence |
| --- | --- | --- | --- |
| Pack 1 IdleWild (VGA) | Selected Dancing Lines drew colored lines on the black screen; Escape restored its settings window. | Alt+F4 closed IdleWild. | [selection](../evidence/wep-clean-8088/pack1-idlewild-vga-selection.png), [saving](../evidence/wep-clean-8088/pack1-idlewild-vga-saving.png), [awake](../evidence/wep-clean-8088/pack1-idlewild-vga-awake.png), [exit](../evidence/wep-clean-8088/pack1-idlewild-vga-exit.png) |
| Pack 2 IdleWild (VGA) | Selected Bricks overlaid the desktop with its masonry grid; Escape woke the desktop and minimized IdleWild. | Restored the minimized icon, then Options > Exit terminated IdleWild. The initial Alt+F4 targeted Executive; its End Session dialog was cancelled. | [selection](../evidence/wep-clean-8088/pack2-idlewild-vga-selection.png), [saving](../evidence/wep-clean-8088/pack2-idlewild-vga-saving.png), [awake](../evidence/wep-clean-8088/pack2-idlewild-vga-awake.png), [exit](../evidence/wep-clean-8088/pack2-idlewild-vga-exit.png) |
| Pack 3 IdleWild (VGA) | Selected Boat Race animated boats on a black screen; Escape woke the desktop and minimized IdleWild. | Restored the minimized icon, then Options > Exit terminated IdleWild. The initial Alt+F4 targeted Executive; its End Session dialog was cancelled. | [selection](../evidence/wep-clean-8088/pack3-idlewild-vga-selection.png), [saving](../evidence/wep-clean-8088/pack3-idlewild-vga-saving.png), [awake](../evidence/wep-clean-8088/pack3-idlewild-vga-awake.png), [exit](../evidence/wep-clean-8088/pack3-idlewild-vga-exit.png) |


## Partial and failed configurations under investigation

A CPU error of `None` is not proof of valid 8088 execution: later instruction bytes can alias original 8088 instructions and run into unrelated code. These rows are not passes.

| Edition / configuration | Observed limitation | Evidence |
| --- | --- | --- |
| Pack 2 Stones, WM88X3/VGA | Reported stone-style DLLs corrupted or missing. The style DLLs are present beside the executable; this is a loader/runtime failure, not a missing-media conclusion. | [capture](../evidence/wep-clean-8088/stones-fixed-limitation.png) |
| Pack 4 Chips, WM88X3/VGA | Reported insufficient memory to run CHIPS.EXE with 640 KiB beside Executive. | [capture](../evidence/wep-clean-8088/p4-chips-limitation.png) |
| Best of Chips, WM88X3/CGA | Independently reported insufficient memory with 640 KiB beside Executive. | [capture](../evidence/wep-clean-8088/best-chips-limitation.png) |
| Pack 4 Go Figure!, WM88X3/VGA | Produced corrupted text instead of a game window. Original VBRUN100/VBX dependencies were used; the separate converted-runtime route is not validated for this game. | [capture](../evidence/wep-clean-8088/p4-gofigure-limitation.png) |
| Pack 4 Tic Tac Drop, WM88X3/VGA | Produced corrupted text instead of a game window. Original VBRUN100/VBX dependencies were used; CMDIALOG.VBX also has unsupported ES-prefixed memory-IMUL sites. | [capture](../evidence/wep-clean-8088/p4-tictacdp-limitation.png) |
| Pack 2 RattleRace, converted helpers/VGA, no WM88X3 | Stayed on the Executive/hourglass frame and reached CS=FFFF, IP=000F with execution counters no longer advancing. The CGA run had displayed its window and exited, but play was not verified. | [capture](../evidence/wep-clean-8088/rattler-vga-limitation.png) |
| Pack 2 Rodent's Revenge, converted helpers/VGA, no WM88X3 | Displayed the DOS fatal internal stack failure message instead of a playable window. CGA startup and exit succeeded separately; no visible move verified. | [capture](../evidence/wep-clean-8088/rodent-vga-limitation.png) |
| Pack 2 Jigsawed, converted helpers/VGA, no WM88X3 | Produced corrupted text and reached CS=0000 rather than a playable puzzle. The CGA wait also did not establish gameplay. | [capture](../evidence/wep-clean-8088/jigsawed-vga-limitation.png) |


## Additional Best of result

| Edition / game | Interaction observed | Exit | Evidence |
| --- | --- | --- | --- |
| Best of Taipei (VGA) | Requested a hint, then removed the highlighted matching two-character tiles on the right edge. The spaces exposed the tiles below. | Game > Exit returned to Executive. | [before](../evidence/wep-clean-8088/bestof-taipei-vga-before.png), [move](../evidence/wep-clean-8088/bestof-taipei-vga-move.png), [exit](../evidence/wep-clean-8088/bestof-taipei-vga-exit.png) |


## Stones dependency discovery correction

Stones constructs style DLL filenames from `STONE%02u.DLL` and `STONEE%02u.DLL`. The original literal-name scan missed all nine supplied styles, so their protected-mode-only header flags remained set. Discovery now expands the observed two-digit filename formats against DLLs actually present in the extracted pack. This uses the existing header-patch mechanism; no new instruction handler or module format is introduced. The [private-input regression log](../evidence/wep-clean-8088/stones-dependencies.txt) verifies all nine styles are discovered and receive that real-mode header patch. Gameplay is being retested separately.
