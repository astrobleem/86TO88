# VBRUN100 on real-mode Windows 3.0 / 8088 — engineering notes

Working notes for `wip/vbrun100-realmode`. Not user documentation. Newest state first in
each section; the git log has the history.

## Build

    VBW_ORIG=<dir with original VBRUN100.DLL FIELD100.DLL> ./build.sh OUTDIR

Default output is the 8088 build: every reachable 80186 instruction rewritten
(`I186=1`), relocation chains merged (`MERGERELOC=1`), both DLLs pass `nevalid.py`
(segment table, relocations, entries, fast-load area, pushed-return gate) and
`i186.py --check` (no 80186 site left in reachable code). `I186=0` gives the previous
V20/80186-only output.

Heap/placement defaults (see "Memory and startup layouts" below): `VBALLOCFIXED` off,
`VBHEAPSKIP4=1`, `VBHEAPRES2=0x400`, `APPDSLOCK=1` (lock the app DGROUP after the entry
grow; unlocked again at exit), `WRAPFIX=1`, WEPUTIL `I186WEPSEG=1`, no fast-load area.

Diagnostic switches (off by default): `WRAPSTATS=1` (wrapper counters, read with `wstats.py`),
`STRTRACE=1` (string-space grow log on port E9), `RAISECHK=1` (error-reset log on port
E9), `KEEPFASTLOAD=1`.

## Components

* `conv.py` — the converter (segment fixes, wrapper, heap headroom, 80186 rewrite, final
  NE assembly).
* `asm/wrapcore.asm` — real-mode call wrapper (in fixed segment 24). Records the caller of
  every far call from movable code into code that can move memory, and re-derives the
  return segment after the call. Each record slot has its own return trampoline, so a
  return identifies its record exactly.
* `asm/i186.asm` + `i186.py` — 80186 -> 8088 rewrite (see below).
* `nevalid.py` — structural validator, run by `build.sh`.
* `i186test.py` — per-site differential test (Unicorn) of the 80186 rewrite against the
  same conversion without it.
* `rig/` — MartyPC scenarios (`puzzle.sh`, `shell.sh`, `exit.sh`, `app.sh`, `trial.sh`).
  `run.sh` stops only a previous instance of its own binary: it used to `pkill -x martypc`,
  so running `tests/test_tools.py` (which exercises run.sh with a fake binary) killed any
  scenario in progress — that was the "emulator dies after a few minutes" seen on 2026-11-13.
* `emulator/martypc/trace-hooks.patch` — PC samples, XW call watches, dumps, ring trace
  (V20 core); PC samples, dumps and an "80186 opcode executed" report (8088 core).

## 80186 -> 8088 (i186.py)

