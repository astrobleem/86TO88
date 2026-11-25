#!/bin/bash
# coverage.sh OUTDIR DLLDIR APP 'STEPS' [VIDEO] -- 80186 coverage run: APP (from $VBW_ORIG) as the
# Windows shell on MartyPC's V20 core with MARTY_W186=1, so every 80186/V20-only opcode that
# executes is logged; then coverage.py maps the reports to module:segment:offset.
#   DLLDIR: the converted DLLs/VBX (build.sh output); *.VBX go to WINDOWS\SYSTEM
#   STEPS:  space-separated: +N waits N million instructions, @NAME takes OUTDIR/NAME.png,
#           anything else is an xdotool key (e.g. alt+g Escape F2 Right ctrl+o)
#   VIDEO:  cga (default) / vga / herc / ega, as build_disk.py --video
# Output: OUTDIR/run.log (MartyPC log), OUTDIR/*.png, OUTDIR/coverage.txt; exit status of
# coverage.py (1 when an executed 80186 opcode lies in a converted module).
# Environment: as build_disk.py (VBW_BASE, VBW_W30DRV, VBW_ORIG, ...); MARTYPC_DIR/DISPLAY select
# the MartyPC instance as for run.sh; OVERLAYS (default ibm_cga; cpu_v20 is added); END (default 0) extra million
# instructions after the steps; FILES extra SRC=DEST files for the disk.
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:?usage: coverage.sh OUTDIR DLLDIR APP STEPS [VIDEO]}; DLL=${2:?}; APP=${3:?}; STEPS=${4:-}
mkdir -p "$OUT"; export MARTY_LOG=$OUT/run.log; . "$HERE/lib.sh"
X=(); for v in "$DLL"/*.VBX; do [ -f "$v" ] && X+=("$v=WINDOWS/SYSTEM/$(basename "$v")"); done
for e in ${FILES:-}; do X+=("$e"); done   # FILES="SRC=DEST ..." extra files on C:
python3 "$HERE/build_disk.py" "$OUT/a.vhd" "$DLL" --video "${5:-cga}" --shell "$APP" "${X[@]}" >/dev/null || exit 2
MARTY_W186=1 MARTY_PCSAMPLE=1000000 "$HERE/run.sh" "$OUT/a.vhd" "${OVERLAYS:-ibm_cga},cpu_v20" 2>/dev/null || exit 2
until [ -n "$(ic)" ]; do sleep 2; done
for s in $STEPS; do
  case "$s" in
    +*) after $(( ${s#+} * 1000000 ));;
    @*) "$HERE/shot.sh" "$OUT/${s#@}.png";;
    *)  key "$s";;
  esac
done
[ "${END:-0}" -gt 0 ] && after $(( END * 1000000 ))
echo "steps done at $(ic)" > "$OUT/coverage.txt"
pkill -f "^$(readlink -f "$MARTYPC_DIR")/target/release/martypc( |\$)" 2>/dev/null
M=(); for f in "$DLL"/*.DLL "$DLL"/*.VBX; do [ -f "$f" ] && M+=("!$f"); done
for f in "$VBW_ORIG/$APP"; do [ -f "$f" ] && M+=("$f"); done
python3 "$HERE/coverage.py" "$MARTY_LOG" "${M[@]}" >> "$OUT/coverage.txt"; r=$?
tail -1 "$OUT/coverage.txt"; exit $r
