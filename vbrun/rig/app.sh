#!/bin/bash
# app.sh DLLDIR APP.EXE [UNTIL] -- boot APP as shell on CGA and screenshot at UNTIL (default 50M).
# RODENT.EXE: starts, matches the protected-mode screen. RATTLER.EXE: with the fast-load fix
# the attract screen runs (the earlier "User defined error" came from FIELD100 seg 4 being copied
# from the wrong memory); one earlier run stopped at ~96M (BIOS F000:F3AD, odd SP); with the
# dispatcher wrap (443d57b) a run reached 131M with the snake moving and the score counting.
# Use '-' as APP with WIN_ARGS=C:\GAME\JIGSAWED.EXE to start Program Manager plus JIGSAWED.
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"; A=$2; tag=$(basename "${A:-pm}" .EXE)
[ "$A" = - ] && S="" || S="--shell $A"
python3 "$HERE/build_disk.py" "$W/$tag.vhd" "$1" $S --win-args "${WIN_ARGS:-}" >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 "$HERE/run.sh" "$W/$tag.vhd"
waitfor ${3:-50000000}; "$HERE/shot.sh" "$W/$tag.png"; echo "$W/$tag.png"
