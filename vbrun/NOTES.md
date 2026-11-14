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

Experimental / diagnostic switches (off by default): `APPDSLOCK=1` (lock the app DGROUP
after the entry grow), `WRAPSTATS=1` (wrapper counters, read with `wstats.py`),
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
to be gone. Sites are found by recursive descent from entries, relocation targets
(far calls/jumps, far pointers with a procedure prologue, offset fixups), PUSH CS/CALL
targets and MSC switch tables (bounded by the `cmp ax,N` before the jump), and run over
the converter's current code so its appended stubs are covered too. Each site is replaced
by code of the same length:

| original | count (VBRUN/FIELD) | replacement |
| --- | --- | --- |
| PUSH imm16 | 595 / 31 | CALL near to a per-segment trampoline per value (per site if a fixup covers the immediate; the fixup moves into the trampoline) |
| PUSH imm8 | 1977 / 52 | INT 3 + the immediate byte; resident handler in segment 24 |
| SHL/SHR/SAR r,imm8 | 156 / 5 | CALL near to a shared trampoline of n 1-bit shifts |
| ENTER n,0 | 15 / 0 | JMP to PUSH BP / MOV BP,SP / LEA SP,[BP-n] / JMP back |
| LEAVE + RETF n | 20 / 0 | JMP to MOV SP,BP / POP BP / RETF n (one LEAVE+RETF moved with the two POPs before it) |
| IMUL r,m,imm | 7 / 1 | JMP to a sequence that saves AX/DX and uses IMUL r/m16 |

The INT 3 handler is installed by the DLL entry point (routed through `init`) and removed
by WEP (routed through `wep`) if the vector still points at it; an INT 3 that is not a
rewritten site (no CC before the return address) goes to the previous handler.

Verification: `tests/test_i186.py` (each form against the native instruction, random
states, corner cases); `i186test.py` on the real DLLs (all 2770 + 89 sites, zero
differences; it detects deliberately broken trampolines/handler); `i186.py --check`.

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

## Open items / limits

(updated as work proceeds)
