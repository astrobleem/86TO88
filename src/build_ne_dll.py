"""Minimal NE (Windows 3.x) DLL writer, 8088-clean, for the small replacement DLLs the bridge ships.

build_dll(module, exports, code_src, imports) -> bytes
  exports : [(ordinal, name_or_None, label)]   label = entry point inside code_src; WEP is added automatically
  imports : [(import_label, module, ordinal)]  each import_label marks a 5-byte "DB 0EAh,255,255,0,0" (JMP FAR) or
            "DB 9Ah,255,255,0,0" (CALL FAR) in code_src that the loader patches to the imported routine
The layout follows build_shell.py (SHELL.DLL), which is proven on real-mode Windows 3.0: two segments (code + 16-byte
auto data), expected Windows version 3.00, 16-byte alignment, a 4-byte empty resource table, and 0xFFFF as the
single-node relocation chain terminator."""
import struct, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from asm88 import assemble

ALIGN = 4
a16 = lambda n: (n + 15) & ~15


def build_dll(module, exports, code_src, imports=()):
    code_src = "ORG 0\nentry:\n MOV AX, 1\n RETF\n" + code_src + "\nwep:\n MOV AX, 1\n RETF 2\n"
    code, labels = assemble(code_src, org=0)
    exports = list(exports) + [(max(o for o, _, _ in exports) + 1, 'WEP', 'wep')]
    # module reference table
    mods = []
    for _, m, _ in imports:
        if m not in mods: mods.append(m)
    imptab = b"\x00"
    modoff = {}
    for m in mods:
        modoff[m] = len(imptab)
        imptab += bytes([len(m)]) + m.encode()
    # resident names: module name (ordinal 0) then named exports
    restab = bytes([len(module)]) + module.encode() + struct.pack("<H", 0)
    for o, nm, _ in sorted(exports):
        if nm: restab += bytes([len(nm)]) + nm.encode() + struct.pack("<H", o)
    restab += b"\x00"
    # entry table
    byord = {o: lab for o, _, lab in exports}
    enttab = b""
    o = 1
    top = max(byord)
    while o <= top:
        if o not in byord:
            n = 0
            while o + n <= top and o + n not in byord and n < 255: n += 1
            enttab += bytes([n, 0]); o += n
        else:
            n = 0
            while o + n <= top and o + n in byord and n < 255: n += 1
            enttab += bytes([n, 1])
            for k in range(n): enttab += bytes([1]) + struct.pack("<H", labels[byord[o + k]])
            o += n
    enttab += b"\x00"
    SEGTAB = 0x40
    RSRC = SEGTAB + 16
    RESTAB = RSRC + 4
    MODTAB = RESTAB + len(restab)
    IMPTAB = MODTAB + 2 * len(mods)
    ENTTAB = IMPTAB + len(imptab)
    hdr_end = ENTTAB + len(enttab)
    NE_OFF = 0x80
    nrestxt = module.encode() + b" replacement (86TO88)"
    nonres = bytes([len(nrestxt)]) + nrestxt + struct.pack("<H", 0) + b"\x00"
    relocs = b"".join(struct.pack("<BBHHH", 3, 1, labels[l] + 1, mods.index(m) + 1, o) for l, m, o in imports)
    data = bytes(16)
    seg1_file = a16(NE_OFF + hdr_end)
    seg2_file = a16(seg1_file + len(code) + 2 + len(relocs))
    nonres_file = a16(seg2_file + len(data))
    hdr = bytearray(0x40)
    hdr[0:2] = b"NE"; hdr[2] = 5
    struct.pack_into("<H", hdr, 4, ENTTAB); struct.pack_into("<H", hdr, 6, len(enttab))
    hdr[0x0C] = 0; hdr[0x0D] = 0x83
    struct.pack_into("<H", hdr, 0x0E, 2)
    struct.pack_into("<H", hdr, 0x14, labels["entry"])
    struct.pack_into("<H", hdr, 0x16, 1)
    struct.pack_into("<H", hdr, 0x1C, 2); struct.pack_into("<H", hdr, 0x1E, len(mods))
    struct.pack_into("<H", hdr, 0x20, len(nonres))
    struct.pack_into("<H", hdr, 0x22, SEGTAB); struct.pack_into("<H", hdr, 0x24, RSRC)
    struct.pack_into("<H", hdr, 0x26, RESTAB); struct.pack_into("<H", hdr, 0x28, MODTAB); struct.pack_into("<H", hdr, 0x2A, IMPTAB)
    struct.pack_into("<I", hdr, 0x2C, nonres_file)
    struct.pack_into("<H", hdr, 0x32, ALIGN)
    hdr[0x36] = 2
    struct.pack_into("<H", hdr, 0x3E, 0x0300)
    # RELOCINFO (0x0100) only when the segment really has relocations: real-mode Windows 3.0 aborts a library load
    # ("insufficient memory") when it meets that flag with a zero-length relocation table
    segtab = struct.pack("<HHHH", seg1_file >> ALIGN, len(code), 0x0D40 if imports else 0x0C40, len(code))
    segtab += struct.pack("<HHHH", seg2_file >> ALIGN, len(data), 0x0C61, len(data))
    blob = bytearray(nonres_file + len(nonres))
    blob[0:2] = b"MZ"
    struct.pack_into("<H", blob, 4, 8); struct.pack_into("<H", blob, 8, 1); struct.pack_into("<H", blob, 0x3C, NE_OFF)
    blob[NE_OFF:NE_OFF + 0x40] = hdr
    blob[NE_OFF + SEGTAB:NE_OFF + SEGTAB + 16] = segtab
    struct.pack_into("<HH", blob, NE_OFF + RSRC, 0, 0)
    blob[NE_OFF + RESTAB:NE_OFF + RESTAB + len(restab)] = restab
    for i, m in enumerate(mods): struct.pack_into("<H", blob, NE_OFF + MODTAB + 2 * i, modoff[m])
    blob[NE_OFF + IMPTAB:NE_OFF + IMPTAB + len(imptab)] = imptab
    blob[NE_OFF + ENTTAB:NE_OFF + ENTTAB + len(enttab)] = enttab
    blob[seg1_file:seg1_file + len(code)] = code
    struct.pack_into("<H", blob, seg1_file + len(code), len(imports))
    blob[seg1_file + len(code) + 2:seg1_file + len(code) + 2 + len(relocs)] = relocs
    blob[seg2_file:seg2_file + len(data)] = data
    blob[nonres_file:nonres_file + len(nonres)] = nonres
    return bytes(blob)
