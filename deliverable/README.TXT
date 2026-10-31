WM88 BRIDGE - run the ORIGINAL Windows 3.1 WINMINE.EXE on Windows 3.0
=====================================================================
Meta Global AI Developer Hackathon - engineering-agent brief solution.
The original, unmodified WINMINE.EXE runs and plays on Windows 3.0 in
real mode. WINMINE.EXE itself is never changed - not on disk, not in
the copy you supply. All adaptation happens around it.

WHAT YOU SUPPLY
---------------
* A PC (real or emulated) with DOS and Windows 3.0 installed and
  working in real mode (WIN /R). VGA graphics in the reference setup.
* Your own unmodified copy of WINMINE.EXE from Windows 3.1.
  Reference specimen used during development:
    size   27,776 bytes
    SHA-256 633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b
  If your file's hash differs, you have a different build; the TSR
  detects this at load time and refuses to patch (it will not touch an
  unrecognised binary).

WHAT WE SHIP (this folder)
--------------------------
* WM88TSR.COM  - DOS terminate-and-stay-resident translation layer.
* SHELL.DLL    - tiny (361-byte) NE DLL providing SHELL.22 ShellAbout,
                 which Windows 3.0 lacks (Windows 3.0 has no SHELL.DLL).
* INSTALL.BAT  - copies SHELL.DLL into C:\WINDOWS\SYSTEM (+ backup).
* WM88.BAT     - one-command launcher (installs the TSR, starts the game).
* dosbox-wm88.conf - DOSBox-X fixture config for modern hosts.

No Python, no compiler, no toolchain is needed to use any of this.

SETUP (real DOS machine)
------------------------
1. Copy the contents of this folder to a floppy or a DOS directory.
2. Run INSTALL.BAT from that directory. It puts SHELL.DLL in
   C:\WINDOWS\SYSTEM and the WM88 files in C:\WINDOWS.
3. Copy your unmodified WINMINE.EXE into C:\WINDOWS.
4. CD \WINDOWS, then run WM88.BAT.
   (Equivalent manual steps: WM88TSR.COM once per DOS session, then
   WIN /R, then launch WINMINE.EXE by any normal means.)
5. Play Minesweeper.

SETUP (DOSBox-X fixture)
------------------------
Build a folder containing your Windows 3.0 installation plus the three
copies described above, point dosbox-wm88.conf's mount at it, and run
dosbox-x -conf dosbox-wm88.conf. Windows itself boots with the game
already open.

WHAT WAS WRONG AND WHAT WE CHANGE (full disclosure)
---------------------------------------------------
The 3.1 binary makes four demands a stock Windows 3.0 / 8088 system
cannot meet. The bridge addresses each one WITHOUT modifying the file:

1. Expected-version stamp. The NE header says "needs Windows 3.10";
   Windows 3.0 refuses it. WM88TSR intercepts DOS file reads of
   WINMINE.EXE and flips those two bytes (3.10 -> 3.00) in the read
   buffer only. The disk file is never written.
2. 80186+ instructions. The code uses PUSH imm, IMUL imm, and
   SHL/SHR/SAR reg,imm8 - illegal on an 8088. All 449 such sites (plus
   6 sites where a 16-bit relocation overlaps a push immediate) are
   rewritten in the read buffer to INT F8h / INT 3h traps, and a
   resident handler emulates each instruction exactly - result,
   flags (merge mask 08C5h, unaffected bits preserved), stack effect
   and register behaviour verified by DOS test suites (TEST88.COM,
   RTEST2.COM, T88B.COM, all passing). Discarded segments are re-read
   from disk, hence automatically re-patched. The TSR self-verifies
   the target before it hooks anything: on every open of a file named
   WINMINE.EXE it checks the exact size (27,776 bytes) and a full
   CRC-32 of the contents, and only then tracks the handle; an
   unrecognised file is left completely alone. Tracked handles are
   keyed by (handle, owning PSP) and dropped when the owning process
   exits, so a recycled DOS handle can never inherit the patch. The
   INT 3h trap additionally verifies the surrounding instruction
   bytes in memory before emulating, and the INT F8h lookup is
   range-checked, so traps from unrelated code are chained to the
   previous handler or counted, never mis-emulated.
