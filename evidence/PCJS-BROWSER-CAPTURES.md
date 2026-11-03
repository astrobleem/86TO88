# Fresh PCjs browser captures - 2026-11-03

These are genuine Chrome screenshots of the local 80286 / EGA / 640 KiB
judge fixture at source commit `bfb389b1959b0cf3762111c088a418e4eb9f2b95`.
They were cropped at capture time to the relevant guest window or console
output. No compositing, generated artwork, retouching or reconstructed VRAM
is used in these three images. Browser chrome and unrelated desktop content
are excluded.

| File | Frame | What it shows |
| --- | --- | --- |
| [Refusal](pcjs-browser-refusal.jpg) | 680 x 225 | The original Windows version refusal without loading the bridge |
| [Gameplay](pcjs-browser-gameplay.jpg) | 268 x 390 | Original Minesweeper with numbered/empty revealed cells and a question mark |
| [DOS suites](pcjs-browser-dos-tests.jpg) | 790 x 148 | Installed/verified specimen, `T88PASS` and `0123456789ABCDERT2PASS` |

The normal prepared disk SHA-256 is
`de9ec058a44090f13f7b6e47c647f09390fe0ee39c2333998a87281f402eb6aa`.
The gameplay image used that unmodified prepared disk.

The refusal control changed only the private disk's AUTOEXEC.BAT to set the
DOS path, enter the Windows directory and run `WIN /R WINMINE.EXE` without
loading WM88TSR. Its disk SHA-256 was
`06733311c15c240c8b55fd2eee7a3c2052fe896cf3f72978fe79b8012405b277`.

The DOS-output capture used the normal startup with a DOS `PAUSE` immediately
before the Windows command, after both real DOS suites passed. Its private
disk SHA-256 was
`52c2bc35f7ad21f7c909e3317717ea6ab562cc98c2bdbf580a94b44efa2c9d55`.
The normal fixture was rebuilt after capture. No Windows/game executable,
display driver, bridge or shim was changed for these controls. Generated
disk and ROM media remains private and outside the repository.

The main README now embeds these tightly framed images. The older 86Box
refusal/installation and DOSBox-X solved-board files remain historical
evidence; the fresh gameplay capture is not labeled as a solved board or
an 8088 validation.
