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
