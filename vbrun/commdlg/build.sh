#!/bin/bash
# build.sh OUTDIR -- assemble the 8086 COMMDLG.DLL (nasm) and link it (mkne.py)
set -e
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:?usage: build.sh OUTDIR}; mkdir -p "$OUT"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cp "$HERE"/*.asm "$HERE"/*.inc "$T"/
(cd "$T" && nasm -f bin -O1 -o commdlg.bin commdlg.asm)
python3 "$HERE/mkne.py" "$T/commdlg.bin" "$T/commdlg.map" "$OUT/COMMDLG.DLL" "$HERE/commdlg.json"
