#!/bin/bash
# run.sh VHD [OVERLAYS]  -- (re)start MartyPC (with trace-hooks.patch applied) on VHD.
# MARTYPC_DIR = MartyPC checkout (binary at target/release/martypc, configs under install/;
# copy emulator/martypc/xt_win640.toml into install/configs/machines/).
# Log (port 0xE9 output, XW/PC/DUMPED lines) goes to ${MARTY_LOG:-/tmp/marty.log}.
: "${MARTYPC_DIR:?set MARTYPC_DIR}"
export DISPLAY=${DISPLAY:-:99}
pgrep Xvfb >/dev/null || { (Xvfb :99 -screen 0 1280x1024x24 >/dev/null 2>&1 &); sleep 2; }
pkill -x martypc; sleep 1
cd "$MARTYPC_DIR/install"
cp "$1" media/hdds/cur.vhd
sed 's/^filename = "default_xtide.vhd"/filename = "cur.vhd"/; s/^#terminal_port = 0xE9/terminal_port = 0xE9/' martypc.toml > cur.toml
nohup ../target/release/martypc --config_file cur.toml --base_dir . --machine-config-name ${MACHINE:-xt_win640} \
  --machine-config-overlays ${2:-ibm_cga,cpu_v20} --no_sound $EXTRA > ${MARTY_LOG:-/tmp/marty.log} 2>&1 &
