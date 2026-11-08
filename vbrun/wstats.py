"""Print the wrapper statistics block (WRAPSTATS=1 builds) from a 1 MB memory dump."""
import sys, struct
m = open(sys.argv[1], 'rb').read()
names = ['calls', 'unknown-caller (locked)', 'returned, caller segment unchanged',
         'returned, caller segment moved or reloaded', 'records abandoned by non-local exit',
         'matched by newest-record fallback', 'max nesting (records)', 'not hooked (record stack full)']
i = m.find(b'WSTATS')
while i >= 0:
    v = struct.unpack_from('<8H', m, i + 6)
    print('at %05x' % i)
    for n, x in zip(names, v):
        print('  %-45s %d' % (n, x // 10 if n.startswith('max') else x))
    i = m.find(b'WSTATS', i + 1)
