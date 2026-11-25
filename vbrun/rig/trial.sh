#!/bin/bash
# trial.sh DLLDIR TAG [UNTIL_ICOUNT] -- build a disk that runs JIGSAWED as shell, boot it with
# allocation tracing, run until UNTIL_ICOUNT instructions (or the log stalls), then summarise
# allocation failures, segment reloads per 10M instructions, LocalShrink calls, message boxes
# and the sampled stack. Env: VIDEO=cga|vga, DUMPAT=icount (memory dump to WORK/TAG.dump.bin),
# WORK=output dir (default ./work).
# The XW addresses are KERNEL seg1 = 0FA7 (GlobalAlloc 0935, GlobalReAlloc 0966, LocalShrink 6848)
# and USER seg1 MessageBox (2B55 with VGA, 29A7 with CGA) for this particular disk layout;
# they shift if DOS/AUTOEXEC or the driver set changes (check PC samples).
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/lib.sh"
D=$1; T=${2:?usage: trial.sh DLLDIR TAG [UNTIL]}; U=${3:-75000000}; V=${VIDEO:-cga}
W=${WORK:-$PWD/work}; mkdir -p "$W"
python3 "$HERE/build_disk.py" "$W/$T.vhd" "$D" --video $V --shell JIGSAWED.EXE >/dev/null || exit 1
[ $V = cga ] && MB=29A7:8FE1 || MB=2B55:8FE1
[ $V = cga ] && OVL=ibm_cga,cpu_v20 || OVL=ibm_vga,cpu_v20
MARTY_DUMP_AT=${DUMPAT:-0} MARTY_DUMP_FILE=$W/$T.dump.bin MARTY_PCSAMPLE=${PCS:-2000000} \
MARTY_XW="GA=0FA7:0935,GRA=0FA7:0966,LS=0FA7:6848,MB=$MB" "$HERE/run.sh" "$W/$T.vhd" $OVL
last=0; stall=0
while sleep 10; do
  n=$(ic); n=${n:-0}; [ "$n" -gt "$U" ] && break
  if [ "$n" = "$last" ]; then stall=$((stall+1)); [ $stall -gt 30 ] && break; else stall=0; fi; last=$n
done
cp "$LOG" "$W/$T.log"; "$HERE/shot.sh" "$W/$T.png"; echo "reached i$n"
python3 "$HERE/xwlog.py" "$W/$T.log"
