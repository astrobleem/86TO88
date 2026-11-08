#!/bin/bash
# shot.sh OUT.png -- capture the Xvfb screen holding the MartyPC window
DISPLAY=${DISPLAY:-:99} import -window root "$1" 2>/dev/null
