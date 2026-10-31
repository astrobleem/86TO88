import sys, pathlib, struct
sys.path.insert(0, "/Users/macsd/winmine-hack/src")
from asm88 import assemble

# Isolation test: original build_shell.py output + ONLY the resource-table fix.
OUT = pathlib.Path(sys.argv[1])

CODE = r"""
ORG 0
entry:
 MOV AX, 1
 RETF
shellabout:
 PUSH BP
 MOV BP, SP
 MOV AX, [BP+16]
 PUSH AX
 MOV AX, [BP+10]
 PUSH AX
 MOV AX, [BP+8]
 PUSH AX
 MOV AX, [BP+14]
 PUSH AX
 MOV AX, [BP+12]
 PUSH AX
 XOR AX, AX
 PUSH AX
call_mb: DB 154,255,255,0,0
 POP BP
 RETF 12
wep:
 MOV AX, 1
 RETF 2
"""
code, labels = assemble(CODE, org=0)

ALIGN = 4
def a16(n): return (n + 15) & ~15

SEGTAB = 0x40
RSRC = SEGTAB + 16
restab_items = [(b"SHELL", 0), (b"SHELLABOUT", 22), (b"WEP", 23)]
RESTAB = RSRC + 4                     # FIX: was RSRC + 2
restab = b""
for nm, o in restab_items:
    restab += bytes([len(nm)]) + nm + struct.pack("<H", o)
restab += b"\x00"
MODTAB = RESTAB + len(restab)
IMPTAB = MODTAB + 2
imptab = b"\x00\x04USER"
modtab_word = 1
ENTTAB = IMPTAB + len(imptab)
enttab = bytes([21, 0])
enttab += bytes([2, 1])
enttab += bytes([1]) + struct.pack("<H", labels["shellabout"])
enttab += bytes([1]) + struct.pack("<H", labels["wep"])
enttab += b"\x00"
hdr_end = ENTTAB + len(enttab)

NE_OFF = 0x80
seg1_file = a16(NE_OFF + hdr_end)
seg1_off_units = seg1_file >> ALIGN
data = bytes(16)
seg2_file = a16(seg1_file + len(code) + 2 + 8)
seg2_off_units = seg2_file >> ALIGN
nonres = bytes([5]) + b"SHELL" + struct.pack("<H", 0) + b"\x00"
nonres_file = a16(seg2_file + len(data))

hdr = bytearray(0x40)
hdr[0:2] = b"NE"
hdr[2] = 5
hdr[3] = 0                            # original: linker sub-version 0
struct.pack_into("<H", hdr, 4, ENTTAB)
struct.pack_into("<H", hdr, 6, len(enttab))
struct.pack_into("<I", hdr, 8, 0)
hdr[0x0C] = 0                         # original: progflags 0
hdr[0x0D] = 0x83
struct.pack_into("<H", hdr, 0x0E, 2)
struct.pack_into("<H", hdr, 0x10, 0)  # original: heap 0
struct.pack_into("<H", hdr, 0x12, 0)
struct.pack_into("<H", hdr, 0x14, labels["entry"])
struct.pack_into("<H", hdr, 0x16, 1)
struct.pack_into("<H", hdr, 0x18, 0)
struct.pack_into("<H", hdr, 0x1A, 0)
struct.pack_into("<H", hdr, 0x1C, 2)
struct.pack_into("<H", hdr, 0x1E, 1)
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
struct.pack_into("<H", hdr, 0x3E, 0x0300)

segtab = struct.pack("<HHHH", seg1_off_units, len(code), 0x0D40, len(code))
segtab += struct.pack("<HHHH", seg2_off_units, len(data), 0x0C61, len(data))

blob = bytearray(nonres_file + len(nonres))
blob[0:2] = b"MZ"
struct.pack_into("<H", blob, 4, 8)     # original MZ quirks kept
struct.pack_into("<H", blob, 8, 1)
struct.pack_into("<H", blob, 0x3C, NE_OFF)
blob[NE_OFF:NE_OFF + 0x40] = hdr
blob[NE_OFF + SEGTAB:NE_OFF + SEGTAB + 16] = segtab
struct.pack_into("<HH", blob, NE_OFF + RSRC, 0, 0)   # FIX: 4-byte empty resource table
blob[NE_OFF + RESTAB:NE_OFF + RESTAB + len(restab)] = restab
struct.pack_into("<H", blob, NE_OFF + MODTAB, modtab_word)
blob[NE_OFF + IMPTAB:NE_OFF + IMPTAB + len(imptab)] = imptab
blob[NE_OFF + ENTTAB:NE_OFF + ENTTAB + len(enttab)] = enttab
reloc = struct.pack("<BBHHH", 3, 1, labels["call_mb"] + 1, 1, 1)
blob[seg1_file:seg1_file + len(code)] = code
struct.pack_into("<H", blob, seg1_file + len(code), 1)
blob[seg1_file + len(code) + 2:seg1_file + len(code) + 10] = reloc
blob[seg2_file:seg2_file + len(data)] = data
blob[nonres_file:nonres_file + len(nonres)] = nonres

OUT.write_bytes(bytes(blob))
print("A0 ->", OUT, len(blob))
