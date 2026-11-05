#!/usr/bin/env python3
"""gen_profile.py OUT.W8X dir0:FILE ... (dir 0=WINDOWS, 1=WINDOWS\\SYSTEM).  Builds a WM88X profile."""
import sys, struct, zlib, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import analyze_ne as A

def collect(specs):
    mods = []; entries = []   # entry dict: grp, segoff, type, reg, srcreg, imm, len, foff, mod
    for mi, (d, path) in enumerate(specs):
        data = open(path, 'rb').read()
        name = pathlib.Path(path).name.upper()
        mods.append(dict(name=name, dir=d, size=len(data), crc=zlib.crc32(data) & 0xFFFFFFFF))
        ne = A.NE(data); res = A.analyze(data)
        kmod = next((i + 1 for i, n_ in enumerate(imports_of(data)) if n_ == 'KERNEL'), 0)
        # expected-Windows-version stamp above 3.00 (3.1 binaries): rewrite to 3.00 in the read buffer
        nehdr = struct.unpack_from('<I', data, 0x3c)[0]
        if struct.unpack_from('<H', data, nehdr + 0x3E)[0] > 0x0300:
            entries.append(dict(mod=mi, seg=0, segoff=0xFFFF, type=8, reg=0, srcreg=0, imm=0x0300, len=2, foff=nehdr + 0x3E))
        # 'protected mode only' flag (NE flags 0x08): clear it so real-mode Windows 3.0 will load the module
        if data[nehdr + 0x0C] & 0x08:
            entries.append(dict(mod=mi, seg=0, segoff=0xFFFF, type=8, reg=0, srcreg=0, imm=data[nehdr + 0x0C] & ~0x08, len=1, foff=nehdr + 0x0C))
        for sg in res['segments']:
            seg = ne.segs[sg['seg'] - 1]; sb = ne.segdata(sg['seg'])
            relocs = seg['relocs']
            def rwidth(at): return 4 if at == 3 else (1 if at == 0 else 2)
            # chain nodes (non-additive relocs): bytes that the loader reads from the image
            chain = set(); nodes = {}
            for at, rf, ro, mi_, val in relocs:
                if rf & 4: 
                    for k in range(rwidth(at)): chain.add(ro + k)
                    nodes[ro] = (at, rf)
                    continue
                loc = ro; guard = 0
                while True:
                    for k in range(rwidth(at)): chain.add(loc + k)
                    nodes[loc] = (at, rf)
                    nxt = struct.unpack_from('<H', sb, loc)[0]
                    if nxt == 0xFFFF or guard > 5000: break
                    loc = nxt; guard += 1
            relocbytes = chain
            # real-mode gate: code that calls KERNEL.GetWinFlags (ordinal 132) and refuses to run unless WF_PMODE (bit 0) is set
            # -> NOP the following 'je' so it always continues as if in protected mode
            if kmod:
                for at, rf, ro, mi_, val in relocs:
                    if (rf & 3) != 1 or mi_ != kmod or val != 132: continue
                    loc = ro; guard = 0; locs = []
                    while True:
                        locs.append(loc)
                        nxt = struct.unpack_from('<H', sb, loc)[0]
                        if rf & 4 or nxt == 0xFFFF or guard > 500: break
                        loc = nxt; guard += 1
                    for loc in locs:
                        if loc < 1 or sb[loc - 1] != 0x9A: continue
                        b = bytes(sb[loc + 4: loc + 4 + 40])
                        for k in range(len(b) - 7):
                            tst = (b[k:k + 2] == b'\xA8\x01' and 2) or (b[k] == 0xF6 and b[k + 1] == 0x06 and b[k + 4] == 1 and 5) or \
                                  (b[k] == 0xF6 and 0xC0 <= b[k + 1] <= 0xC3 and b[k + 2] == 1 and 3) or (b[k:k + 2] == b'\xA9\x01' and b[k + 2] == 0 and 3)
                            if tst and b[k + tst] == 0x74:
                                off = loc + 4 + k + tst
                                entries.append(dict(mod=mi, seg=sg['seg'], segoff=0xFFFF, type=8, reg=0, srcreg=0, imm=0x9090, len=2, foff=seg['fo'] + off))
                                break
            def add(off, typ, reg, srcreg, imm, ln):
                entries.append(dict(mod=mi, seg=sg['seg'], segoff=off, type=typ, reg=reg, srcreg=srcreg, imm=imm, len=ln, foff=seg['fo'] + off))
            for s in sg['sites']:
                off, typ, ln = s['off'], s['type'], s['len']
                if typ == 0 and ln == 3 and (off + 1) in relocbytes:
                    assert nodes.get(off + 1, (0,))[0] in (2, 5), (name, hex(off))
                    ca = sb[off + 3] if (off + 3) not in relocbytes else 0
                    cb = sb[off + 4] if (off + 4) not in relocbytes and off + 4 < len(sb) else 0
                    add(off, 5, ca, cb, 0, 3)
                else:
                    assert not ({off, off + 1} & chain), ('chain/patch overlap', name, sg['seg'], hex(off))
                    assert not ({off, off + 1} & relocbytes) or typ == 0 and False, ('reloc in patched bytes', name, hex(off))
                    add(off, typ, s['reg'], s['srcreg'], s['imm'], ln)
            for u in sg['unsup']:
                raw = bytes.fromhex(u['raw']); off = u['off']
                if u['kind'] == 'unsup-leave':
                    ca = sb[off + 1] if off + 1 < len(sb) and (off + 1) not in relocbytes else 0
                    cb = sb[off + 2] if off + 2 < len(sb) and (off + 2) not in relocbytes else 0
                    assert off not in chain
                    add(off, 6, ca, cb, 0, 1)
                elif u['kind'] == 'unsup-mem-imul':
                    op, mrm = raw[0], raw[1]
                    mod_, rm = mrm >> 6, mrm & 7
                    if op != 0x6b or mod_ == 3:
                        print('  UNSUPPORTED', name, sg['seg'], hex(off), u['kind'], u['raw']); continue
                    if mod_ == 0:
                        if rm == 6: ea = 8; disp = struct.unpack_from('<H', raw, 2)[0]
                        else: ea = rm; disp = 0
                    elif mod_ == 1:
                        ea = rm; disp = raw[2] - 256 if raw[2] > 127 else raw[2]
                    else:
                        ea = rm; disp = struct.unpack_from('<H', raw, 2)[0]
                    imm8 = raw[-1]
                    assert not ({off, off + 1} & chain)
                    assert len(raw) < 16
                    add(off, 7, (mrm >> 3) & 7, imm8, disp & 0xFFFF, len(raw) | (ea << 4))
                else:
                    print('  UNSUPPORTED', name, sg['seg'], hex(off), u['kind'], u['raw'])
    return mods, entries