On an 8088 the 80186 opcodes alias instead of faulting, so every one that can execute has
to be gone. Sites are found by recursive descent, run over the converter's current code so
its appended stubs are covered too. Definite roots: entries, relocation targets (far
calls/jumps, far pointers with a procedure prologue, offset fixups), PUSH CS/CALL targets
and MSC switch tables (exactly the entries the `cmp ax,N` before the jump allows).
Heuristic roots, kept only when their decode agrees with the definite code: MSC far
procedure prologues (reached through tables the runtime builds) and p-code handlers. The
p-code is threaded: the program's p-code holds the handler offsets in segment 2 directly
(JIGSAWED's EXE references 91 of them), and nothing in VBRUN points at them; a handler
follows an unconditional jump and a descriptor word. Calls into the error entries and into
the p-code escape dispatchers (2:48F9..4938, which pop their return address and read
operand bytes behind it) are treated as not returning, so their inline bytes are not
taken for code. The first 8088 run (descent only) hit an unconverted PUSH imm8 at 83:0DDD
in a switch case; the wider coverage is from that. Each site is replaced by code of the
same length:

| original | count (VBRUN/FIELD) | replacement |
| --- | --- | --- |
| PUSH imm16 | 641 / 31 | CALL near to a per-segment trampoline per value (per site if a fixup covers the immediate; the fixup moves into the trampoline) |
| PUSH imm8 | 2096 / 52 | INT 3 + the immediate byte; resident handler in segment 24 |
| SHL/SHR/SAR r,imm8 | 162 / 5 | CALL near to a shared trampoline of n 1-bit shifts |
| ENTER n,0 | 18 / 0 | JMP to PUSH BP / MOV BP,SP / LEA SP,[BP-n] / JMP back |
| LEAVE + RET(F) | 33 / 0 | JMP to MOV SP,BP / POP BP / RETF n; a 2-byte LEAVE+RET(F) moves with the simple instruction before it |
| IMUL r,m,imm | 7 / 1 | JMP to a sequence that saves AX/DX and uses IMUL r/m16 |

The INT 3 handler is installed by the DLL entry point (routed through `init`) and removed
by WEP (routed through `wep`) if the vector still points at it; an INT 3 that is not a
rewritten site (no CC before the return address) goes to the previous handler.

Verification: `tests/test_i186.py` (each form against the native instruction, random
states, corner cases); `i186test.py` on the real DLLs (VBRUN 2974, FIELD100 89, WEPUTIL
223 sites, zero differences; it detects deliberately broken trampolines/handler);
`i186.py --check`. The table above counts the first pass; the totals include the sites
found later in converter stubs, post-jump code and handlers without a descriptor word.

Coverage evidence (observed, not proven): the V20 core with `MARTY_W186=1` reports every
80186-only opcode executed outside the ROM BIOS. On the final build the full JIGSAWED
workflow (launch, open bitmap, scramble, hint, solve, rescramble) reported none. Earlier
runs of the same check found the misses fixed in 914c30a, 2af748d and e1758a0 (a switch
case, class registration in 75:019C, p-code handler 2:41E6, and WEPUTIL). The same
workflow on the 8088 core (where an 80186 opcode would alias, not trap) also completed with
no 80186 opcode executed: 188M instructions, 22684 INT 3 traps (121 per 1M instructions,
about 0.2% of cycles at ~380 cycles per trap). Repeated on the final default build (heap
settings, APPDSLOCK, WEPUTIL fixes) with long waits: Open, Scramble, Hint, Fast Solve,
Rescramble complete, no 80186 opcode, 66 traps per 1M instructions (0.1%). A path not exercised by a run can still hold
a missed site; the static census is the only guard there.

WEPUTIL.DLL (Entertainment Pack helper, imported by JIGSAWED and the non-VB EP games) is
converted with only the 80186 rewrite (no wrapper, no segment changes). Its INT 3 handler
lives in its own fixed segment 3, because non-VB games load it without VBRUN; two handlers
chain through each other's `old3`, and each WEP restores the vector only if it still points
at itself, so when the DLL that installed first is unloaded first, the other handler's `old3` (and,
after the second unload, the vector) points at freed code. Only an INT 3 that is not one
of our sites (a debugger breakpoint) reaches it; rewritten sites are gone with their DLL.
Known limitation, not fixed.

