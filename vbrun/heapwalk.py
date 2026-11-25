"""Walk the Windows 3.0 real-mode global arena in a 1 MB memory dump.
Arena header (one paragraph before each block):
  +0 count(lock) +1 owner +3 size(paras) +5 flags +6 prev +8 next +0A handle
Usage: heapwalk.py dump.bin [module_seg ...]"""
import struct, sys, collections

def W(m, a): return struct.unpack_from('<H', m, a)[0]

def find_heap(m, hint=None):
    # find an arena whose next/prev links are mutually consistent, then walk back to the start
    def ok(s):
        a = s << 4; sz = W(m, a + 3); nx = W(m, a + 8); pv = W(m, a + 6)
        return 0 < s < 0xa000 and nx == s + sz + 1 and nx < 0xa000 and W(m, (nx << 4) + 6) == s
    start = None
    for s in ([hint] if hint else []) + list(range(0x0400, 0x9000)):
        if s and ok(s): start = s; break
    s = start; seen = set()
    while True:
        pv = W(m, (s << 4) + 6)
        if pv == s or pv in seen or pv == 0 or pv >= s: break
        if W(m, (pv << 4) + 8) != s: break
        seen.add(s); s = pv
    return s

def walk(m, first):
    blocks = []; s = first; seen = set()
    while s not in seen and s < 0xa000:
        seen.add(s); a = s << 4
        cnt = m[a]; owner = W(m, a + 1); size = W(m, a + 3); fl = m[a + 5]
        nx = W(m, a + 8); h = W(m, a + 10)
        blocks.append(dict(arena=s, seg=s + 1, size=size, owner=owner, lock=cnt, flags=fl, handle=h))
        if nx == s or nx <= s:
            # broken header: find the next arena whose prev points here
            cand = [t for t in range(s + 1, min(s + 0x1000, 0xa000)) if W(m, (t << 4) + 6) == s and W(m, (t << 4) + 8) > t]
            if not cand or blocks[-1]['size'] and False: break
            blocks[-1]['corrupt'] = True; blocks[-1]['size'] = cand[0] - s - 1
            s = cand[0]; continue
        s = nx
    return blocks

def module_segs(m, hexe):
    a = hexe << 4
    if m[a:a + 2] != b'NE': return None
    sto = W(m, a + 0x22); n = W(m, a + 0x1c)
    out = []
    for i in range(n):
        e = a + sto + 10 * i
        out.append(dict(num=i + 1, sector=W(m, e), len=W(m, e + 2), flags=W(m, e + 4),
                        minalloc=W(m, e + 6), handle=W(m, e + 8)))
    return out

def modname(m, hexe):
    a = hexe << 4
    rn = W(m, a + 0x26); ln = m[a + rn]
    return m[a + rn + 1:a + rn + 1 + ln].decode('latin1')

def report(fn, mods=(), quiet=False):
    m = open(fn, 'rb').read()
    first = find_heap(m)
    bl = walk(m, first)
    free = [b for b in bl if b['owner'] == 0]
    tot_free = sum(b['size'] for b in free) * 16
    largest = max((b['size'] for b in free), default=0) * 16
    owners = collections.Counter()
    for b in bl: owners[b['owner']] += b['size'] * 16
    res = dict(first=first, blocks=len(bl), free_bytes=tot_free, largest_free=largest,
               free_blocks=len(free), end=bl[-1]['arena'] + bl[-1]['size'] + 1 if bl else 0)
    names = {}
    for o in owners:
        try:
            names[o] = modname(m, o)
        except Exception:
            pass
    res['by_module'] = {names.get(o, '%04x' % o): v for o, v in owners.most_common()}
    segmap = {}
    for o, nm in names.items():
        if mods and nm not in mods: continue
        ms = module_segs(m, o)
        if not ms: continue
        byh = {b['handle']: b for b in bl if b['owner'] == o}
        byseg = {b['seg']: b for b in bl if b['owner'] == o}
        loaded = {}
        for s in ms:
            h = s['handle']
            b = byh.get(h) or byseg.get(h)          # fixed segments: handle == segment address
            if b: loaded[s['num']] = dict(addr=b['seg'], paras=b['size'], lock=b['lock'], flags=s['flags'])
        segmap[nm] = loaded
    res['segments'] = segmap
    return res, bl

if __name__ == '__main__':
    r, bl = report(sys.argv[1], tuple(sys.argv[2:]))
    bad=[b for b in bl if b.get('corrupt')]
    print('corrupt arena headers:', ['%04x' % b['arena'] for b in bad])
    print('heap first arena %04x end %04x blocks %d' % (r['first'], r['end'], r['blocks']))
    print('free %d bytes in %d blocks, largest %d' % (r['free_bytes'], r['free_blocks'], r['largest_free']))
    print('by owner:', {k: v for k, v in list(r['by_module'].items())[:12]})
    for nm, segs in r['segments'].items():
        tot = sum(v['paras'] for v in segs.values()) * 16
        print('%s: %d segments resident, %d bytes' % (nm, len(segs), tot))
        if len(sys.argv) > 2:
            print('  ', ' '.join('%d@%04x%s' % (k, v['addr'], 'L' if v['lock'] else '') for k, v in sorted(segs.items())))
