# Entertainment Pack compatibility coverage — edition-specific audit

**Latest 8088 follow-up:** [Clean interaction tests and short-path module lookup fix](WEP-CLEAN-8088.md). The inventory and historical results below are retained as an earlier record.

**Fresh follow-up:** [DOSBox-X 8086-prefetch diagnostics](WEP-FRESH-DOSBOXX.md) attempted all Pack 1 and Pack 4 editions and Best of RODENT. These single-run observations are incomplete and do not establish 8088 compatibility. The historical inventory and counts below describe the earlier audit.

**Status as of November 14, 2026.** This inventory was checked against the user's uploaded Pack 1, Pack 2, Pack 3, Pack 4 floppy images and *Best of* ZIP. It covers **44 pack-specific executable/screen-saver entries representing 29 distinct titles** (28 games and IdleWild). Installers and support DLLs are not counted as games.

**Important: this is a complete *inventory*, not 44 successful execution tests.** The current review environment could extract and inspect the media but could not launch Windows: a compatible MartyPC/DOSBox executable was unavailable. **No new gameplay or startup screenshot was captured for this audit.** All execution results below are historical, taken from the committed [WM88X3 test report](WEP-LIBRARY.md) and the merged [VB runtime report](../vbrun/REPORT.md). Do not interpret an untested row as incompatible, a startup screen as completed gameplay, or a successful result from one pack as proof about a different executable in another pack.

## Result summary

| Coverage measure | Count |
| --- | ---: |
| Distinct titles (including IdleWild screen saver) | **29** |
| Pack-specific entries in all five uploaded editions | **44** |
| Entries with earlier launch/screen/dialog evidence | **24** |
| Entries with newer VB runtime / WEPUTIL gameplay evidence | **4** |
| Entries with previously observed startup failures | **4** |
| Entries with no pack-specific execution evidence | **12** |

In terms of **distinct** titles, 22 have at least one historical successful launch/screen or gameplay result across the provided editions, including IdleWild. **Blackjack, Chips and Stones** have documented historical failures; **Chess, Go Figure!, Maxwell's Maniac and Tic Tac Drop** have no execution result yet. Those counts do not imply every edition works, or that titles were tested together.

## What the result labels mean

- **VB runtime gameplay / WEP helper gameplay:** Newer MartyPC V20 and stock-8088-core results with 640 KB and IBM CGA from the merged `vbrun/` project. Not physical 8088 hardware.
- **Prior startup / splash / dialog / screen saver:** Earlier `WM88X3` module-library tests; typically just a displayed window, dialog, splash, or blanked saver. No full-play claim.
- **Prior VGA startup:** Tetris tested with the separate 16-color VGA display driver.
- **Prior failure:** The earlier setup tried this edition and failed. A different converter or video configuration could behave differently.
- **Not tested:** No verified execution result for this particular executable build.

## Coverage by pack

### Pack 1 (1990)

| Game / application | Filename on uploaded media | Status | What was actually observed |
| --- | --- | --- | --- |
| Cruel | `CRUEL.EXE` | Prior startup | WM88X3 game window; not played through |
| Golf | `GOLF.EXE` | Not tested | Pack 1 executable not tested; Best of edition launched separately |
| IdleWild (screen saver) | `IDLEWILD.EXE` | Prior screen saver | WM88X3 blanked the display |
| Pegged | `PEGGED.EXE` | Prior startup | WM88X3 game window; no full play |
| Tetris | `TETRIS.EXE` | Not tested | Pack 1 executable untested; Best of Tetris had separate VGA-only result |
| TicTactics | `TIC.EXE` | Prior startup | WM88X3 game window; no full play |
| Taipei | `TP.EXE` | Prior splash | Splash screen only, not gameplay |
| WinMine (Windows 3.0 edition) | `WINMINE.EXE` | Prior startup | WM88X3 game window; not the Windows 3.1 WINMINE.EXE used in the original WM88 bridge |

### Pack 2 (1991)

| Game / application | Filename on uploaded media | Status | What was actually observed |
| --- | --- | --- | --- |
| FreeCell | `FREECELL.EX$` | Prior startup | WM88X3 window; empty until F2, no complete game |
| IdleWild (screen saver) | `IDLEWILD.EX$` | Not tested | No separate test of this edition |
| JIGSAWED | `JIGSAWED.EX$` | VB runtime gameplay | Full puzzle and clean exit beside MS-DOS Executive; MartyPC V20 and 8088, CGA |
| Pipe Dream | `PIPE.EX$` | WEP helper gameplay | Played with converted WEPUTIL.DLL on both CPU cores; no completed game |
| RATTLER | `RATTLER.EX$` | VB runtime gameplay | Launched and played on both CPU cores; no completed game |
| RODENT | `RODENT.EX$` | VB runtime gameplay | Launched and played on both CPU cores; no completed game |
| Stones | `STONES.EX$` | Prior failure | WM88X3 run reported style DLLs corrupted or missing, including protected-mode-only DLLs |
| Tut's Tomb | `TUTSTOMB.EX$` | Prior startup | WM88X3 opening/dealt display; no full game |

### Pack 3 (1991)

