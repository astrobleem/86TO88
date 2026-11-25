#!/bin/bash
# build.sh OUTDIR -- assemble the 8086 COMMDLG.DLL (nasm) and link it (mkne.py); CDTEST=1 also
# builds CDTEST.EXE
set -e
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:?usage: build.sh OUTDIR}; mkdir -p "$OUT"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cp "$HERE"/*.asm "$HERE"/*.inc "$T"/
(cd "$T" && nasm -f bin -O1 -o commdlg.bin commdlg.asm)
python3 "$HERE/mkne.py" "$T/commdlg.bin" "$T/commdlg.map" "$OUT/COMMDLG.DLL" "$HERE/commdlg.json"
# CDTEST=1: also the test program that opens every dialog
if [ -n "${CDTEST:-}" ]; then
  (cd "$T" && nasm -f bin -O1 -o cdtest.bin cdtest.asm)
  python3 "$HERE/mkne.py" "$T/cdtest.bin" "$T/cdtest.map" "$OUT/CDTEST.EXE" "$HERE/cdtest.json"
fi
