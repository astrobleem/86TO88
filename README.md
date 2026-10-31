# 86TO88 — run the original Windows 3.1 Minesweeper on Windows 3.0 / 8088-class hardware

**86TO88** (the **WM88 bridge**) makes the *original, unmodified* Windows 3.1
`WINMINE.EXE` run and play under Windows 3.0 in real mode — the environment of
an 8088-based Tandy 1000 EX (7.16 MHz, 640 KB). It is a small DOS TSR plus a
361-byte DLL shim. No part of the game is reimplemented.

> **The original `WINMINE.EXE` stays byte-for-byte unchanged on disk.** The
> TSR intercepts DOS file reads of that one file and translates the bytes
> **in memory only** (in the caller's read buffer). The disk file is never
> written, and segments that Windows discards and reloads are simply
> re-translated on the next read.

## Why the 3.1 binary won't start on Windows 3.0, and what the bridge does

| Barrier in the stock binary | Bridge fix (all outside the file) |
|---|---|
| NE header says "requires Windows 3.10" | The two version bytes are flipped 3.10 → 3.00 in the read buffer only |
| 449 sites use 80186+ instructions (`PUSH imm`, `IMUL imm`, `SHL/SHR/SAR reg,imm8`) that fault on an 8088 | Sites are rewritten in the buffer to `INT F8h` traps; a resident handler emulates each instruction exactly (result, flags, stack). 6 further sites where a relocation overlaps a push immediate use an `INT 3h` handler |
| Imports `ShellAbout` from module `SHELL` ordinal 22; Windows 3.0 has no `SHELL.DLL` | We ship a 361-byte `SHELL.DLL` exporting exactly that entry (it forwards the app's own strings to `MessageBox`) plus `WEP` |
| Everything else (`KERNEL`, `USER`, `GDI`, `SOUND` imports) | Resolves to genuine Windows 3.0 components — module `SOUND` is provided by the stock `SOUND.DRV`. **No Windows file is patched, hooked, or replaced** |

Safety: before hooking anything, the TSR verifies the target (file size,
MZ/NE signatures, version bytes, and a reconstruction of every trap site).
An unrecognized binary is left completely alone.

## What you supply

* DOS + **Windows 3.0** running in real mode (`WIN /R`).
* **Your own unmodified `WINMINE.EXE`** from Windows 3.1. This repository
  contains no Microsoft binaries. Reference specimen used in development:
  27,776 bytes, SHA-256
  `633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b`.
  A different build will (correctly) be refused by the TSR.

## Quick start

**Real DOS machine**

1. Copy `deliverable/` to a floppy or DOS directory.
2. Run `INSTALL.BAT` there — it installs `SHELL.DLL` into `C:\WINDOWS\SYSTEM`
   (backing up any existing one) and the launcher into `C:\WINDOWS`.
3. Copy your `WINMINE.EXE` into `C:\WINDOWS`.
4. `CD \WINDOWS`, run `WM88.BAT`, play.

**DOSBox-X fixture**

Put a Windows 3.0 installation plus the copies above into one folder, point
`deliverable/dosbox-wm88.conf`'s mount at it, and run
`dosbox-x -conf dosbox-wm88.conf`. Windows boots with the game already open.

## Status — what is proven, and an honest caveat

Proven end-to-end (see `evidence/`): the original binary launches, and real
gameplay works — first-click flood reveal, numbers, flag/question-mark
cycling with the mine counter, the 1 Hz timer, F2 / Game→New restart,
preference persistence to `WINMINE.INI`, a logically solved **win** (best-time
dialog, `Time1=801` recorded by the game itself), and a **loss** with all ten
mines exposed. DOS-level suites (`tests/TEST88.COM`, `tests/RTEST2.COM`)
verify the instruction emulation (flags/stack/registers) and the read
interception (partial/overlapping reads, seeks, EOF) exactly.

> **Caveat:** the full *Windows* sessions above ran on an **emulated 286**
> (DOSBox-X `cputype=286`), because DOSBox-X's 8086 core hangs even a
> completely stock Windows 3.0 — an emulator limitation, confirmed with
> unmodified boot disks. The emulation handler itself is CPU-exact and the
> DOS suites pass on 8088-class settings, but **literal-8088 end-to-end
> validation (PCjs, DOSBox-X `machine=tandy`, physical Tandy 1000 EX) is
> still in progress and is not claimed here.**

Real vs simulated: all of Windows and 100% of the game logic are the genuine
original code. The single simulated piece is `ShellAbout`: instead of the
richer 3.1 About box you get a plain `MessageBox` with the app's name and
"by Robert Donner and Curt Johnson". No game API is stubbed.

Performance (DOSBox-X, 10,000 fixed cycles): DOS boot → playable window in
about 2.3 s. The TSR is 10,253 bytes on disk, ≈9.3 KB resident. On a real
7.16 MHz 8088 expect slower flood-fill redraws; functional, not yet measured.

## Repository layout

* `deliverable/` — the consumer bundle (TSR, shim, installer, launcher, fixture config)
* `src/` — all builder/analysis source, including the two-pass 8086 assembler (`asm88.py`), the site generator (`gen_sites.py`), and the TSR/shim builders
* `artifacts/` — generated patch/site tables the builders embed, plus export maps used during analysis
* `tests/` — prebuilt DOS verification suites
* `tools/` — host-side test tooling (serial-mouse server, board reader)
* `emulator/` — the scripted-test DOSBox-X configuration (serial mouse)
* `evidence/` — curated screenshots and test outputs from the runs described above

See `BUILD.md` to rebuild everything from source.

Built for the Meta Global AI Developer Hackathon engineering-agent brief.
Development model: Muse (muse-wonder-1.0) — all reverse engineering,
implementation, testing, and gameplay.
