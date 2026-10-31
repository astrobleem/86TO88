import sys, pathlib, struct
sys.path.insert(0, "/Users/macsd/winmine-hack/src")
from asm88 import assemble

ROOT = pathlib.Path("/Users/macsd/winmine-hack")

CODE = r"""
ORG 0
entry:
 MOV AX, 1
 RETF
opensound:
 MOV AX, 1
 RETF
closesound:
 XOR AX, AX
 RETF
setvoicenote:
 XOR AX, AX
 RETF 8
setvoiceaccent:
 XOR AX, AX
 RETF 10
startsound:
 XOR AX, AX
 RETF
stopsound:
 XOR AX, AX
 RETF
wep:
 MOV AX, 1
 RETF 2
"""
code, labels = assemble(CODE, org=0)
print("code len", hex(len(code)), {k: labels[k] for k in ("entry","opensound","closesound","setvoicenote","setvoiceaccent","startsound","stopsound","wep")})

ALIGN = 4
def a16(n): return (n + 15) & ~15

SEGTAB = 0x40
RSRC = SEGTAB + 16
# resident name table: module name + exported names (KERNEL resolves WEP by name)
restab_items = [(b"SOUND", 0), (b"OPENSOUND", 1), (b"CLOSESOUND", 2),
                (b"SETVOICENOTE", 4), (b"SETVOICEACCENT", 5),
                (b"STARTSOUND", 9), (b"STOPSOUND", 10), (b"WEP", 11)]
RESTAB = RSRC + 2
restab = b""
for nm, o in restab_items:
    restab += bytes([len(nm)]) + nm + struct.pack("<H", o)
restab += b"\x00"
MODTAB = RESTAB + len(restab)
IMPTAB = MODTAB  # no imported modules: modtab (first word) overlaps empty imptab start
imptab = b""
ENTTAB = IMPTAB + len(imptab)
enttab = bytes([2, 1])                                   # ordinals 1-2, fixed seg 1
for lbl in ("opensound", "closesound"):
    enttab += bytes([1]) + struct.pack("<H", labels[lbl])
enttab += bytes([1, 0])                                  # skip ordinal 3
enttab += bytes([2, 1])                                  # ordinals 4-5
for lbl in ("setvoicenote", "setvoiceaccent"):
    enttab += bytes([1]) + struct.pack("<H", labels[lbl])
enttab += bytes([3, 0])                                  # skip ordinals 6-8
enttab += bytes([3, 1])                                  # ordinals 9-11
for lbl in ("startsound", "stopsound", "wep"):
    enttab += bytes([1]) + struct.pack("<H", labels[lbl])
enttab += b"\x00"
hdr_end = ENTTAB + len(enttab)

NE_OFF = 0x80
seg1_file = a16(NE_OFF + hdr_end)
seg1_off_units = seg1_file >> ALIGN
data = bytes(16)
seg2_file = a16(seg1_file + len(code))
seg2_off_units = seg2_file >> ALIGN
nonres = bytes([5]) + b"SOUND" + struct.pack("<H", 0) + b"\x00"
nonres_file = a16(seg2_file + len(data))

hdr = bytearray(0x40)
hdr[0:2] = b"NE"
hdr[2] = 5
hdr[3] = 0
struct.pack_into("<H", hdr, 4, ENTTAB)
struct.pack_into("<H", hdr, 6, len(enttab))
struct.pack_into("<I", hdr, 8, 0)
hdr[0x0C] = 0
hdr[0x0D] = 0x83
struct.pack_into("<H", hdr, 0x0E, 2)      # auto DS = segment 2
struct.pack_into("<H", hdr, 0x10, 0)
struct.pack_into("<H", hdr, 0x12, 0)
struct.pack_into("<H", hdr, 0x14, labels["entry"])
struct.pack_into("<H", hdr, 0x16, 1)
struct.pack_into("<H", hdr, 0x18, 0)
struct.pack_into("<H", hdr, 0x1A, 0)
struct.pack_into("<H", hdr, 0x1C, 2)      # cseg
struct.pack_into("<H", hdr, 0x1E, 0)      # cmod = 0 (no imports)
struct.pack_into("<H", hdr, 0x20, len(nonres))
struct.pack_into("<H", hdr, 0x22, SEGTAB)
struct.pack_into("<H", hdr, 0x24, RSRC)
struct.pack_into("<H", hdr, 0x26, RESTAB)
struct.pack_into("<H", hdr, 0x28, MODTAB)
struct.pack_into("<H", hdr, 0x2A, IMPTAB)
struct.pack_into("<I", hdr, 0x2C, nonres_file)
struct.pack_into("<H", hdr, 0x30, 0)
struct.pack_into("<H", hdr, 0x32, ALIGN)
struct.pack_into("<H", hdr, 0x34, 0)
hdr[0x36] = 2
struct.pack_into("<H", hdr, 0x3E, 0x0300)  # expected Windows 3.0

segtab = struct.pack("<HHHH", seg1_off_units, len(code), 0x0D40, len(code))
segtab += struct.pack("<HHHH", seg2_off_units, len(data), 0x0C61, len(data))

blob = bytearray(nonres_file + len(nonres))
blob[0:2] = b"MZ"
struct.pack_into("<H", blob, 4, 8)
struct.pack_into("<H", blob, 8, 1)
struct.pack_into("<H", blob, 0x3C, NE_OFF)
blob[NE_OFF:NE_OFF + 0x40] = hdr
blob[NE_OFF + SEGTAB:NE_OFF + SEGTAB + 16] = segtab
struct.pack_into("<H", blob, NE_OFF + RSRC, 0)
blob[NE_OFF + RESTAB:NE_OFF + RESTAB + len(restab)] = restab
struct.pack_into("<H", blob, NE_OFF + MODTAB, 0)   # cmod=0, word unused
blob[NE_OFF + ENTTAB:NE_OFF + ENTTAB + len(enttab)] = enttab
blob[seg1_file:seg1_file + len(code)] = code
blob[seg2_file:seg2_file + len(data)] = data
blob[nonres_file:nonres_file + len(nonres)] = nonres

out = ROOT / "artifacts/SOUND.DLL"
out.write_bytes(bytes(blob))
print("SOUND.DLL", len(blob), "seg1 file", hex(seg1_file), "seg2 file", hex(seg2_file), "nonres", hex(nonres_file))
