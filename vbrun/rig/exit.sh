#!/bin/bash
# exit.sh DLLDIR -- CGA, JIGSAWED as shell: dismiss About, Alt+F4, watch for 100M instructions.
# KNOWN FAILURE: ends on a white screen in the USER/KERNEL idle loop instead of leaving Windows;
# one longer session later ran into memory above 640K. MARTY_RING=20000:A000:C000 dumps the last
# 20000 instructions if CS enters A000-BFFF.
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"
python3 "$HERE/build_disk.py" "$W/exit.vhd" "$1" --shell JIGSAWED.EXE >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 MARTY_XW="GA=0FA7:0935" "$HERE/run.sh" "$W/exit.vhd"
waitfor 47000000; click; key Return; after 3000000; key alt+F4
after 100000000; "$HERE/shot.sh" "$W/exit.png"
grep -a RING-TRIGGERED "$LOG" && echo "runaway CPU (see ring dump in $LOG)"