Limitation: an INT 3 used by something else while VBRUN is loaded is still interpreted as
ours when the byte before the return address is CC (a debugger breakpoint, or the W8X
TSR's own INT 3 sites in a game running at the same time).

## Wrapper record identification (wrapcore)

Before: a return was matched to the record with the highest return-slot address below the
returning SP. A record left behind by a non-local exit whose slot lies inside a later
call's arguments was chosen for that call's return (reproduced:
`test_throw_then_call_whose_args_cover_old_slot`). Now each record slot k has trampoline
k as the hooked return address; the return identifies the record exactly; records of the
same stack whose slot is at or below the returning one are reclaimed (they belong to
unwound frames); a trampoline whose record is gone ends in FatalAppExit.

Records abandoned by an error reset or Throw are reclaimed when a call made from an outer
frame returns, so they are transient; an X=0 (unknown caller) record keeps its segment
locked until then.

## Error-raiser far jumps (pushret-reviewed.json)

See the entries' `why`. Summary of the evidence: the 14 jumps into 7:0279..0292 and the 2
into 2:4A6A/4A6C (which `call far 7:0294` and are followed by bytes nothing references)
never get the far return on the stack consumed by a RETF: the raiser body 7:0294..030B
only leaves through `call 0204 / ret`; 7:0204 calls far 4:173A; 4:173A runs straight to
`call far 2:0FCA` and 4:17F2 after it is a separate procedure; 2:0FCA begins with
`pop bx / pop bx`, discarding its own return address, restores the interpreter state from
the frame at SP (set by 4:17AA `mov sp,ax` from 2:42E7) and leaves with a near RET in
segment 2. So 4:173A, 7:0204 and the raiser never return. The jump's slot is reached again
only if the reset lands at or below it, inside the raising code's own frames — which would
break the runtime the same way in protected mode. Residual (observed, not proven): that
the reset target always encloses the raising code.

## Calls into the FIXSEGS segments (exit hang)

`wrap_pass` rewrote only ordinal references, i.e. far calls into movable segments. Calls
into the segments the converter makes FIXED (4, 5, 16) stay type-2 segment fixups and were
never wrapped, although 16 audited callees in seg 4 have 34 call sites in movable code.
Traced on exit after play beside MS-DOS Executive (MARTY_RING with an exact CS:IP
trigger): 2:11E1 `lcall 4:1232` (VB's terminate path) frees memory, seg 2 moves, and the
RETF at 4:124F returns to seg 2's old address — by then KERNEL seg 2, where 7705:11E6 is
`jbe $` in the middle of an instruction; the task spins (3 of 4 runs) or VB reports
"Subscript out of range" (1 run). APPDSLOCK made no difference. These 33 CALL FAR sites now
go through W stubs (`wrap_fixcallee`; `WRAPFIX=0` restores the old output). After the
change: exit after play clean in 2 of 2 runs, and in the full scenario below.

## Memory beside MS-DOS Executive

Scenario (`WIN /R C:\GAME\JIGSAWED.EXE` from MS-DOS Executive, V20, 640K, CGA): About,
Open, Scramble, Hint, Fast Solve, Rescramble, Alt+F4, close the shell, End Session.

| build | result | free during play |
| --- | --- | --- |
| allocfixed, headroom on all seg-105 allocations (old default) | VB quits at start: "Not enough memory to run; quitting" | — |
| same, I186=0 | same | — |
| allocfixed off | plays to Hint; KERNEL cannot load a 6 KB USER segment in Fast Solve, task terminated | 17 KB, largest 6.5 KB |
| allocfixed off, no headroom at all | VB quits at start (string-space block cannot grow) | — |
| allocfixed off + VBHEAPSKIP4 + WRAPFIX | whole scenario passes, back to DOS | 13-20 KB; 297 KB after exit |
| same, but apps started as the shell | RATTLER, RODENT, JIGSAWED quit at start ("Not enough memory to run"): string-space block has a locked upper neighbour | — |
| + VBHEAPRES2=0x400 | as shell: start; beside MS-DOS Executive: "Custom control '' not found" (stale app-DGROUP pointer, below) | — |
| allocfixed + all headroom + VBHEAPRES2=0x400 | as shell: puzzle and RODENT pass; beside MS-DOS Executive: freezes after Scramble, 144 bytes free | — |
| allocfixed off + SKIP4 + RES2=0x400 + APPDSLOCK + WEPUTIL fixes (default) | as shell: RATTLER, RODENT, PIPE run, JIGSAWED plays the puzzle; beside MS-DOS Executive: whole scenario passes | 13-15 KB |

Why: VB grows a few heap blocks in place through 105:008A; real mode cannot move them
(callers keep the segment). With `allocfixed` the string-space block (allocated through
seg 35, grown by 106:0749) landed in a 368-byte hole whose upper neighbour is a fixed font
block; it worked before the 8088 build only because the blocks then landed above the
smaller fixed VBRUN segment. Traced callers (MARTY_XW_DEPTH=48): ~100 of JIGSAWED's ~106
seg-105 allocations come from fixed seg 4:274B; their grows go through CTXGROW's grow2
(105:0214), which may move the block, so the 1.25x / 0x100 headroom on them never served a
grow (each measured grow exceeded it) and cost ~20 KB. `VBHEAPSKIP4` drops it for callers
whose CS is seg 4's. The few non-seg-4 blocks (string space through seg 35, program data
through seg 5, seg 7) are grown in place only and get `VBHEAPRES2` (1 KB) up front.
Not taken: `allocfixed` with no seg-4 headroom - grow2 then moves GMEM_FIXED blocks
(traced 3EC5 -> 489D) and JIGSAWED as shell spun at 3BDF:0E2x, i.e. something else held the
old segment.

Cost of the default (measured, JIGSAWED as shell after the About box): ~74% of PC samples
in KERNEL's global-heap code (0FA7:20Fx-21Ex, 354x), against 38% with the old allocfixed
settings; Game>Open takes more than 60M instructions before the dialog shows - at the 18.8
cycles/instruction measured on the 8088 core, roughly 4 minutes at 4.77 MHz (the old
settings: ~32M, about 2 minutes). Locked movable VB blocks spread
through the movable area make every allocation search and compaction longer.

Margins remain thin: one KERNEL segment load still fails once during
Fast Solve and succeeds after compaction.

## WEPUTIL conversion faults (found on the as-shell runs)

* WEP routed into fixed data segment 3 (where the INT 3 handler lives): when VB loads
  WEPUTIL for a `Declare` (JIGSAWED at Game>Open) and the load fails for memory, KERNEL calls
  WEP through GetProcAddress (KERNEL seg 2, `push "WEP"` at 094C) before seg 3 exists; traced
  jump to 182D:01DA (zeros) and a runaway. WEP now enters a stub in movable code seg 1
  (`I186WEPSEG`, default 1), loaded on demand through the entry thunk like the original WEP;
  it restores the INT 3 vector only if it still points at the handler in seg 3.
* Fast-load area: without FIXSEGS the converter kept an area ending at the start of the last
  data-bearing segment, leaving preloaded fixed seg 3 outside it. PIPE as shell: KERNEL read
  the header and the area, closed all files, Windows quit to DOS. No converted module keeps
  a fast-load area now.

## App DGROUP pointers at startup (APPDSLOCK)

Beside MS-DOS Executive with the in-place-grown blocks at a 1 KB minimum, VB reported
"Custom control '' not found" at start. Traced (ring trigger on the loader's error call
101:0241, then back through 21:03B0 -> 71:0394): 71:0FE4 looks the control class up, 54:010E
returns the far pointer 4085:187C (the model pointer into the app DGROUP that APPDSLOCK was
written for) and 54:004E finds nothing there; the DGROUP had moved (4087 -> 4085) after VB
stored it. A write-watch on both the new and the old location (MARTY_WW) shows only KERNEL's
block copy of the whole DGROUP at the move (1093:20B7, i16.6M) and no later write through
a stale pointer, so the record at 187C is intact: what fails is VB's check against the
DGROUP segment it stored inside its own records. Any DGROUP move after the records exist
breaks them; keeping the DGROUP in place is the fix, hence APPDSLOCK=1 by default. With it
that case starts and the full scenario passes.

Cost (JIGSAWED as shell, same build with and without the lock, slow-paced puzzle run):
KERNEL 60% of PC samples after start with APPDSLOCK, 24% without; both complete the
puzzle. The locked 35 KB DGROUP sits in the middle of the movable area (7A33 as shell)
and every compaction has to work around it. Placing it low first (GlobalWire) was tried
in an earlier session and crashed on close; not retried.

## Entertainment Pack 4 controls (Go Figure!, Tic Tac Drop)

`build.sh` now also converts any supplied `*.VBX` and `COMMDLG.DLL` (every data segment
fixed, `ORDSEL=1`, `TABSEGS=` empty) and `WEP4UTIL.DLL` (WEPUTIL recipe).

* The controls take selectors and offsets of their own procedures and data segments through
  their movable entry ordinals (THREED 7 push pairs and 2 stores, GAUGE 2, CMDIALOG 3,
  COMMDLG 21 `mov ax,off / mov dx,seg` pairs). `ORDSEL` resolves such fixups to the entry's
  segment/offset so the existing far-pointer patterns apply; before, GAUGE raised an
  IndexError and THREED got an entry with segment 0xFF.
* `TABSEGS`: FIELD100's far-pointer table segment 4 was assumed for every non-VB module;
  in the controls seg 4 is code (a `mov [bp-18h],seg` there became a bogus entry).
* A far call into a segment that is FIXED in the original (CMDIALOG seg 1) is no longer
  turned into a movable entry.
* 80186 differential test: GAUGE 112 sites, THREED 742, CMDIALOG 98, no difference.
  COMMDLG has no 80186 instruction; all its KERNEL/USER/GDI/KEYBOARD imports exist in the
  real-mode 3.0 modules; its LibEntry only looks at bit 15 of __WINFLAGS.

Runs (as shell, CGA; V20 = diagnostic only):

| app | controls | result |
| --- | --- | --- |
| Tic Tac Drop | original (V20) | "Custom control 'CommonDialog' not found" |
| Tic Tac Drop | converted (8088 core) | splash and credits from ~175M instructions; "Invalid property value" at ~460M |
| Go Figure! | original (V20) | "Custom control 'SSPanel' not found" |
| Go Figure! | converted (8088 core; V20 the same at 176M) | blank until ~176-200M, then "Property or control 'uGameNewMatch' not found" (raised from VBRUN seg 21) |

Both start very slowly: as shell the heap holds ~100 KB free in pieces but KERNEL keeps
discarding and reloading code segments (about 8 loads per million instructions, VBRUN
segments 49-100, THREED, CGA.DRV, USER/GDI). A GlobalAlloc of 0x13D4 bytes repeating every
cycle was traced to a system module's bitmap path (386 branch next to it), not a control.

### Go Figure's missing control: a VB local heap that cannot grow in place

Traced on the V20 (diagnostic; the same error and timing class as the 8088 core) with
GlobalAlloc, GlobalReAlloc, LocalAlloc, LocalReAlloc and MessageBox watched, as shell:

* Up to the error at 176M there are 44 failed LocalAlloc calls, all between 16.67M and
  17.07M, all from VBRUN seg 78:0025 (VB's "allocate in local heap X" helper, sizes
  0x11-0x1C, LMEM_MOVEABLE|ZEROINIT) in the heap at 474B (handle 0532). No GlobalAlloc
  failed in the run.
* That heap was created at 15.46M by seg 88:0013 through seg 77 (GlobalAlloc 0x42 of
  0x400+0x210 bytes, locked, LocalInit). At 16.32M KERNEL's LocalGrow asked
  GlobalReAlloc(0532, 0x840, 0) - in place, the block is locked - and it failed after
  ~350k instructions of compaction. Every later allocation in that heap failed.
* Then VB could not find a control by name: 'uGameNewMatch' at 640 KB. With 576 KB
  (machine xt_win576, 8088 core) the error comes at the same point with a different name,
  'uLevelBeginner'. So the failure is where the locked heap sits, not the total free memory
  (~100 KB free, largest block ~95 KB at the error).
* `VBLHEAP88=0x1000` (seg 88 heap created with 0x1000+0x210): no LocalAlloc failure; the
  next failure is the seg 71 heap (handle 06CA) growing to 0x3324 in place, followed by a VB
  error box with an empty message at 38.8M. `VBLHEAP71=0x4000` as well: no allocation
  failure, and the game window with its menu and controls appears (V20 76M, 8088 core
  ~200M). In the default build the seg 71 heap reached 0x38A4 and the seg 88 heap 0xA8C
  (Tic Tac Drop).

On the 8088 core with both larger heaps, as shell: the window appears at ~200M and the Game
menu opens and closes (no puzzle played).

Beside MS-DOS Executive the outcome depends on the build, not on free memory:

* Default build (8088): the window appears (~330M), Game menu, F2 starts a puzzle (digits
  dealt, score and timer running), Alt+F4 returns to the Executive, End Session to DOS.
* Larger heaps (8088 and V20): hang. This is memory corruption, not exhaustion (an earlier
  reading of "160 bytes free" came from a broken arena chain). V20 write watch on the
  overwritten arena: VBRUN seg 73:00C5-00FA copies a counted string into a 64-byte stack
  buffer. The string pointer came from seg 4:0DCD (name lookup through the module-context
  table in [2E04]) and pointed into a block that now holds p-code (5803:00DE, "length"
  0xDD sign-extended by CBW), so the loop copied ~64 KB over the stack segment and the
  next arenas; seg 4:0E2B then loops on the damaged list.
* Larger heaps with `CTXGROW=` (no moving grow2 for seg-4 context blocks, V20): the window
  appears. So a context block moved by CTXGROW's grow2 leaves another holder of its old
  segment; only [di+2] is updated. Same symptom as the earlier allocfixed note (spin at
  seg 4:0E2x). The other holder is not identified; candidates are the context cache copies
  at DGROUP 2E54/2E94 (seg 4:0326/0339) and the table at [2E04]. `TABGROW` and `CTXGROW`
  are now overridable; defaults unchanged (runtime byte-identical). With the larger
heaps JIGSAWED (About, Open, scramble), RATTLER and RODENT still pass the Executive exit
sequence on the 8088 core.

### Tic Tac Drop's "Invalid property value"

Not an allocation failure: no LocalAlloc failure, four in-place GlobalReAlloc failures of
0x470 bytes from VBRUN seg 105 that VB retries, and the error is unchanged with the larger
heaps. Trace (V20, deterministic, error raised at 487.95M through entry 106 = seg 7:0294 with
BX=0x17C): VBRUN seg 83:03D5 calls the subclassed control's original window procedure
(CallWindowProc) with message 0x040E (CB_SETCURSEL), wParam 0xFFFE (-2), on hwnd 1A90; USER's
combo box code returns -1 (CB_ERR) and VB turns that into error 380. Where the index -2 comes
from (e.g. a list count of -1) is not established.

The default build keeps VBLHEAP88=0x400 and VBLHEAP71=0x3000 (byte-identical runtime);
`VBLHEAP88` is now overridable like `VBLHEAP71`. The larger heaps cost ~7 KB of locked
memory, which matters beside MS-DOS Executive (13-20 KB free with JIGSAWED).

Exits beside MS-DOS Executive on the 8088 core (Pack 2 files): RATTLER and RODENT both
started a game, played, closed with Alt+F4 back to the Executive, End Session to DOS;
JIGSAWED the same after About, Game>Open of C:\PUZ.BMP and the scrambled puzzle.
Tic Tac Drop's error box is raised from VBRUN seg 21 as well (V20, i476M).

## Open items / limits

* No real hardware tested. All results are MartyPC (V20 and 8088 cores, 640K, IBM CGA).
  Tandy 1000 video was not exercised.
* Speed: with APPDSLOCK, JIGSAWED as shell spends ~60% of its time in KERNEL's heap code;
  Game>Open is minutes on a 4.77 MHz 8088 by instruction count. Beside MS-DOS Executive the
  KERNEL share is ~45% (36% without the lock).
* Memory margins are thin beside MS-DOS Executive (13-20 KB free during play); one 6 KB
  KERNEL segment load fails during Fast Solve and succeeds after compaction.
* Layout sensitivity: several faults found here (string-space hole, stale DGROUP record,
  exit stale return, WEP into an unallocated segment) appeared only in some memory layouts.
  The fixed ones are understood; other latent ones may show with other apps or setups.
* The 16 error-raiser far jumps (pushret-reviewed.json) stay reviewed by static flow plus
  the observed reset; the corrupt-bitmap test did not raise a VB error (JIGSAWED reports
  "Out of memory" itself and recovers), so it adds no run-time evidence for them.
* INT 3 handler chaining between VBRUN and WEPUTIL on out-of-order unload (see above).
* JIGSAWED as the Windows shell: exit is a UAE in stock protected mode too (not pursued).
* Not taken: allocfixed with no seg-4 headroom (grow2 moves fixed blocks; a holder of the
  old segment made JIGSAWED spin at start).
