#!/usr/bin/env python3
"""Check Stones' formatted style-DLL dependencies using a private extracted pack."""
import pathlib
import re
import sys
import gen_profile as G

pack = pathlib.Path(sys.argv[1])
expected = {p.name.upper() for p in pack.iterdir()
            if re.fullmatch(r'STONEE?[0-9]{2}\.DLL', p.name.upper())}
assert expected, 'No private Stones style DLLs found'
specs = G.auto_specs(pack / 'STONES.EXE', pack)
actual = {pathlib.Path(p).name.upper() for _, p in specs}
assert expected <= actual, (expected - actual)
for name in sorted(expected):
    src = next(p for p in pack.iterdir() if p.name.upper() == name)
    _, entries = G.collect([(1, str(src))])
    flags = next(e for e in entries if e['type'] == 8)
    assert flags['imm'] & 8 == 0, (name, flags)
    print(name, 'discovered; real-mode header patch present')
print('PASS:', len(expected), 'formatted style DLL dependencies')
