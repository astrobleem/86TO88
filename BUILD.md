# Building 86TO88 from source

You only need Python 3 (standard library; `capstone` is needed solely for the
optional site-regeneration step). No C compiler is used anywhere — the TSR and
the shim are assembled by the small two-pass 8086 assembler in `src/asm88.py`.

All commands run from the repository root. Builders write to `artifacts/`.

## 1. Build the TSR and the shim

```
python3 src/build_tsr.py     # -> artifacts/WM88TSR.COM   (10,253 bytes)
python3 src/build_shell.py   # -> artifacts/SHELL.DLL     (361 bytes)
```

Expected SHA-256:

```
3e9c7c029547a57df183b4366e72d33b8913b5fc1f5d9bdd46010397f0d3af5b  WM88TSR.COM
2d7532ae8ac73b957b5fb423449168c7b8f976b150155a42ac37d4b0139ddd1b  SHELL.DLL
```

`build_tsr.py` embeds the committed tables `artifacts/sites-table.bin`,
`artifacts/patchbytes.bin`, and `artifacts/cc-sites.bin` (the census of the
449 `INT F8h` sites, the byte patches, and the 6 relocation-overlap `INT 3h`
sites). `deliverable/` holds copies of the two built binaries together with
`INSTALL.BAT`, `WM88.BAT`, and the fixture config.

## 2. Build and run the DOS verification suites

```
python3 src/build_test88.py                 # -> artifacts/TEST88.COM
python3 src/build_readtest2.py WINMINE.EXE  # -> artifacts/RTEST2.COM (arg: your specimen copy)
```

* `TEST88.COM` — 14 cases checking the `INT F8h`/`INT 3h` emulation exactly:
  results, flag bits (merge mask `08C5h`, unaffected bits preserved), stack
  effect, and register behaviour. Prints `T88PASS` on success.
* `RTEST2.COM` — 15 cases checking the read interception: partial and
  overlapping reads, reads starting inside a patch site, version-span reads,
  sequential continuation, seeks from start/current/end, EOF partial reads,
  zero-length reads, and two interleaved handles. Prints `RT2PASS-15`.

Prebuilt copies are in `tests/`. Run them in any DOS (or DOSBox-X with
`-silent -exit` and a directory mount); captured passing outputs are in
`evidence/T88OUT.TXT` and `evidence/R2OUT.TXT`.

## 3. Run the full Windows test

Use `emulator/dosbox-wm88-test.conf` (serial-mouse variant used for the
scripted evidence) or `deliverable/dosbox-wm88.conf` (standard mouse). Both
boot a guest folder that contains Windows 3.0, your `WINMINE.EXE`, and the
deliverable installed per the README. Note the `cputype=286` setting: it is
required with DOSBox-X today because its 8086 core hangs even stock
Windows 3.0. The guest mouse in the test config is a Microsoft serial mouse
served by `tools/mousesrv.py` (TCP 127.0.0.1:13999, commands via
`/tmp/mouse.fifo`); `tools/boardread.py` classifies the 8×8 board from a
screenshot for scripted verification.

## 4. (Optional) Regenerate the site tables

```
python3 src/gen_sites.py WINMINE.EXE   # -> artifacts/sites-table.bin, patchbytes.bin, cc-sites.*
```

This disassembles segment 1 of the specimen and rebuilds the census. It
additionally needs `capstone` and the `w31check` NE parser from the Windows
XT project (https://github.com/astrobleem/oemdisplay-tandy) on `PYTHONPATH`.
It refuses nothing itself — always check the specimen SHA-256 first
(`633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b`); the TSR
re-verifies the same facts at load time in the guest.

## Notes on the rest of `src/`

`src/` also contains the diagnostic builders used during development
(`build_dbg*.py`, `build_only*.py`, `build_tsr_log.py`, the `build_shellv2.py`
bisect variants, `audit_ne.py`, `analyze*.py`, …). They document how the two
real bugs were isolated — the far-call chain terminator that had to be
`0xFFFF`, and the 2-byte NE resource table that corrupted KERNEL's heap —
and are kept for the record; several still reference the original development
machine's layout. The supported build path is steps 1–2 above.
