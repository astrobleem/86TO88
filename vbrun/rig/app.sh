#!/bin/bash
# app.sh DLLDIR APP.EXE [UNTIL] -- boot APP as shell on CGA and screenshot at UNTIL (default 50M).
# RODENT.EXE: starts, matches the protected-mode screen. RATTLER.EXE: starts, then
# "User defined error" (KNOWN, not investigated). Use '-' as APP with WIN_ARGS=C:\GAME\JIGSAWED.EXE
# to start Program Manager plus JIGSAWED (KNOWN: "Insufficient memory to run this application").
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
W=${WORK:-$PWD/work}; mkdir -p "$W"; A=$2; tag=$(basename "${A:-pm}" .EXE)
[ "$A" = - ] && S="" || S="--shell $A"
python3 "$HERE/build_disk.py" "$W/$tag.vhd" "$1" $S --win-args "${WIN_ARGS:-}" >/dev/null || exit 1
MARTY_PCSAMPLE=1000000 "$HERE/run.sh" "$W/$tag.vhd"
waitfor ${3:-50000000}; "$HERE/shot.sh" "$W/$tag.png"; echo "$W/$tag.png"
