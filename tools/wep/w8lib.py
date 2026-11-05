#!/usr/bin/env python3
"""w8lib.py - WM88X3 module library tool.
  w8lib.py auto  LIB GAME.EXE...   analyze each EXE plus the helper DLL/VBX it pulls in (found beside the EXE), add the modules
  w8lib.py add   LIB FILE [dir]    analyze one NE file (dir 0=WINDOWS, 1=WINDOWS\\SYSTEM) and add it as a stand-alone module
  w8lib.py list  LIB               show the library
  w8lib.py check LIB               verify format, and that no game needs two modules that conflict
Each module is LIB\\BASE.W8x (x = first letter of the file extension); LIB\\GAMES.TXT records which modules each game uses.
Trap keys (vector, segment offset) are allocated so that all modules of one game are collision-free (hard rule).
Modules of different games may collide; such pairs are recorded as conflicts in the image and the TSR drops the
conflicting resident module when it loads the other one."""
import sys, os, struct, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import gen_profile as G

HDR = 66
sem = lambda e: (e['type'], e['reg'], e['srcreg'], e['imm'], e['len'])
ccsem = lambda e: sem(e) + (e['reg'], e['srcreg'])
def keyof(e): return (7, e['segoff'], ccsem(e)) if e['type'] in (5, 6) else (e['vec'], e['segoff'], sem(e))

def image_name(name):
    base, ext = name.rsplit('.', 1)
    return f"{base[:8]}.W8{ext[0].upper()}"

