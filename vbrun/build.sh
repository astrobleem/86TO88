#!/bin/bash
# build.sh OUTDIR -- convert the user's VBRUN100.DLL and FIELD100.DLL with the current
# work-in-progress baseline. Extra converter switches can be passed in the environment
# (e.g. WRAPSTATS=1 for wrapper counters, read back with wstats.py from a memory dump).
set -e
: "${VBW_ORIG:?set VBW_ORIG to the directory holding the original VBRUN100.DLL and FIELD100.DLL}"
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:?usage: build.sh OUTDIR}; mkdir -p "$OUT"
FSHRINK=1 VBPROBE=0x200 FIXSEGS=${VB_FIXSEGS:-4,5,16} WRAP=@"$HERE/data/callees.json" WRAPMAP="$OUT/wrapmap.json" \
VBHEAPRES=0x100 VBHEAPGROW=1 TABGROW=1 CTXGROW=1 VBLHEAP=0x1000 VBLHEAP71=0x3000 VBLHEAP88=0x400 \
VBALLOCFIXED=1 FSW8087=1 GROWKEEP=1 \
  python3 "$HERE/conv.py" "$VBW_ORIG/VBRUN100.DLL" "$OUT/VBRUN100.DLL"
# FIELD100 (custom control): data segment 4 fixed, because VB keeps a far pointer to the
# control model that lives in it.
env -u WRAP -u WRAPSTATS FIXSEGS=4 python3 "$HERE/conv.py" "$VBW_ORIG/FIELD100.DLL" "$OUT/FIELD100.DLL" novb
# structural check of both outputs (segment table, relocations, entries, fast-load area)
[ "${KEEPFASTLOAD:-}" = 1 ] || for f in VBRUN100.DLL FIELD100.DLL; do
  r=$(python3 "$HERE/nevalid.py" "$OUT/$f" | tail -1); case "$r" in OK*) ;; *) echo "$f: $r" >&2; exit 1;; esac
done
