# sourced helpers: instruction-count waits and key injection for MartyPC under Xvfb
export DISPLAY=${DISPLAY:-:99}
LOG=${MARTY_LOG:-/tmp/marty.log}
ic(){ grep -ao 'i[0-9]*$' "$LOG" | tail -1 | tr -d i; }
waitfor(){ until [ "$(ic)" -gt "$1" ] 2>/dev/null; do sleep 3; done; }
after(){ local s; s=$(ic); waitfor $((s+$1)); }          # wait N more instructions
focus(){ xdotool windowfocus "$(xdotool search --name MartyPC | head -1)"; }
key(){ focus; xdotool key --delay 300 "$@"; }
click(){ focus; xdotool mousemove 500 400 click 1; sleep 0.5; }
