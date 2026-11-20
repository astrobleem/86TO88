#!/bin/bash
# build.sh OUTDIR -- convert the user's VBRUN100.DLL and FIELD100.DLL with the current
# work-in-progress baseline. Extra converter switches can be passed in the environment
# (e.g. WRAPSTATS=1 for wrapper counters, read back with wstats.py from a memory dump).
set -e
: "${VBW_ORIG:?set VBW_ORIG to the directory holding the original VBRUN100.DLL and FIELD100.DLL}"
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:?usage: build.sh OUTDIR}; mkdir -p "$OUT"
FSHRINK=1 VBPROBE=0x200 FIXSEGS=${VB_FIXSEGS:-4,5,16} WRAP=@"$HERE/data/callees.json" WRAPMAP="$OUT/wrapmap.json" \
VBHEAPRES=${VBHEAPRES-0x100} VBHEAPGROW=${VBHEAPGROW-1} TABGROW=${TABGROW-1} CTXGROW=${CTXGROW-1} CTXMIRROR=${CTXMIRROR-} VBLHEAP=0x1000 VBLHEAP71=${VBLHEAP71-0x3000} VBLHEAP88=${VBLHEAP88-0x400} \
VBALLOCFIXED=${VBALLOCFIXED-} VBHEAPSKIP4=${VBHEAPSKIP4-1} VBHEAPRES2=${VBHEAPRES2-0x400} APPDSLOCK=${APPDSLOCK-1} FSW8087=1 GROWKEEP=1 I186=${I186:-1} \
  python3 "$HERE/conv.py" "$VBW_ORIG/VBRUN100.DLL" "$OUT/VBRUN100.DLL"
# FIELD100 (custom control): data segment 4 fixed, because VB keeps a far pointer to the
# control model that lives in it.
env -u WRAP -u WRAPSTATS FIXSEGS=4 I186=${I186:-1} python3 "$HERE/conv.py" "$VBW_ORIG/FIELD100.DLL" "$OUT/FIELD100.DLL" novb
# structural check of both outputs (segment table, relocations, entries, fast-load area)
[ "${KEEPFASTLOAD:-}" = 1 ] || for f in VBRUN100.DLL FIELD100.DLL; do
  r=$(python3 "$HERE/nevalid.py" "$OUT/$f" --reviewed "$HERE/data/pushret-reviewed.json" | tail -1); case "$r" in OK*) ;; *) echo "$f: $r" >&2; exit 1;; esac
done
# WEPUTIL.DLL (Entertainment Pack helper imported by JIGSAWED, also used by non-VB games):
# only the 80186 rewrite, with its own INT 3 handler in its fixed data segment 3
# (WEP4UTIL.DLL, Entertainment Pack 4's version, has the same layout and gets the same treatment)
for f in WEPUTIL.DLL WEP4UTIL.DLL; do
  if [ "${I186:-1}" != 0 ] && [ -f "$VBW_ORIG/$f" ]; then
    env -u WRAP -u WRAPSTATS FIXSEGS= I186=1 I186HOME=3 I186WEPSEG=${I186WEPSEG-1} python3 "$HERE/conv.py" "$VBW_ORIG/$f" "$OUT/$f" novb
  fi
done
# Other custom controls (*.VBX: THREED, GAUGE, CMDIALOG from Entertainment Pack 4) and
# COMMDLG.DLL, when present: every data segment FIXED (VB keeps far pointers into them, like
# FIELD100), selector/offset references made through their own movable entries resolved
# (ORDSEL), no far-pointer table segment. They rely on VBRUN's INT 3 handler, like FIELD100.
# (names matched case-insensitively; outputs are upper case; one source per output name)
CTL=""; CTLSRC=()
while IFS= read -r p; do
  f=$(basename "$p" | tr a-z A-Z); case " $CTL " in *" $f "*) continue;; esac
  CTL="$CTL $f"; CTLSRC+=("$p")
  ds=$(python3 -c 'import struct,sys
d=open(sys.argv[1],"rb").read(); ne=struct.unpack_from("<I",d,0x3c)[0]; st,=struct.unpack_from("<H",d,ne+0x22); n,=struct.unpack_from("<H",d,ne+0x1c)
print(",".join(str(i+1) for i in range(n) if struct.unpack_from("<H",d,ne+st+8*i+4)[0]&1))' "$p")
  env -u WRAP -u WRAPSTATS FIXSEGS=$ds ORDSEL=1 TABSEGS= I186=${I186:-1} python3 "$HERE/conv.py" "$p" "$OUT/$f" novb
  r=$(python3 "$HERE/nevalid.py" "$OUT/$f" | tail -1); case "$r" in OK*) ;; *) echo "$f: $r" >&2; exit 1;; esac
done < <(find "$VBW_ORIG" -maxdepth 1 -type f \( -iname '*.vbx' -o -iname 'commdlg.dll' \) | sort)
# 8088: no 80186 instruction left in reachable code (I186=0 builds a V20/80186-only pair)
[ "${I186:-1}" = 0 ] || for f in VBRUN100.DLL FIELD100.DLL $(cd "$OUT" && ls WEPUTIL.DLL WEP4UTIL.DLL 2>/dev/null); do
  r=$(python3 "$HERE/i186.py" --check "$VBW_ORIG/$f" "$OUT/$f" | tail -1); [ "$r" = OK ] || { echo "$f: 80186 check: $r" >&2; exit 1; }
done
[ "${I186:-1}" = 0 ] || for p in "${CTLSRC[@]}"; do
  f=$(basename "$p" | tr a-z A-Z)
  r=$(python3 "$HERE/i186.py" --check "$p" "$OUT/$f" | tail -1); [ "$r" = OK ] || { echo "$f: 80186 check: $r" >&2; exit 1; }
done
