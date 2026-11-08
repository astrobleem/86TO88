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
INST=$MARTYPC_DIR/install; BIN=$MARTYPC_DIR/target/release/martypc
[ -x "$BIN" ] || { echo "run.sh: $BIN not built" >&2; exit 1; }
LOGF=${MARTY_LOG:-/tmp/marty.log}
export DISPLAY=${DISPLAY:-:99}
pgrep Xvfb >/dev/null || { (Xvfb :99 -screen 0 1280x1024x24 >/dev/null 2>&1 &); sleep 2; }
pkill -x martypc; sleep 1
STAGE=$INST/media/hdds/cur.vhd
rm -f -- "$STAGE" "$INST/cur.toml"
cp -- "$VHD" "$STAGE" && cmp -s -- "$VHD" "$STAGE" || { echo "run.sh: staging $VHD -> $STAGE failed" >&2; rm -f -- "$STAGE"; exit 1; }
sed 's/^filename = "default_xtide.vhd"/filename = "cur.vhd"/; s/^#terminal_port = 0xE9/terminal_port = 0xE9/' \
  "$INST/martypc.toml" > "$INST/cur.toml" && grep -q '^filename = "cur.vhd"' "$INST/cur.toml" \
  || { echo "run.sh: could not write $INST/cur.toml" >&2; exit 1; }
: > "$LOGF" || { echo "run.sh: cannot write $LOGF" >&2; exit 1; }
cd "$INST" || exit 1
nohup "$BIN" --config_file cur.toml --base_dir . --machine-config-name ${MACHINE:-xt_win640} \
  --machine-config-overlays ${2:-ibm_cga,cpu_v20} --no_sound ${EXTRA:-} > "$LOGF" 2>&1 &
echo "booting $VHD" >&2