3. Missing library. WINMINE imports ShellAbout from module SHELL,
   ordinal 22. Windows 3.0 has no SHELL.DLL, so we ship a 361-byte
   replacement DLL exporting exactly that entry (plus the module name
   and WEP). Everything else WINMINE imports (KERNEL, USER, GDI, and
   SOUND ordinals 1..18) resolves to genuine Windows 3.0 components -
   module SOUND is provided by the stock SOUND.DRV sound driver.
4. Nothing else. No Windows component is patched, hooked or replaced:
   KERNEL.EXE, USER.EXE, GDI.EXE, drivers - all stock.

SIMULATED vs REAL - read this
-----------------------------
REAL (untouched Microsoft code doing the work): all of Windows, the
loader, USER/GDI, the sound driver, and 100% of the game logic.
Minesweeper's board logic, mine placement, flood fill, timer, flag
and question-mark handling, win/loss detection, best-times table and
WINMINE.INI settings persistence all execute in the original binary,
proven end-to-end (see development evidence: a fully logically-solved
win with the name "MUSE" recorded in WINMINE.INI, losses with all ten
mines exposed, restarts via F2 and Game->New).
SIMULATED (ours, clearly): only ShellAbout. Our shim forwards the
caller-supplied strings to USER's MessageBox, so Help -> About shows a
plain dialog with the app's name and its "by Robert Donner and Curt
Johnson" line instead of the richer genuine 3.1 About box. That one
dialog is a behavioural stub; no game API is stubbed.

One development note: an early defect in our shim - a truncated NE
resource table (2 bytes instead of the required 4: shift word +
terminator) - made KERNEL corrupt its global heap while loading it.
That was our bug, in our DLL, found by bisecting against the genuine
DLL and fixed at the correct layer. It never involved WINMINE.EXE.

CPU HONESTY
-----------
The real target is an 8088 (Tandy 1000 EX, 7.16 MHz, 640 KB). All
emulated instructions are executed by our handler, so CPU correctness
on an 8088 is a matter of the handler, which was validated at the DOS
level on exact flag/stack/register semantics. However: the full
Windows sessions above were driven in DOSBox-X with cputype=286,
because DOSBox-X's 8086 core hangs even a completely stock Windows 3.0
(confirmed with unmodified boot disks - an emulator limitation, not a
property of this bridge).

The literal-8088 question was then bisected on two more, independent
emulators. PCjs: the identical XT machine/BIOS/disk with ONLY the CPU
model swapped from 8088 to 80286 boots Windows 3.0 to Program Manager;
the 8088 model dies in real-mode KERNEL startup. 86Box: stock Windows
3.0 on an XT/8088 (4.77 MHz, EGA) shows the splash, then wedges on a
black screen with no disk I/O and interrupts dead (keyboard type, DOS
drivers and mouse presence each bisected out); the SAME disk image on
an XT Model 286 (80286) boots to Program Manager. Windows 3.0 ran on
real 8088 hardware, so this is an emulator 8088-core fidelity gap in
KERNEL startup, reproduced independently in PCjs and 86Box - not the
disk, the Windows install, or this bridge. Literal-8088 end-to-end
proof therefore still awaits physical hardware: a real Tandy 1000 EX
has NOT been run, and nothing here claims it.
Performance in the fixture (DOSBox-X, 10,000 fixed cycles): DOS boot
to playable Minesweeper window in about 2.3 s wall clock; game is
fully responsive, 1 Hz timer exact. On a real 7.16 MHz 8088 expect
noticeably slower flood-fill redraws (each emulated shift costs a
trap); functional, not yet measured.

MEMORY FOOTPRINT
----------------
WM88TSR.COM: 12,316 bytes on disk, about 11 KB resident. SHELL.DLL:
361 bytes. No other resident cost.

FILES AND HASHES
----------------
WM88TSR.COM  SHA-256 c04950d38ca03a209a898e16029260211e0b538c65ee3a99f3ac90e285c469f7
SHELL.DLL    SHA-256 2d7532ae8ac73b957b5fb423449168c7b8f976b150155a42ac37d4b0139ddd1b
