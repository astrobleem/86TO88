#!/bin/bash
# exit.sh DLLDIR -- CGA, JIGSAWED as shell: dismiss About, Alt+F4, watch for 100M instructions.
# KNOWN FAILURE (JIGSAWED as the shell only): the kernel returns from 0FA7:0092 to a garbage
# address read from the app's stack (traced 0466:0466, then A750:xxxx above 640K). Stock files
# in protected mode with JIGSAWED as shell also end in "UAE - Terminating current application".
# Closing JIGSAWED started from MS-DOS Executive works (rig/shell.sh with NOPUZ=1).
# MARTY_RING=300000:A000:C000 dumps the last 300000 instructions if CS enters A000-BFFF.
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"
python3 "$HERE/build_disk.py" "$W/exit.vhd" "$1" --shell JIGSAWED.EXE >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 MARTY_XW="GA=0FA7:0935" "$HERE/run.sh" "$W/exit.vhd"
waitfor 47000000; click; key Return; after 3000000; key alt+F4
after 100000000; "$HERE/shot.sh" "$W/exit.png"
grep -a RING-TRIGGERED "$LOG" && echo "runaway CPU (see ring dump in $LOG)"
