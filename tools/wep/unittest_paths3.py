#!/usr/bin/env python3
"""Loader-read regressions for module lookup through short or absent directory prefixes.

Pass the same dir:original-file arguments as unittest_io3.py. Each path runs in
an independent emulator so a resident table from a previous path cannot mask a
lookup failure. Original game/helper binaries stay outside the repository.
"""
import os
from pathlib import Path
import subprocess
import sys

if len(sys.argv) < 2:
    raise SystemExit('usage: unittest_paths3.py 0:GAME.EXE [1:HELPER.DLL ...]')
script = Path(__file__).with_name('unittest_io3.py')
for prefix in ('C:\\G', 'C:\\GAME', '', 'C:\\WINDOWS\\SYSTEM'):
    print('OPEN_PREFIX =', repr(prefix), flush=True)
    env = dict(os.environ, OPEN_PREFIX=prefix)
    subprocess.run([sys.executable, str(script), *sys.argv[1:]], env=env, check=True)
print('PASS: short, normal, bare-name and long module paths')
