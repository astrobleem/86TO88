import sys, pathlib, struct, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from asm88 import assemble

ROOT = pathlib.Path(__file__).resolve().parent.parent
# verify MessageBox ordinal in Win3.0 USER from earlier analysis
u30 = json.loads((ROOT / "artifacts/exports-WINDOWS-USER.json").read_text())
mb = u30.get("byname", {}).get("MESSAGEBOX")
print("USER MessageBox ordinal:", mb)

# NOTE: call_mb offset word must be 0xFFFF -- KERNEL walks far-pointer fixup
# chains through the image offset words; 0xFFFF is the single-node terminator.
# (0x0000 made the walker follow our own code bytes as links -> infinite loop.)
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
print("code len", hex(len(code)), "entry", labels["entry"], "shellabout", labels["shellabout"], "wep", labels["wep"], "call_mb", labels["call_mb"])

ALIGN = 4  # 16-byte segment alignment in file
def a16(n): return (n + 15) & ~15

# --- NE header block layout (NE-relative offsets) ---
SEGTAB = 0x40
RSRC = SEGTAB + 16
# An empty resource table is FOUR bytes: shift-count word 0 AND terminating
# type word 0. Shipping only the shift word (2 bytes) made KERNEL parse the
# resident-name table as a TYPEINFO with wCount=0x4548 -> global-heap
# corruption and an infinite arena loop at DLL load. (Bisected 2026-10-31:
# this 2-byte change alone fixes the load hang.)
restab_items = [(b"SHELL", 0), (b"SHELLABOUT", 22), (b"WEP", 23)]
RESTAB = RSRC + 4
restab = b""
for nm, o in restab_items:
    restab += bytes([len(nm)]) + nm + struct.pack("<H", o)
restab += b"\x00"
MODTAB = RESTAB + len(restab)
IMPTAB = MODTAB + 2
imptab = b"\x00\x04USER"          # leading 0, then length-prefixed module name
modtab_word = 1                    # offset of "USER" length byte within imptab
ENTTAB = IMPTAB + len(imptab)
enttab = bytes([21, 0])            # skip ordinals 1..21
enttab += bytes([2, 1])            # 2 fixed entries in segment 1
enttab += bytes([1]) + struct.pack("<H", labels["shellabout"])
enttab += bytes([1]) + struct.pack("<H", labels["wep"])
enttab += b"\x00"
hdr_end = ENTTAB + len(enttab)

NE_OFF = 0x80
seg1_file = a16(NE_OFF + hdr_end)
seg1_off_units = seg1_file >> ALIGN
data = bytes(16)
seg2_file = a16(seg1_file + len(code) + 2 + 8)  # leave room for reloc count + 1 record
seg2_off_units = seg2_file >> ALIGN
nonres = bytes([5]) + b"SHELL" + struct.pack("<H", 0) + b"\x00"
nonres_file = a16(seg2_file + len(data))

hdr = bytearray(0x40)
hdr[0:2] = b"NE"
hdr[2] = 5   # linker version 5.0-ish
hdr[3] = 0
struct.pack_into("<H", hdr, 4, ENTTAB)
struct.pack_into("<H", hdr, 6, len(enttab))
struct.pack_into("<I", hdr, 8, 0)          # CRC (0 = unchecked)
hdr[0x0C] = 0                              # program flags (as WIN87EM.DLL)
hdr[0x0D] = 0x83                           # application flags: DLL
struct.pack_into("<H", hdr, 0x0E, 2)       # auto DS = segment 2
struct.pack_into("<H", hdr, 0x10, 0)       # heap
struct.pack_into("<H", hdr, 0x12, 0)       # stack
struct.pack_into("<H", hdr, 0x14, labels["entry"])   # IP
struct.pack_into("<H", hdr, 0x16, 1)                 # CS = segment 1
struct.pack_into("<H", hdr, 0x18, 0)                 # SP
struct.pack_into("<H", hdr, 0x1A, 0)                 # SS
struct.pack_into("<H", hdr, 0x1C, 2)       # cseg
struct.pack_into("<H", hdr, 0x1E, 1)       # cmod
struct.pack_into("<H", hdr, 0x20, len(nonres))       # cbnrestab
struct.pack_into("<H", hdr, 0x22, SEGTAB)
struct.pack_into("<H", hdr, 0x24, RSRC)
struct.pack_into("<H", hdr, 0x26, RESTAB)
struct.pack_into("<H", hdr, 0x28, MODTAB)
struct.pack_into("<H", hdr, 0x2A, IMPTAB)
struct.pack_into("<I", hdr, 0x2C, nonres_file)
struct.pack_into("<H", hdr, 0x30, 0)       # cmovent
struct.pack_into("<H", hdr, 0x32, ALIGN)
struct.pack_into("<H", hdr, 0x34, 0)       # cres
hdr[0x36] = 2                              # exetyp: Windows
struct.pack_into("<H", hdr, 0x3E, 0x0300)  # expected Windows 3.0

segtab = struct.pack("<HHHH", seg1_off_units, len(code), 0x0D40, len(code))
segtab += struct.pack("<HHHH", seg2_off_units, len(data), 0x0C61, len(data))

blob = bytearray(nonres_file + len(nonres))
# MZ stub: 0x80 bytes, e_lfanew at 0x3C
blob[0:2] = b"MZ"
struct.pack_into("<H", blob, 4, 8)         # e_cparhdr = 8 paragraphs (0x80 bytes)
struct.pack_into("<H", blob, 8, 1)         # e_minalloc
struct.pack_into("<H", blob, 0x3C, NE_OFF)
blob[NE_OFF:NE_OFF + 0x40] = hdr
blob[NE_OFF + SEGTAB:NE_OFF + SEGTAB + 16] = segtab
struct.pack_into("<HH", blob, NE_OFF + RSRC, 0, 0)
blob[NE_OFF + RESTAB:NE_OFF + RESTAB + len(restab)] = restab
struct.pack_into("<H", blob, NE_OFF + MODTAB, modtab_word)
blob[NE_OFF + IMPTAB:NE_OFF + IMPTAB + len(imptab)] = imptab
blob[NE_OFF + ENTTAB:NE_OFF + ENTTAB + len(enttab)] = enttab
reloc = struct.pack("<BBHHH", 3, 1, labels["call_mb"] + 1, 1, 1)  # far addr, import-ordinal, USER.1
blob[seg1_file:seg1_file + len(code)] = code
struct.pack_into("<H", blob, seg1_file + len(code), 1)   # relocation count
blob[seg1_file + len(code) + 2:seg1_file + len(code) + 10] = reloc
blob[seg2_file:seg2_file + len(data)] = data
blob[nonres_file:nonres_file + len(nonres)] = nonres

out = ROOT / "artifacts/SHELL.DLL"
out.write_bytes(bytes(blob))
print("SHELL.DLL", len(blob), "seg1 file", hex(seg1_file), "seg2 file", hex(seg2_file), "nonres", hex(nonres_file))