def build(specs, verbose=True):
    mods, entries = collect(specs)
    import os
    if os.environ.get('W8X_TYPES') is not None:
        keep = {int(x) for x in os.environ['W8X_TYPES'].split(',') if x}
        entries = [e for e in entries if e['type'] in keep]
    if os.environ.get('W8X_FILTER'):
        entries = [e for e in entries if eval(os.environ['W8X_FILTER'])]
    # drop modules with nothing to patch (no record, no CRC pass, no handle tracking) and renumber
    keep = sorted({e['mod'] for e in entries})
    remap = {m: i for i, m in enumerate(keep)}
    mods = [mods[m] for m in keep]
    for e in entries: e['mod'] = remap[e['mod']]
    # vector assignment: group = (mod,seg); INT sites need unique segoff per vector
    groups = collections.OrderedDict()
    for e in entries:
        if e['type'] not in (5, 6, 8): groups.setdefault((e['mod'], e['seg']), []).append(e)
    sem = lambda e: (e['type'], e['reg'], e['srcreg'], e['imm'], e['len'])
    vec_sites = [dict() for _ in range(7)]  # vec -> segoff -> sem
    vec_of = {}
    for g, es in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        for v in range(7):
            if all(vec_sites[v].get(e['segoff'], sem(e)) == sem(e) for e in es):
                for e in es: vec_sites[v][e['segoff']] = sem(e)
                vec_of[g] = v; break
        else:
            raise SystemExit(f'vector exhaustion for group {g}')
    cc = {}
    for e in entries:
        if e['type'] in (5, 6):
            k = e['segoff']
            assert cc.get(k, sem(e) + (e['reg'], e['srcreg'])) == sem(e) + (e['reg'], e['srcreg']), ('cc collision', hex(k))
            cc[k] = sem(e) + (e['reg'], e['srcreg']); e['vec'] = 7
    for e in entries:
        if e['type'] == 8: e['vec'] = 7
        elif e['type'] not in (5, 6): e['vec'] = vec_of[(e['mod'], e['seg'])]
    # INT 3 context bytes are read back from memory at run time, where neighbouring patched sites
    # have already been rewritten: record the patched byte, not the file byte
    pbyte = {}
    for e in entries:
        k = (e['mod'], e['seg'])
        if e['type'] == 8: continue
        pbyte[k, e['segoff']] = 0xCC if e['type'] in (5, 6) else 0xCD
        if e['type'] not in (5, 6): pbyte[k, e['segoff'] + 1] = 0xF8 + e['vec']
    for e in entries:
        if e['type'] in (5, 6):
            base = 3 if e['type'] == 5 else 1
            k = (e['mod'], e['seg'])
            if e['reg'] and (k, e['segoff'] + base) in pbyte: e['reg'] = pbyte[k, e['segoff'] + base]
            if e['srcreg'] and (k, e['segoff'] + base + 1) in pbyte: e['srcreg'] = pbyte[k, e['segoff'] + base + 1]
    entries.sort(key=lambda e: (e['vec'], e['segoff']))
    used = 0
    vtab = [(0, 0)] * 8
    start = 0
    for v in range(8):
        n = sum(1 for e in entries if e['vec'] == v)
        vtab[v] = (start, n); start += n
        if n: used |= (1 << v)
    out = bytearray(b'W8X1')
    out += struct.pack('<BBH', len(mods), used, len(entries))
    for s_, c_ in vtab: out += struct.pack('<HH', s_, c_)
    for m in mods:
        nm = m['name'].encode()[:12]
        out += struct.pack('<B12sBHHHH', len(nm), nm.ljust(12, b'\0'), m['dir'], m['size'] & 0xFFFF, m['size'] >> 16, m['crc'] & 0xFFFF, m['crc'] >> 16)
    for e in entries:
        out += struct.pack('<HBBHBBHBB', e['segoff'], e['type'], e['reg'], e['imm'], e['len'], e['srcreg'],
                           e['foff'] & 0xFFFF, e['foff'] >> 16, (e['mod'] << 4) | e['vec'])
    # window table: per module {lo_page w, hi_page w} (page = file offset >> 8) of the bytes we patch,
    # so the read hook can skip reads that cannot touch any patched byte (0xFFFF/0 = no sites)
    for mi in range(len(mods)):
        offs = []
        for e in entries:
            if e['mod'] == mi:
                offs.append(e['foff'])
                if e['type'] not in (5, 6): offs.append(e['foff'] + 1)
        out += struct.pack('<HH', (min(offs) >> 8) if offs else 0xFFFF, (max(offs) >> 8) if offs else 0)
    if verbose:
        c = collections.Counter(e['type'] for e in entries)
        print('modules', [m['name'] for m in mods], 'sites', len(entries), dict(c), 'vectors used', [v for v in range(8) if used >> v & 1], 'profile bytes', len(out))
    return bytes(out)

