# Entertainment Pack: preliminary MartyPC 8088 runs

These are individual, incomplete experiments, not completed compatibility results. None has a verified player move. Additional runs and dependency isolation are needed.

## Setup and evidence

MartyPC 0.5.0 source, configured as an IBM XT with its emulated **8088**, 640 KiB, XT-IDE, CGA, DOS, and Windows 3.0 real mode. A locally modified headless frontend ran the machine, injected keyboard events, and saved video-card framebuffers. The PNGs are direct reconstructions of those emulator framebuffers; they are not desktop screenshots or photographs of physical hardware. No speed comparison is implied. The game media and Windows image are private and are not included in the repository.

Pack 1 and 4 used the current WM88X3 resident bridge with independently generated per-pack module libraries. The test disk also contained files from a pre-existing test fixture; this and multiple bridge mechanisms require isolation before attributing failures. The test used fixed delays and only one attempt per title. An unchanged screen after an input does not establish whether the input was received or whether the game failed.

| Edition and title | Observation on 8088 | Evidence |
| --- | --- | --- |
| Pack 1 Golf | Board appeared, F2 produced a different deal, and Alt+F4 returned to MS-DOS Executive. No card move verified. | [initial](../evidence/wep-marty-8088/pack1-golf.png), [new deal](../evidence/wep-marty-8088/pack1-golf-new-deal.png) |
| Pack 1 Cruel | Board appeared, F2 produced a different deal, and Alt+F4 returned to MS-DOS Executive. No card move verified. | [initial](../evidence/wep-marty-8088/pack1-cruel.png), [new deal](../evidence/wep-marty-8088/pack1-cruel-new-deal.png), [exit](../evidence/wep-marty-8088/pack1-cruel-exit.png) |
| Pack 1 Pegged | Board appeared and Alt+F4 returned to MS-DOS Executive. No peg move verified. | [board](../evidence/wep-marty-8088/pack1-pegged.png), [exit](../evidence/wep-marty-8088/pack1-pegged-exit.png) |
| Pack 1 Tetris | Reported insufficient display resolution on CGA; no gameplay. | [message](../evidence/wep-marty-8088/pack1-tetris.png) |
| Pack 4 Chip's Challenge | Windows reported not enough memory to run CHIPS in this setup. No cause established. | [message](../evidence/wep-marty-8088/pack4-chips.png) |
| Pack 4 Maxwell's Maniac | Board appeared after F2; no game move or clean exit verified. | [board](../evidence/wep-marty-8088/pack4-maxwell.png) |

TicTactics displayed a board, Taipei displayed its splash screen, and other attempts were inconclusive at the capture times. The separate [DOSBox-X diagnostics](WEP-FRESH-DOSBOXX.md) used an 8086 configuration and should not be conflated with these 8088 runs. In particular, Pegged reached its board here despite the earlier DOSBox-X attempt failing; neither single attempt establishes a general compatibility verdict.

## Broader first-pass attempts

All 44 inventory entries received a separate fixed-time 8088 launch attempt, using Pack 1, 2, 3, 4, or Best of media as appropriate. This is **not** 44 verified startups or playthroughs. The harness typed a name into MS-DOS Executive's Run dialog, waited, captured a frame, sent F2, captured again, sent Alt+F4, and captured a final frame. Some titles were still loading when the latter commands arrived. An unchanged Executive display or a black display is inconclusive. IdleWild is a screen saver rather than a game; F2 is not a meaningful universal interaction.

**Important test-setup defect:** Pack 2, Pack 3 and Best of were built with the converted WEPUTIL/FIELD runtime in SYSTEM while the generated module libraries were analyzed from the original pack DLLs. That can produce a module-to-binary mismatch, and the converted DLL may also be the wrong version for a title. In fact, Pack 3 and Best of Tetravex asked for a newer WEPUTIL.DLL. The separate WM88X3 and VB conversion mechanisms also have not been validated together as one installation. These runs must be repeated with matching dependencies; do not treat their errors as established 86TO88 defects.

| Edition | First-pass observations, restricted to what the frames show |
| --- | --- |
| Pack 2 | FreeCell and Tut's Tomb drew partial deals late in the capture sequence; Pipe Dream drew its window and returned to Executive after Alt+F4. Stones reported a stone-style DLL problem. IdleWild, Jigsawed, Rattler and Rodent were inconclusive at the capture times. None has verified gameplay. |
| Pack 3 | Fuji Golf requested its DAT file in the Windows directory; Klotski showed a welcome prompt; Life Genesis showed its grid and changed screen after F2, then returned to Executive; TriPeaks showed a player prompt; WordZap showed its title and game setup, then returned to Executive. SkiFree and IdleWild were inconclusive. Tetravex requested a newer WEPUTIL.DLL. No move verified. |
| Best of | Golf showed a board, changed deal after F2, and returned to Executive; Pipe Dream showed its window and returned to Executive; FreeCell and Tut's Tomb were still dealing; TriPeaks showed a player prompt; Tetris reported inadequate display resolution; Taipei showed a splash screen; Tetravex requested a newer WEPUTIL.DLL. Blackjack and JezzBall displayed corruption; Chips, Rodent and SkiFree were inconclusive at the capture times. No move verified. |

Each contact-sheet row shows initial, after-F2, and after-Alt+F4 frames from a single isolated emulator run. The labels identify the pack and executable, not a compatibility status. Pack 1/4 sheets also contain the separately attempted Best of Rodent. The latter sheets are generated from the raw emulator video buffer and reduced in size for comparison:

- [Pack 1/4 sheet 1](../evidence/wep-marty-8088/comparison-part0.png), [sheet 2](../evidence/wep-marty-8088/comparison-part1.png), [sheet 3](../evidence/wep-marty-8088/comparison-part2.png), [sheet 4](../evidence/wep-marty-8088/comparison-part3.png)
- [Pack 2/3 and Best of sheet 1](../evidence/wep-marty-8088/final-0.png), [2](../evidence/wep-marty-8088/final-1.png), [3](../evidence/wep-marty-8088/final-2.png), [4](../evidence/wep-marty-8088/final-3.png), [5](../evidence/wep-marty-8088/final-4.png), [6](../evidence/wep-marty-8088/final-5.png), [7](../evidence/wep-marty-8088/final-6.png), [8](../evidence/wep-marty-8088/final-7.png).

After copying FUJIGOLF.DAT into the Windows directory, a separate retry reached the [Fuji Golf clubhouse](../evidence/wep-marty-8088/pack3-fuji-dat-retry.png); the helper DLL mismatch still applies and no gameplay was verified. In two separate Pegged mouse experiments, injected mouse movement placed the cursor on the board but the subsequent captured frame was black. The cause has not been isolated and no move was verified.
