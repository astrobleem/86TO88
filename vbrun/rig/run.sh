#!/bin/bash
# run.sh VHD [OVERLAYS]  -- (re)start MartyPC (with trace-hooks.patch applied) on VHD.
# MARTYPC_DIR = MartyPC checkout (binary at target/release/martypc, configs under install/;
# copy emulator/martypc/xt_win640.toml into install/configs/machines/).
# Log (port 0xE9 output, XW/XR/PC/DUMPED lines) goes to ${MARTY_LOG:-/tmp/marty.log}.
# Fails (exit 1) instead of booting whatever disk was staged before if VHD can't be staged.
set -u
: "${MARTYPC_DIR:?set MARTYPC_DIR}"
[ $# -ge 1 ] || { echo "usage: run.sh VHD [OVERLAYS]" >&2; exit 2; }
VHD=$(readlink -f -- "$1") && [ -f "$VHD" ] || { echo "run.sh: no such disk image: $1" >&2; exit 1; }
# absolute, because the emulator is started from inside install/
MD=$(readlink -f -- "$MARTYPC_DIR") && [ -d "$MD" ] || { echo "run.sh: MARTYPC_DIR not found: $MARTYPC_DIR" >&2; exit 1; }
INST=$MD/install; BIN=$MD/target/release/martypc
[ -x "$BIN" ] || { echo "run.sh: $BIN not built" >&2; exit 1; }
LOGF=$(readlink -m -- "${MARTY_LOG:-/tmp/marty.log}")
export DISPLAY=${DISPLAY:-:99}
pgrep Xvfb >/dev/null || { (Xvfb :99 -screen 0 1280x1024x24 >/dev/null 2>&1 &); sleep 2; }
# stop a previous instance of this emulator binary only (not other martypc processes, e.g. one
# started from another checkout or a test's fake binary)
pkill -f -- "^$BIN( |\$)" && sleep 1
STAGE=$INST/media/hdds/cur.vhd
rm -f -- "$INST/cur.toml"
if [ -e "$STAGE" ] && [ "$VHD" -ef "$STAGE" ]; then
  :   # already the staged disk: boot it as is, never delete the input
else
  # copy beside the stage, verify, then rename over it: the old stage is only replaced by a
  # verified copy, and nothing is removed before that
  TMP=$STAGE.tmp.$$
  cp -- "$VHD" "$TMP" && cmp -s -- "$VHD" "$TMP" && mv -f -- "$TMP" "$STAGE" \
    || { echo "run.sh: staging $VHD -> $STAGE failed" >&2; rm -f -- "$TMP"; [ -e "$STAGE" ] && ! [ "$VHD" -ef "$STAGE" ] && rm -f -- "$STAGE"; exit 1; }
fi
sed 's/^filename = "default_xtide.vhd"/filename = "cur.vhd"/; s/^#terminal_port = 0xE9/terminal_port = 0xE9/' \
  "$INST/martypc.toml" > "$INST/cur.toml" && grep -q '^filename = "cur.vhd"' "$INST/cur.toml" \
  || { echo "run.sh: could not write $INST/cur.toml" >&2; exit 1; }
: > "$LOGF" || { echo "run.sh: cannot write $LOGF" >&2; exit 1; }
cd "$INST" || exit 1
nohup "$BIN" --config_file cur.toml --base_dir . --machine-config-name ${MACHINE:-xt_win640} \
  --machine-config-overlays ${2:-ibm_cga,cpu_v20} --no_sound ${EXTRA:-} > "$LOGF" 2>&1 &
PID=$!
sleep ${MARTY_START_CHECK:-2}
kill -0 "$PID" 2>/dev/null || { echo "run.sh: emulator exited at startup; log tail:" >&2; tail -5 "$LOGF" >&2; exit 1; }
echo "booting $VHD (pid $PID)" >&2