def imports_of(data):
    import struct
    ne = struct.unpack_from('<I', data, 0x3c)[0]
    n = struct.unpack_from('<H', data, ne + 0x1e)[0]
    mrt = struct.unpack_from('<H', data, ne + 0x28)[0]; imp = struct.unpack_from('<H', data, ne + 0x2a)[0]
    out = []
    for i in range(n):
        o = struct.unpack_from('<H', data, ne + mrt + 2 * i)[0]
        out.append(data[ne + imp + o + 1: ne + imp + o + 1 + data[ne + imp + o]].decode().upper())
    return out

def auto_specs(exe, wepdir):
    """EXE (dir 0) plus every helper DLL/VBX it imports, transitively, that ships with the game set (dir 1)."""
    wep = pathlib.Path(wepdir)
    specs = [(0, str(exe))]; seen = set(); todo = [str(exe)]
    import re
    seen_root = False
    have = {f.name.upper(): f for f in wep.iterdir() if f.suffix.upper() in ('.DLL', '.VBX')}
    while todo:
        data = open(todo.pop(), 'rb').read()
        # static imports (module reference table) plus helper libraries the code LoadLibrary()s by name
        names = {n + e for n in imports_of(data) for e in ('.DLL', '.VBX')}
        if not seen_root:
            seen_root = True    # by-name LoadLibrary strings are taken from the game EXE only (DLL copyright strings are noise)
            names |= {m.group(0).decode().upper() for m in re.finditer(rb'[A-Za-z0-9_]{3,12}\.(?:DLL|VBX)', data, re.I)}
        for nm in sorted(names):
            if nm in have and nm not in seen:
                seen.add(nm); specs.append((1, str(have[nm]))); todo.append(str(have[nm]))
    return specs

if __name__ == '__main__':
    # gen_profile.py OUT dir:FILE ...   |   gen_profile.py OUT auto:GAME.EXE   (imports resolved from the EXE's folder)
    out = sys.argv[1]; specs = []
    for a in sys.argv[2:]:
        d, p = a.split(':', 1)
        if d == 'auto': specs += auto_specs(p, pathlib.Path(p).parent)
        else: specs.append((int(d), p))
    open(out, 'wb').write(build(specs))
