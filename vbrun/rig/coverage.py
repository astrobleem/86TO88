#!/usr/bin/env python3
"""coverage.py LOG MODULE... -- map MartyPC's 80186-opcode reports (MARTY_W186=1, V20 core)
back to module:segment:offset.

Each 'W186 CS:IP b0 b1 .. b7 iN' line is an 80186/V20-only opcode that executed. Code
segments start at offset 0 of their block, so IP is the offset inside the segment; the
segment is found by matching the reported bytes at that offset in the given NE files (the
converted DLLs, the game, the Windows modules). Prints one line per distinct site with the
number of executions, the first instruction count and every matching module segment, then
a summary. Exit status 1 when any site matched one of the modules marked with a leading '!'
(the converter's outputs, which must be 80186-free)."""
import re, struct, sys, os, collections

def segments(path):
    d = open(path, 'rb').read()
    if d[:2] != b'MZ': return []
    ne = struct.unpack_from('<I', d, 0x3c)[0]
    if d[ne:ne + 2] != b'NE': return []
    n, st, al = (struct.unpack_from('<H', d, ne + o)[0] for o in (0x1c, 0x22, 0x32))
    out = []
    for i in range(n):
        o, l, f, _ = struct.unpack_from('<HHHH', d, ne + st + 8 * i)
        if o and not f & 1:
            out.append((i + 1, d[o << al:(o << al) + (l or 0x10000)]))
    return out

def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    strict = {os.path.basename(a[1:]).upper() for a in argv[2:] if a.startswith('!')}
    mods = {}
    for a in argv[2:]:
        p = a.lstrip('!'); mods[os.path.basename(p).upper()] = segments(p)
    hits = collections.OrderedDict()
    for line in open(argv[1], 'rb').read().decode('latin1').splitlines():
        m = re.match(r'W186 ([0-9A-F]{4}):([0-9A-F]{4}) ((?:[0-9A-F]{2} ?){8}) i(\d+)', line)
        if not m: continue
        ip = int(m.group(2), 16); bs = bytes.fromhex(m.group(3).replace(' ', ''))
        k = (ip, bs)
        if k not in hits: hits[k] = [0, int(m.group(4)), set()]
        hits[k][0] += 1; hits[k][2].add(m.group(1))
    bad = 0; unknown = 0
    for (ip, bs), (cnt, first, css) in hits.items():
        where = []
        for name, segs in mods.items():
            for n, c in segs:
                if c[ip:ip + len(bs)] == bs or (len(c) - ip < len(bs) and c[ip:] == bs[:len(c) - ip] and len(c) > ip):
                    where.append('%s %d:%04X' % (name, n, ip))
        if not where: unknown += 1
        if any(w.split()[0] in strict for w in where): bad += 1
        print('%5d x  first i%-11d %s  %s  [%s]' % (cnt, first, bs.hex(' '), ', '.join(where) or 'not in the given modules',
                                                   ' '.join(sorted(css))))
    print('%d distinct sites, %d in converted modules, %d not matched' % (len(hits), bad, unknown))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
