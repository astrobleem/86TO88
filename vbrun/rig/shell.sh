#!/bin/bash
# shell.sh DLLDIR PUZ.BMP [SHELL] -- CGA/V20, SHELL (default MSDOS.EXE) started with
# 'WIN /R C:\GAME\JIGSAWED.EXE': dismiss About, open PUZ.BMP, Fast Solve, then Alt+F4 and
# check that the shell is still there.  NOPUZ=1: About, Alt+F4 (JIGSAWED), Alt+F4 + Enter
# (end the Windows session from the shell).
# Results so far (CGA/V20, curD = default build): About, Open and Scramble work beside MS-DOS
# Executive; play then ends in "System Error / Terminating current application" or a runaway
# when seg 2 (19K + 0xC42-byte relocation buffer) cannot be reloaded.  Closing JIGSAWED:
# default build calls through a stale far pointer into the moved app DGROUP (83:0158 ->
# FFEF:FFF0); with APPDSLOCK=1 one run closed cleanly and ended Windows, one hit
# "Divide By Zero" during termination (the shell survived).  Screenshots: WORK/sh_*.png.  Kernel addresses in
# MARTY_XW are for this disk layout (KERNEL code at 1093 with MS-DOS Executive).
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"; SH=${3:-MSDOS.EXE}
python3 "$HERE/build_disk.py" "$W/sh.vhd" "$1" --shell "$SH" --win-args 'C:\GAME\JIGSAWED.EXE' "$2=PUZ.BMP" >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 MARTY_XW="${SH_XW:-GA=1093:0935,GRA=1093:0966}" "$HERE/run.sh" "$W/sh.vhd" || exit 1
waitfor 72000000; "$HERE/shot.sh" "$W/sh_1_about.png"; click; key Return
if [ -n "${NOPUZ:-}" ]; then   # NOPUZ=1: just close JIGSAWED, then the shell
  after 5000000; key alt+F4; after 30000000; "$HERE/shot.sh" "$W/sh_5_exit.png"
  key alt+F4; after 20000000; "$HERE/shot.sh" "$W/sh_6_shell_close.png"
  key Return; after 30000000; "$HERE/shot.sh" "$W/sh_7_left_windows.png"; grep -a "^PC" "$LOG" | tail -3; exit 0
fi
after 3000000; key ctrl+o
after 32000000; "$HERE/shot.sh" "$W/sh_2_open.png"; key Down
after 1500000; key Down
after 2500000; key Return
after 40000000; "$HERE/shot.sh" "$W/sh_3_scrambled.png"
key ctrl+f; after 25000000; "$HERE/shot.sh" "$W/sh_4_solved.png"
key alt+F4; after 30000000; "$HERE/shot.sh" "$W/sh_5_exit.png"
key alt+F4; after 20000000; "$HERE/shot.sh" "$W/sh_6_shell_close.png"
grep -a "^PC" "$LOG" | tail -3
