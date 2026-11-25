#!/bin/bash
# puzzle.sh DLLDIR PUZ.BMP -- CGA, JIGSAWED as shell, C:\PUZ.BMP present: dismiss the startup
# About box, Game>Open (Ctrl+O), pick PUZ.BMP, open it, then Hint (Ctrl+H), Fast Solve (Ctrl+F),
# Scramble (Ctrl+S). Screenshots go to WORK/puz_*.png. PUZ.BMP must fit CGA (<= 640x200;
# the app rejects larger pictures in protected mode too). Key timing is by instruction count.
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"
python3 "$HERE/build_disk.py" "$W/puz.vhd" "$1" --shell JIGSAWED.EXE "$2=PUZ.BMP" >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 MARTY_XW="GA=0FA7:0935,GRA=0FA7:0966,MB=29A7:8FE1" "$HERE/run.sh" "$W/puz.vhd"
waitfor 47000000; "$HERE/shot.sh" "$W/puz_1_about.png"; click; key Return
after 2000000; key ctrl+o
after 32000000; "$HERE/shot.sh" "$W/puz_2_open.png"; key Down
after 1500000; key Down
after 2500000; key Return
after 40000000; "$HERE/shot.sh" "$W/puz_3_scrambled.png"
key ctrl+h; after 10000000; "$HERE/shot.sh" "$W/puz_4_hint.png"
key ctrl+f; after 25000000; "$HERE/shot.sh" "$W/puz_5_solved.png"
key ctrl+s; after 20000000; "$HERE/shot.sh" "$W/puz_6_rescrambled.png"
grep -a "^XW MB" "$LOG" | head -3
