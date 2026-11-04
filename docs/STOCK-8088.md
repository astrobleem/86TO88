# Stock 8088: why Windows 3.0 crashes, and what runs

Technical notes. The README links here; nothing in it depends on this file.

## Cause

The stock Windows 3.0 install crashes on a real 8088 because its own EGA display driver,
`WINDOWS\SYSTEM\EGA.DRV`, uses 80186 instructions. On an 8088 the 80186 opcodes are
aliased rather than faulting (`C1` executes as `RET`, `0F` as `POP CS`, and so on), so the
first `shr dx,3` (`C1 EA 03`) sends execution into garbage. This is the black-screen hang
and the KERNEL-startup failure seen earlier in PCjs and 86Box. The bridge is not involved.

## Method

MartyPC 0.5.0 (cycle-accurate 8088, GLaBIOS, XT-IDE, IBM EGA) was traced instruction by
instruction, with a reader that flags opcodes `60`-`6F`, `C0`, `C1`, `C8`, `C9`.

* **8088 core, stock disk:** the first 80186 opcode executed is `C1 EA 03` at `1e51:09ca`
  (instruction 12,082,498), in `EGA.DRV` at file offset 5412. The machine fails there.
* **V20 core, stock disk:** Windows reaches Program Manager. All 63 unique 80186 sites
  executed on the way belong to `EGA.DRV`: two static ones (`shr dx,3`, `shr bx,2`, each
  occurring exactly once in the file) and the rest in bitblt code the driver generates at
  run time (`rol/ror al,n`). KERNEL, KRNL286, USER, GDI, PROGMAN, SYSTEM.DRV, KEYBOARD and
  MOUSE execute none.
* **8088 core, `CGA.DRV` + CGA fonts instead of the EGA driver:** Windows 3.0 reaches
  Program Manager with no 80186 opcode executed in 20.6 million instructions.
* **Same, plus the WM88 bridge:** the original Windows 3.1 `WINMINE.EXE` launches and runs
  with none executed in about 19 million instructions. The CGA screen is 640x200
  monochrome, so the window extends past the bottom. Gameplay was not exercised.

## Other Windows 3.0 distributions

`EGA.DRV` is byte-identical (SHA-256 `03d772c6...`) in the project's disk and in the
Windows 3.0 720K, 3.0 360K and 3.0a 720K retail sets, so none offers a different EGA
driver. `VGA.DRV` and `8514.DRV` contain the same `shr` patterns. `CGA.DRV`,
`HERCULES.DRV`, `EGAMONO.DRV`, `EGAHIBW.DRV` and `TTY.DRV` do not. Only `CGA.DRV` was
confirmed by execution.

## TANDY88

The TANDY88 driver was audited separately by the project author: no unsupported opcodes
in 13,707 emitted instruction rows, and an 8086-prefetch test passed all 4,096
generated-rotate cases. That audit was not re-run here. The Tandy 1000 EX used for the
hardware run has an NEC V20, so that run does not exercise the 8088 case.

## Limits

MartyPC's 8088 results use a CGA display, not the Tandy video hardware. No Tandy BIOS was
available to run the TANDY88 driver under MartyPC. Earlier DOSBox-X gameplay sessions
used an emulated 286.
