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
