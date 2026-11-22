#!/usr/bin/env python3
"""mkne.py -- link a small Windows 3.0 NE DLL from one nasm 'bin' image with two sections.

The nasm source has 'section code vstart=0' and 'section data vstart=0 ... follows=code' and
writes a map file ('[map all FILE]'). Relocations are labels the source macros emit (with nasm's '..@' prefix, which keeps
local labels working):
  __I_<MODULE>_<ordinal>_<n>   a far pointer (offset, segment) to an imported ordinal
  __D_<n>                      a 16-bit selector of the data segment
Each location holds 0FFFFh in its first word (end of the loader's fixup chain).

Usage: mkne.py BIN MAP OUT.DLL SPEC.json
SPEC: {"name": "COMMDLG", "description": "...", "heap": 1024, "entry": "LibEntry",
       "imports": ["USER", "KERNEL", "GDI"],
       "exports": [[ordinal, "NAME", "label", resident(bool)], ...],
       "code_flags": "fixed" | "moveable"}
Code is segment 1, data (the automatic data segment, fixed) segment 2."""
import json, re, struct, sys

def pstr(s): b = s.encode('latin1'); return bytes([len(b)]) + b

def build(binp, mapp, out, spec):
    img = open(binp, 'rb').read()
    text = open(mapp).read()
    symtext = text[text.index('-- Symbols'):]
    secs = {}
    for m in re.finditer(r'^\s*([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+progbits\s+(\S+)$',
                         text[:text.index('-- Sections (detailed)')], re.M):
        secs[m.group(5)] = (int(m.group(2), 16), int(m.group(4), 16))
    syms = {}
    cur = None
    for line in symtext.splitlines():
        m = re.match(r'---- Section (\S+) ', line)
        if m: cur = m.group(1); continue
        m = re.match(r'\s+([0-9A-F]+)\s+([0-9A-F]+)\s+(\S+)\s*$', line)
        if m and cur: syms[m.group(3)] = (cur, int(m.group(2), 16))
    code = img[secs['code'][0]:secs['code'][0] + secs['code'][1]]
    data = img[secs['data'][0]:secs['data'][0] + secs['data'][1]] if 'data' in secs else b''
    mods = [m.upper() for m in spec['imports']]
    relocs = {'code': [], 'data': []}
    for name, (sec, off) in syms.items():
        m = re.match(r'(?:\.\.@)?__I_([A-Z0-9]+)_(\d+)_\d+$', name)
        if m:
            relocs[sec].append(struct.pack('<BBHHH', 3, 1, off, mods.index(m.group(1)) + 1, int(m.group(2)))); continue
        if re.match(r'(?:\.\.@)?__D_\d+$', name):
            relocs[sec].append(struct.pack('<BBHBBH', 2, 0, off, 2, 0, 0))
    for sec, blob in (('code', code), ('data', data)):
        for r in relocs[sec]:
            off = struct.unpack_from('<H', r, 2)[0]
            assert blob[off:off + 2] == b'\xff\xff', 'relocation at %s:%04X does not hold 0FFFFh' % (sec, off)
    assert not relocs['data'], 'relocations in the data segment are not supported'

    # ---- tables
    exports = sorted(spec['exports'])
    res = pstr(spec['name'].upper()) + b'\0\0'
    nres = pstr(spec.get('description', spec['name'])) + b'\0\0'
    for o, n, lab, resident in exports:
        e = pstr(n.upper()) + struct.pack('<H', o)
        if resident: res += e
        else: nres += e
    res += b'\0'; nres += b'\0'
    imp = b'\0'; modoffs = []
    for m in mods: modoffs.append(len(imp)); imp += pstr(m)
    modtab = b''.join(struct.pack('<H', o) for o in modoffs)
    # entry table: code segment entries; fixed bundles (segment number) or moveable (0FFh)
    moveable = spec.get('code_flags') == 'moveable'
    ent = b''; nxt = 1; i = 0; ords = {o: syms[lab][1] for o, n, lab, r in exports}
    for o in sorted(ords): assert syms[[e for e in exports if e[0] == o][0][2]][0] == 'code'
    keys = sorted(ords)
    while i < len(keys):
        o = keys[i]
        while nxt < o:                               # gap: empty bundles
            k = min(o - nxt, 255); ent += bytes([k, 0]); nxt += k
        run = [o]
        while i + len(run) < len(keys) and keys[i + len(run)] == run[-1] + 1 and len(run) < 255: run.append(keys[i + len(run)])
        if moveable:
            ent += bytes([len(run), 0xFF]) + b''.join(struct.pack('<BHBH', 3, 0x3FCD, 1, ords[r]) for r in run)
        else:
            ent += bytes([len(run), 1]) + b''.join(struct.pack('<BH', 3, ords[r]) for r in run)
        i += len(run); nxt = run[-1] + 1
    ent += b'\0'

    # ---- layout: MZ stub, NE header, segment table, (no resources), names, modules, imports, entries, nres
    stubcode = bytes.fromhex('0e1fba0e00b409cd21b8014ccd21') + b'This program requires Microsoft Windows.\r\n$'
    mz = bytearray(64); mz[0:2] = b'MZ'
    struct.pack_into('<HHHHHHHHHH', mz, 2, 0, 0, 0, 4, 0, 0xFFFF, 0, 0xB8, 0, 0)
    struct.pack_into('<H', mz, 0x18, 0x40); stub = bytes(mz) + stubcode
    stub += b'\0' * (-len(stub) % 16)
    ne_off = len(stub); struct.pack_into('<I', bytearray(stub), 0x3C, ne_off)
    stub = bytearray(stub); struct.pack_into('<I', stub, 0x3C, ne_off)
    nseg = 2 if data else 1
    segtab_off = 0x40; rsrc_off = segtab_off + 8 * nseg; res_off = rsrc_off
    mod_off = res_off + len(res); imp_off = mod_off + len(modtab); ent_off = imp_off + len(imp)
    nres_file = ne_off + ent_off + len(ent)
    hdr_end = nres_file + len(nres)
    SH = 4; align = lambda x: (x + 15) & ~15
    code_pos = align(hdr_end)
    code_rel = struct.pack('<H', len(relocs['code'])) + b''.join(relocs['code'])
    data_pos = align(code_pos + len(code) + len(code_rel)) if data else 0
    cflags = 0x0100 | 0x0040 | (0x1010 if moveable else 0)   # relocinfo, preload (+moveable, discardable)
    dflags = 0x0001 | 0x0040                                   # data, preload, fixed
    segtab = struct.pack('<HHHH', code_pos >> SH, len(code), cflags, len(code))
    if data: segtab += struct.pack('<HHHH', data_pos >> SH, len(data), dflags, len(data))
    entry_lab = syms[spec['entry']]; assert entry_lab[0] == 'code'
    cmov = len(exports) if moveable else 0
    h = bytearray(0x40); h[0:2] = b'NE'; h[2] = 5; h[3] = 10
    struct.pack_into('<HH', h, 4, ent_off, len(ent))
    struct.pack_into('<H', h, 0x0C, 0x8301 if data else 0x8300)       # library, single data, windows API
    struct.pack_into('<HHH', h, 0x0E, 2 if data else 0, spec.get('heap', 0), 0)
    struct.pack_into('<HH', h, 0x14, entry_lab[1], 1)
    struct.pack_into('<HH', h, 0x18, 0, 0)
    struct.pack_into('<HHH', h, 0x1C, nseg, len(mods), len(nres))
    struct.pack_into('<HHHHH', h, 0x22, segtab_off, rsrc_off, res_off, mod_off, imp_off)
    struct.pack_into('<IHHH', h, 0x2C, nres_file, cmov, SH, 0)
    h[0x36] = 2                                                      # Windows
    struct.pack_into('<H', h, 0x3E, 0x0300)
    out_b = bytearray(stub) + h + segtab + res + modtab + imp + ent + nres
    assert len(out_b) == hdr_end
    out_b += b'\0' * (code_pos - len(out_b)) + code + code_rel
    if data: out_b += b'\0' * (data_pos - len(out_b)) + data
    open(out, 'wb').write(out_b)
    return len(out_b), len(code), len(data), len(relocs['code'])

if __name__ == '__main__':
    if len(sys.argv) != 5: print(__doc__); sys.exit(2)
    n = build(sys.argv[1], sys.argv[2], sys.argv[3], json.load(open(sys.argv[4])))
    print('%s: %d bytes (code %d, data %d, %d relocations)' % (sys.argv[3], *n))
