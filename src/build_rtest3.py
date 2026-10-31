import sys, pathlib, struct
sys.path.insert(0, "/Users/macsd/winmine-hack/src")
from asm88 import assemble

ROOT = pathlib.Path("/Users/macsd/winmine-hack")
ART = ROOT / "artifacts"

def build(name, src):
    code, labels = assemble(src, org=0x100)
    (ART / name).write_bytes(code)
    print(name, len(code), "bytes")
    return labels

# ---------- LEAK.COM: open WINMINE.EXE, exit WITHOUT closing ----------
build("LEAK.COM", r"""
ORG 100h
start:
 MOV AX, CS
 MOV DS, AX
 MOV DX, fname
 MOV AX, 3D00h
 INT 21h
 MOV AX, 4C00h
 INT 21h
fname: DB 87,73,78,77,73,78,69,46,69,88,69,0
""")

# ---------- CHECK / FCHECK: open a file, read 500h, test byte at 43Eh ----------
def reader(name, path_db, safe, patched):
    src = r"""
ORG 100h
start:
 MOV AX, CS
 MOV DS, AX
 MOV DX, fname
 MOV AX, 3D00h
 INT 21h
 JB err
 MOV BX, AX
 MOV CX, 1280
 MOV DX, buf
 MOV AH, 3Fh
 INT 21h
 JB err
 CMP BYTE [buf+1086], 16
 JE is_safe
 MOV DX, m_patched
 JMP pr
is_safe:
 MOV DX, m_safe
pr:
 MOV AH, 9
 INT 21h
 MOV AX, 4C00h
 INT 21h
err:
 MOV DX, m_err
 MOV AH, 9
 INT 21h
 MOV AX, 4C01h
 INT 21h
fname: DB __PATH__
m_safe: DB __SAFE__
m_patched: DB __PATCHED__
m_err: DB 69,82,82,13,10,36
buf: DB __BUF__
"""
    src = src.replace("__PATH__", ",".join(str(b) for b in path_db))
    src = src.replace("__SAFE__", ",".join(str(b) for b in safe))
    src = src.replace("__PATCHED__", ",".join(str(b) for b in patched))
    src = src.replace("__BUF__", ",".join("0" for _ in range(1280)))
    build(name, src)

reader("CHECK.COM", b"DUMMY.BIN\x00", b"SAFE\r\n$", b"PATCHED\r\n$")
reader("FCHECK.COM", b"SUB\\WINMINE.EXE\x00", b"FSAFE\r\n$", b"FPATCHED\r\n$")

# ---------- T88B.COM: foreign INT 3 / INT F8 / INT F8 low-underflow ----------
# All stimulus bytes live in a separate trampoline segment so the handler keys
# (raw IP in that segment) match the specimen offsets they are compared with.
sites = set()
tbl = (ART / "sites-table.bin").read_bytes()
for i in range(0, len(tbl), 8):
    sites.add(struct.unpack_from("<H", tbl, i)[0])
assert 0x200 not in sites and 0x10 not in sites

SRC = r"""
ORG 100h
start:
 MOV AX, CS
 MOV DS, AX
 ; shrink own block (.COM owns all memory), then allocate trampoline
 MOV BX, 160
 MOV AH, 74
 INT 21h
 MOV SP, 2560
 MOV BX, 64
 MOV AH, 48h
 INT 21h
 JB afail
 MOV [tseg], AX
 MOV ES, AX
 ; stub U at 0010h: CD F8, EA uf_back
 MOV BYTE ES:[16], 205
 MOV BYTE ES:[17], 248
 MOV BYTE ES:[18], 234
 MOV AX, uf_back
 MOV ES:[19], AX
 MOV AX, CS
 MOV ES:[21], AX
 ; stub F at 0200h: CD F8, EA f8_back  (0200h is not a table key)
 MOV BYTE ES:[512], 205
 MOV BYTE ES:[513], 248
 MOV BYTE ES:[514], 234
 MOV AX, f8_back
 MOV ES:[515], AX
 MOV AX, CS
 MOV ES:[517], AX
 ; stub C at 03AFh: CC, word 1234h, 90 90 90 (wrong context), EA cc_chk
 MOV BYTE ES:[943], 204
 MOV BYTE ES:[944], 52
 MOV BYTE ES:[945], 18
 MOV BYTE ES:[946], 144
 MOV BYTE ES:[947], 144
 MOV BYTE ES:[948], 144
 MOV BYTE ES:[949], 234
 MOV AX, cc_chk
 MOV ES:[950], AX
 MOV AX, CS
 MOV ES:[952], AX
 ; ---- INT 3 test ----
 MOV AX, SP
 MOV [spb], AX
 PUSH CS
 MOV AX, cc_back
 PUSH AX
 MOV AX, [tseg]
 PUSH AX
 MOV AX, 943
 PUSH AX
 RETF
cc_chk:
 MOV AX, SP
 ADD AX, 4
 CMP AX, [spb]
 JE cc_chained
 MOV BYTE [out3], 80
 POP AX
 RETF
cc_chained:
 MOV BYTE [out3], 67
 RETF
cc_back:
 ; ---- INT F8 unknown-key test ----
 PUSH CS
 MOV AX, f8_back2
 PUSH AX
 MOV AX, [tseg]
 PUSH AX
 MOV AX, 512
 PUSH AX
 RETF
f8_back:
 MOV BYTE [outf], 70
 RETF
f8_back2:
 ; print "T" out3 outf before the dangerous underflow test
 MOV DL, 84
 MOV AH, 2
 INT 21h
 MOV DL, [out3]
 MOV AH, 2
 INT 21h
 MOV DL, [outf]
 MOV AH, 2
 INT 21h
 ; ---- INT F8 low-underflow test (key 0010h < first table entry) ----
 PUSH CS
 MOV AX, uf_back2
 PUSH AX
 MOV AX, [tseg]
 PUSH AX
 MOV AX, 16
 PUSH AX
 RETF
uf_back:
 MOV BYTE [outu], 85
 RETF
uf_back2:
 MOV DL, [outu]
 MOV AH, 2
 INT 21h
 MOV DL, 13
 MOV AH, 2
 INT 21h
 MOV DL, 10
 MOV AH, 2
 INT 21h
 MOV AX, 4C00h
 INT 21h
afail:
 MOV DX, m_af
 MOV AH, 9
 INT 21h
 MOV AX, 4C01h
 INT 21h
m_af: DB 65,70,65,73,76,13,10,36
tseg: DW 0
spb: DW 0
out3: DB 63
outf: DB 63
outu: DB 63
"""

code, labels = assemble(SRC, org=0x100)
(ART / "T88B.COM").write_bytes(code)
print("T88B.COM", len(code), "bytes")