def read_image(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'W8M1', path
    n, nconf, _ = struct.unpack_from('<HBB', d, 4)
    assert len(d) == HDR + 12 * n + 2 * nconf, (path, len(d), n, nconf)
    nl = d[40]
    rec = dict(name=d[41:41 + nl].decode(), dir=d[53], size=struct.unpack_from('<HH', d, 54), crc=struct.unpack_from('<HH', d, 58))
    sites = []
    for i in range(n):
        segoff, typ, reg, imm, ln, src, fl, fh, vec = struct.unpack_from('<HBBHBBHBB', d, HDR + 12 * i)
        sites.append(dict(segoff=segoff, type=typ, reg=reg, imm=imm, len=ln, srcreg=src, foff=fl | fh << 16, vec=vec & 7))
    conf = list(struct.unpack_from(f'<{nconf}H', d, HDR + 12 * n))
    return rec, sites, conf, d[:HDR + 12 * n]

def lib_images(lib, skip=None):
    out = {}
    for f in sorted(pathlib.Path(lib).glob('*.W8?')):
        if skip and f.name.upper() == skip.upper(): continue
        out[f.name.upper()] = read_image(f)
    return out

def games(lib):
    g = {}
    p = pathlib.Path(lib) / 'GAMES.TXT'
    if p.exists():
        for ln in p.read_text().splitlines():
            if ':' in ln:
                k, v = ln.split(':', 1); g[k.strip()] = v.split()
    return g

def save_games(lib, g):
    os.makedirs(lib, exist_ok=True)
    (pathlib.Path(lib) / 'GAMES.TXT').write_text(''.join(f"{k}: {' '.join(v)}\n" for k, v in sorted(g.items())))

def coreq(lib, fn, extra=()):
    s = set(extra)
    for mods in games(lib).values():
        if fn in mods: s |= set(mods)
    s.discard(fn)
    return s

def make_body(mod, entries, imgs, fn, must):
    """allocate vectors against the library; returns image body (no conflict list)"""
    for e in entries: e['mod'] = 0
    owners = [collections.defaultdict(list) for _ in range(8)]      # vec -> segoff -> [(fn, sem)]
    for ofn, (rec, sites, conf, body) in imgs.items():
        for e in sites:
            if e['type'] == 8: continue
            owners[7 if e['type'] in (5, 6) else e['vec']][e['segoff']].append((ofn, ccsem(e) if e['type'] in (5, 6) else sem(e)))
    # one vector per SITE (not per segment): only sites that share a segment offset need distinct vectors
    for e in sorted((e for e in entries if e['type'] not in (5, 6, 8)), key=lambda e: e['segoff']):
        best = None
        for v in range(7):
            hit = set(); bad = False
            for ofn, sm in owners[v].get(e['segoff'], []):
                if sm != sem(e):
                    hit.add(ofn)
                    if ofn in must or ofn == fn: bad = True
            if bad: continue
            if best is None or len(hit) < len(best[1]): best = (v, hit)
            if not hit: break
        if best is None:
            raise SystemExit(f"{mod['name']}: no vector for site at offset {e['segoff']:#x} (more than 7 clashing sites at one offset)")
        e['vec'] = best[0]; owners[best[0]][e['segoff']].append((fn, sem(e)))
    for e in entries:
        if e['type'] in (5, 6):
            for ofn, sm in owners[7].get(e['segoff'], []):
                if sm != ccsem(e) and ofn in must:
                    raise SystemExit(f"{mod['name']}: INT 3 key {e['segoff']:#x} collides with {ofn}, which the same game needs resident")
            owners[7][e['segoff']].append((fn, ccsem(e))); e['vec'] = 7
        elif e['type'] == 8: e['vec'] = 7
    pbyte = {}
    for e in entries:
        if e['type'] == 8: continue
        pbyte[e['seg'], e['segoff']] = 0xCC if e['type'] in (5, 6) else 0xCD
        if e['type'] not in (5, 6): pbyte[e['seg'], e['segoff'] + 1] = 0xF8 + e['vec']
    for e in entries:
        if e['type'] in (5, 6):
            base = 3 if e['type'] == 5 else 1
            if e['reg'] and ((e['seg'], e['segoff'] + base) in pbyte): e['reg'] = pbyte[e['seg'], e['segoff'] + base]
            if e['srcreg'] and ((e['seg'], e['segoff'] + base + 1) in pbyte): e['srcreg'] = pbyte[e['seg'], e['segoff'] + base + 1]
    entries.sort(key=lambda e: (e['vec'], e['segoff']))
    vtab = []; start = 0
    for v in range(8):
        n = sum(1 for e in entries if e['vec'] == v); vtab.append((start, n)); start += n
    out = bytearray(b'W8M1') + struct.pack('<HBB', len(entries), 0, 0)
    for s_, c_ in vtab: out += struct.pack('<HH', s_, c_)
    nm = mod['name'].encode()[:12]
    out += struct.pack('<B12sBHHHH', len(nm), nm.ljust(12, b'\0'), mod['dir'], mod['size'] & 0xFFFF, mod['size'] >> 16, mod['crc'] & 0xFFFF, mod['crc'] >> 16)
    offs = []
    for e in entries:
        offs.append(e['foff'])
        if e['type'] not in (5, 6): offs.append(e['foff'] + 1)
    out += struct.pack('<HH', min(offs) >> 8, max(offs) >> 8)
    for e in entries:
        out += struct.pack('<HBBHBBHBB', e['segoff'], e['type'], e['reg'], e['imm'], e['len'], e['srcreg'], e['foff'] & 0xFFFF, e['foff'] >> 16, e['vec'])
    assert len(out) == HDR + 12 * len(entries)
    return bytes(out)

def rebuild_conflicts(lib):
    """recompute every module's conflict list (modules with a differing meaning at the same trap key) and rewrite the images"""
    imgs = lib_images(lib)
    keys = {}
    for fn, (rec, sites, conf, body) in imgs.items():
        keys[fn] = {}
        for e in sites:
            if e['type'] == 8: continue
            keys[fn][(7 if e['type'] in (5, 6) else e['vec'], e['segoff'])] = ccsem(e) if e['type'] in (5, 6) else sem(e)
    ident = {fn: imgs[fn][0]['crc'][0] for fn in imgs}
    pairs = collections.defaultdict(set)
    fns = sorted(imgs)
    for i, a in enumerate(fns):
        for b in fns[i + 1:]:
            ka, kb = keys[a], keys[b]
            small, big = (ka, kb) if len(ka) < len(kb) else (kb, ka)
            if any(k in big and big[k] != v for k, v in small.items()):
                pairs[a].add(b); pairs[b].add(a)
    for fn in fns:
        ids = sorted({ident[o] for o in pairs[fn]})
        body = bytearray(imgs[fn][3]); body[6] = len(ids)
        (pathlib.Path(lib) / fn).write_bytes(bytes(body) + b''.join(struct.pack('<H', i) for i in ids))
    return pairs

def add(lib, path, d=1, quiet=False, must=()):
    os.makedirs(lib, exist_ok=True)
    mods, entries = G.collect([(d, path)])
    name = mods[0]['name']; fn = image_name(name)
    if not entries:
        p = pathlib.Path(lib) / fn
        if p.exists(): p.unlink()
        if not quiet: print(f"  {name}: no 80186 code - nothing to patch (no library entry)")
        return None
    imgs = lib_images(lib, skip=fn)
    must = set(must) | coreq(lib, fn)
    body = make_body(mods[0], entries, imgs, fn, must)
    (pathlib.Path(lib) / fn).write_bytes(body)
    pairs = rebuild_conflicts(lib)
    c = collections.Counter(e['type'] for e in entries)
    if not quiet:
        cf = f", conflicts with {sorted(pairs[fn])}" if pairs[fn] else ""
        print(f"  {name}: {len(entries)} sites {dict(sorted(c.items()))} -> {fn} ({(pathlib.Path(lib)/fn).stat().st_size} bytes){cf}")
    return fn

def add_game(lib, exe):
    specs = G.auto_specs(exe, pathlib.Path(exe).parent)
    gname = pathlib.Path(exe).name.upper()
    print(f"{gname}: {len(specs)} module(s)")
    fns = []
    for d, p in specs:
        mods, entries = G.collect([(d, p)])
        if entries: fns.append(image_name(mods[0]['name']))
    g = games(lib); g[gname] = fns; save_games(lib, g)        # record the game's module set first: it becomes the co-residence rule
    for d, p in specs: add(lib, p, d)

def listing(lib):
    imgs = lib_images(lib); g = games(lib)
    for fn, (rec, sites, conf, body) in imgs.items():
        c = collections.Counter(e['type'] for e in sites)
        print(f"  {fn:12} {rec['name']:14} {len(sites):5} sites {HDR + 12*len(sites) + 2*len(conf):6} B  conflicts {len(conf)}  types {dict(sorted(c.items()))}")
    print(f"{len(imgs)} modules, {sum(HDR + 12*len(v[1]) + 2*len(v[2]) for v in imgs.values())} bytes; games: {len(g)}")
    for k, v in sorted(g.items()): print(f"    {k:14} {' '.join(v) if v else '(nothing to patch)'}")

def check(lib):
    imgs = lib_images(lib); bad = 0
    keys = {fn: {(7 if e['type'] in (5, 6) else e['vec'], e['segoff']): (ccsem(e) if e['type'] in (5, 6) else sem(e)) for e in v[1] if e['type'] != 8} for fn, v in imgs.items()}
    for game, mods in games(lib).items():
        mods = [m for m in mods if m in keys]
        for i, a in enumerate(mods):
            for b in mods[i + 1:]:
                for k, v in keys[a].items():
                    if k in keys[b] and keys[b][k] != v: print('CONFLICT within', game, a, b, k); bad += 1; break
    print('library OK' if not bad else f'{bad} conflicts')
    return bad

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'add': add(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 1)
    elif cmd == 'auto':
        for e in sys.argv[3:]: add_game(sys.argv[2], e)
    elif cmd == 'list': listing(sys.argv[2])
    elif cmd == 'check': sys.exit(1 if check(sys.argv[2]) else 0)
    else: print(__doc__)
