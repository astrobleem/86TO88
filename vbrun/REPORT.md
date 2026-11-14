# VBRUN100 real mode / 8088 — engineering report

Branch `wip/vbrun100-realmode`, 2026-11-14. Not merged, not released. All testing is in
MartyPC (V20 and 8088 cores, 640 KB, IBM CGA); **no real hardware was tested**. Details and
evidence are in `NOTES.md`.

## Result against the acceptance targets

| target | status | evidence (emulator) |
| --- | --- | --- |
| 1. JIGSAWED launches, plays a complete puzzle, exits cleanly | met in both layouts tested | as shell: About, Open, Scramble, Hint, Fast Solve, Rescramble on V20 and 8088 cores; beside MS-DOS Executive: same plus Alt+F4 back to the shell, End Session, back to DOS |
| 2. JIGSAWED beside MS-DOS Executive without exhausting memory | met, thin margin | 13-20 KB free during play, 297 KB after JIGSAWED exits; one KERNEL segment load retries once during Fast Solve |
| 3. RATTLER and the other test apps keep working | met for RATTLER, RODENT, PIPE | each started as shell and played on V20 and 8088 cores; PIPE is a non-VB EP game using the converted WEPUTIL.DLL |
| 4. Relocation, compaction, callbacks, errors, termination | fixed what the runs exposed | see "Faults found and fixed"; error-raiser paths remain reviewed statically (no run raised a VB error) |
| 5. 8088-compatible within realistic memory | met in the emulator | no 80186 opcode executed in any run (V20 report and 8088 core); INT 3 trap cost 0.1-0.2% of cycles; 640 KB |

Main cost: speed. With the app DGROUP locked (needed for correctness), JIGSAWED as shell
spends ~60% of its time in KERNEL's heap code; Game>Open is on the order of minutes on a
4.77 MHz 8088 (estimated from instruction counts, not measured on hardware).

## Faults found and fixed in this round

1. **8088 opcodes**: every reachable 80186 instruction in VBRUN100 (2974 sites),
   FIELD100 (89) and WEPUTIL (223) rewritten; differential test per site, zero differences;
   coverage confirmed by running the workflows with an "80186 opcode executed" report.
2. **Exit hang after play** (3 of 4 runs hung, 1 showed "Subscript out of range"): far calls
   from movable code into callees in the segments the converter makes FIXED were never
   wrapped; VB's terminate path moved seg 2 under its caller and the RETF went into KERNEL
   code. 33 call sites now go through the wrapper (`WRAPFIX`).
3. **VB quits at start ("Not enough memory to run")**: a heap block VB grows in place landed
   in a hole capped by a fixed block. Allocation headroom now goes only to the few blocks
   grown in place (1 KB minimum, `VBHEAPRES2`); the ~100 seg-4 blocks (whose grows may move)
   get none (`VBHEAPSKIP4`, saves ~20 KB); `allocfixed` off.
4. **"Custom control '' not found" at start**: VB stores its DGROUP segment inside its own
   records; a 2-paragraph DGROUP move broke the lookup. The DGROUP is locked after the entry
   grow (`APPDSLOCK`, now default) and unlocked at exit.
5. **WEPUTIL runaway**: WEP had been routed into a fixed data segment; a failed on-demand
   load made KERNEL call it before that segment existed. WEP now goes through a stub in a
   movable code segment.
6. **WEPUTIL would not load (PIPE, RODENT, JIGSAWED's Open)**: the converter's fast-load area
   left a preloaded fixed segment outside it. No converted module keeps a fast-load area.
7. **Stale far returns**: wrapper records are matched exactly by per-slot return
   trampolines; a return without a record ends the app instead of guessing.

The 16 error-path far jumps kept their stale-return protection; they are documented as
reviewed (static flow, residual assumption stated), not proven.

## Known limitations

* No hardware validation; Tandy 1000 video not exercised.
* Speed with the DGROUP lock (above). Without the lock the as-shell case is ~2.5x lighter
  on KERNEL but the MS-DOS Executive case fails at start.
* Memory beside MS-DOS Executive is tight; other apps or a larger picture may not fit.
* Faults here were layout-dependent; others may appear with other apps or configurations.
* INT 3 handler chaining between VBRUN and WEPUTIL on out-of-order unload.

## Build and tests

    VBW_ORIG=<dir with the original DLLs> vbrun/build.sh OUTDIR
    python3 -m pytest vbrun/tests        # 103 tests
    vbrun/i186test.py ORIG PRE CONV      # per-site 80186 differential test

Emulator scenarios: `vbrun/rig/` (puzzle, shell, app). Diagnostic switches and emulator
trace options (`MARTY_W186`, `MARTY_RING` with exact CS:IP, `MARTY_XW_DEPTH`, `MARTY_WW`)
are described in `NOTES.md` and `emulator/martypc/trace-hooks.patch`.