| Game / application | Filename on uploaded media | Status | What was actually observed |
| --- | --- | --- | --- |
| Fuji Golf | `FUJIGOLF.EX$` | Prior startup | WM88X3 clubhouse; needs FUJIGOLF.DAT expanded from FUJIGOLF.DA$ |
| IdleWild (screen saver) | `IDLEWILD.EX$` | Not tested | No separate test of this edition |
| Klotski | `KLOTSKI.EX$` | Prior startup | WM88X3 game window; no full game |
| LifeGenesis | `LIFEGEN.EX$` | Prior startup | WM88X3 game window; no full game |
| SkiFree | `SKI.EX$` | Prior startup | WM88X3 game window; no full game |
| TetraVex | `TETRAVEX.EX$` | Prior startup | WM88X3 game window; no full game |
| TriPeaks | `TRIPEAKS.EX$` | Prior dialog | Name dialog only; gameplay not established |
| WordZap | `WORDZAP.EX$` | Prior startup | WM88X3 game window; no full game |

### Pack 4 (1992)

| Game / application | Filename on uploaded media | Status | What was actually observed |
| --- | --- | --- | --- |
| Blackjack | `BLAKJAK.EX_` | Not tested | This edition untested; Best of Blackjack previously failed |
| Chess | `CHESS.EX_` | Not tested | No launch evidence |
| Chips Challenge | `CHIPS.EX_` | Not tested | This edition untested; Best of Chips previously failed |
| Go Figure! | `GOFIGURE.EX_` | Not tested | No launch evidence |
| JezzBall | `JEZZBALL.EX_` | Not tested | This edition untested; Best of JezzBall launched separately |
| Maxwell's Maniac | `MAXWELL.EX_` | Not tested | No launch evidence |
| Tic Tac Drop | `TICTACDP.EX_` | Not tested | No launch evidence; the pack's own README says approximately 500 KB free RAM is needed |

### Best of Microsoft Entertainment Pack (1994)

| Game / application | Filename on uploaded media | Status | What was actually observed |
| --- | --- | --- | --- |
| Blackjack | `BLAKJAK.EX_` | Prior failure | WM88X3: protected-only flag; attempting to patch caused memory corruption |
| Chips Challenge | `CHIPS.EX_` | Prior failure | WM88X3: insufficient-memory startup error |
| FreeCell | `FREECELL.EX_` | Prior startup | WM88X3 window; no complete game |
| Golf | `GOLF.EX_` | Prior startup | WM88X3 game window/dealt display |
| JezzBall | `JEZZBALL.EX_` | Prior startup | WM88X3 game window; no complete game |
| Pipe Dream | `PIPE.EX_` | Prior splash | Opening screen only; Pack 2 gameplay does not validate this executable |
| RODENT | `RODENT.EX_` | Prior failure | Old WM88X3 test failed; not retested with new converted VB runtime for this edition |
| SkiFree | `SKI.EX_` | Not tested | Best of edition untested; Pack 3 SkiFree launched separately |
| TetraVex | `TETRAVEX.EX_` | Prior startup | WM88X3 game window |
| Tetris | `TETRIS.EX_` | Prior VGA startup | Screenshot with separate 640x480 16-color VGA driver, not CGA or WM88X3 proof |
| Taipei | `TP.EX_` | Prior splash | Splash screen only |
| TriPeaks | `TRIPEAKS.EX_` | Prior startup | WM88X3 game window |
| Tut's Tomb | `TUTSTOMB.EX_` | Prior startup | WM88X3 game window |

## Screenshots

The repository already contains real **earlier emulator captures**. They illustrate particular builds and should not be represented as screenshots from this audit or as proof of every edition.

| Screenshot | Capture notes |
| --- | --- |
| [Tetris](../evidence/wep-tetris-vga88.png) | Separate VGA driver; not CGA |
| [Golf](../evidence/wep-golf.png) | Earlier WEP startup/dealt screen |
| [Tut's Tomb](../evidence/wep-tuts-tomb.png) | Earlier WEP startup |
| [FreeCell](../evidence/wep-freecell.png) | Earlier WEP startup |
| [Fuji Golf](../evidence/wep-fuji-golf.png) | Pack 3 clubhouse |
| [TetraVex](../evidence/wep-tetravex.png) | Earlier WEP startup |

The VB project also captured JIGSAWED, RATTLER and RODENT screens in separate earlier emulator sessions; those images are not committed in this repository and are **not evidence of this audit**.

## What still needs to be run

**Not yet tested on the specific uploaded edition:** Pack 1 Golf and Tetris; Pack 2 and Pack 3 IdleWild; all seven Pack 4 games; Best of SkiFree. **Four earlier failures need rechecking:** Pack 2 Stones; Best of Blackjack, Chips and RODENT (the last with the newly converted VBRUN100 runtime). Older launch-only results still need fuller testing before making a blanket pack-compatibility claim.

For each fresh run, record: exact pack/build, Windows 3.0 real-mode configuration, CPU core (V20/8088), video driver (CGA/VGA/TGA), whether the process actually reached a menu or interactive screen, input response, exit, memory/error conditions, 80186 audit warnings, and a captured image.

The `WM88X3` module-library method is documented in [WEP-LIBRARY.md](WEP-LIBRARY.md); the distinct Visual Basic converter, test rig and defaults are in [vbrun/](../vbrun/) and [its report](../vbrun/REPORT.md). **The two systems have not been verified as a single all-games installation.** The VB and WEPUTIL INT 3 handlers have a known unload-order limitation. Original Microsoft files, private disk images and uploaded pack media are not distributed by this repository.
