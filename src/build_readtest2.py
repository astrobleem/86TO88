import sys, pathlib, struct
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from asm88 import assemble

ROOT = pathlib.Path(__file__).resolve().parent.parent
exe = pathlib.Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else (ROOT / "WINMINE.EXE").read_bytes()  # specimen copy (user-supplied)
pb = (ROOT / "artifacts/patchbytes.bin").read_bytes()
patches = {}
for i in range(len(pb) // 4):
    off, b = struct.unpack_from("<HBx", pb, i * 4)
    patches[off] = b

def expected(start, n):
    return bytes(patches.get(start + i, exe[start + i]) for i in range(n))

def db_lines(data):
    return "\n".join(" DB " + ",".join(str(b) for b in data[i:i+16]) for i in range(0, len(data), 16))

LAST_SITE = 0x620 + 0x2550  # last site file offset (push 6 at seg off 0x2550)

# case tuples: (kind, handle_var, seek_mode, seek_off, read_n, exp_start or None, exp_ax)
CASES = [
    ("read", "hmain", 0, 0x43D, 4,    0x43D, None),   # partial span over version patch
    ("read", "hmain", 0, 0,     2048, 0,     None),   # whole header+sites region
    ("read", "hmain", 0, 0x620, 256,  0x620, None),   # first chunk
    ("cont", "hmain", None, None, 256, 0x720, None),  # sequential continuation
    ("read", "hmain", 0, LAST_SITE - 1, 4, LAST_SITE - 1, None),  # last site
    ("read", "hmain", 0, 0x662, 8,    0x662, None),   # starts inside patched site0
    ("read", "hmain", 2, -(len(exe) - 0x43E), 2, 0x43E, None),  # seek from end
    ("read", "hmain", 0, 27770, 16,   27770, 6),      # EOF partial read
    ("read0", "hmain", 0, 0x43E, 0,   None,  0),      # zero-length read
    ("read", "hmain", 1, 0x2C0, 4,    0x700, None),   # seek-from-current +0x2C0 (pos 0x440 -> 0x700)
    ("read", "hmain", 1, -0x2C6, 2,   0x43E, None),   # seek-from-current -0x2C6 (pos 0x704 -> 0x43E)
    ("read", "hmain", 0, 0x9CE, 5,    0x9CE, None),   # CC site: single 0xCC byte, FF FF preserved
]

L = []
L.append("ORG 100h")
L.append("start:")
L.append(" MOV AX, CS")
L.append(" MOV DS, AX")
L.append(" MOV DX, fname")
L.append(" MOV AX, 3D00h")
L.append(" INT 21h")
L.append(" JB fail_open")
L.append(" MOV [hmain], AX")
L.append(" MOV [hB], AX")  # placeholder; hB opened later

ci = 0
def emit_seek(hvar, mode, off):
    L.append(f" MOV BX, [{hvar}]")
    if mode == 0:
        L.append(" MOV AX, 4200h")
    elif mode == 1:
        L.append(" MOV AX, 4201h")
    else:
        L.append(" MOV AX, 4202h")
    off32 = off & 0xFFFFFFFF
    L.append(f" MOV CX, {off32 >> 16}")
    L.append(f" MOV DX, {off32 & 0xFFFF}")
    L.append(" INT 21h")
    L.append(f" JB fail_{ci}")

def emit_read_cmp(hvar, n, expstart, exp_ax, buf="buf"):
    global ci
    L.append(f" MOV BX, [{hvar}]")
    L.append(f" MOV DX, {buf}")
    L.append(f" MOV CX, {n}")
    L.append(" MOV AH, 3Fh")
    L.append(" INT 21h")
    L.append(f" JB fail_{ci}")
    want = exp_ax if exp_ax is not None else n
    L.append(f" CMP AX, {want}")
    L.append(f" JNE fail_{ci}")
    cmpn = want
    if cmpn:
        L.append(f" MOV SI, {buf}")
        L.append(f" MOV DI, exp_{ci}")
        L.append(f" MOV CX, {cmpn}")
        L.append(f"cmp_{ci}:")
        L.append(" MOV AL, [SI]")
        L.append(" CMP AL, [DI]")
        L.append(f" JNE fail_{ci}")
        L.append(" INC SI")
        L.append(" INC DI")
        L.append(f" LOOP cmp_{ci}")
    marker = "0123456789ABCDEFGHIJ"[ci]
    L.append(f" MOV DL, {ord(marker)}")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    ci += 1

for kind, hvar, mode, off, n, expstart, exp_ax in CASES:
    if kind == "read":
        emit_seek(hvar, mode, off)
        emit_read_cmp(hvar, n, expstart, exp_ax)
    elif kind == "cont":
        emit_read_cmp(hvar, n, expstart, exp_ax)
    elif kind == "read0":
        emit_seek(hvar, mode, off)
        emit_read_cmp(hvar, 0, None, 0)
        # position must still be 0x43E: read 2 without seek
        emit_read_cmp(hvar, 2, 0x43E, None)

# two-handle interleave
emit_seek("hmain", 0, 0x43E)  # hmain positioned at version, not yet read
L.append(" MOV DX, fname")
L.append(" MOV AX, 3D00h")
L.append(" INT 21h")
L.append(f" JB fail_{ci}")
L.append(" MOV [hB], AX")
emit_seek("hB", 0, 0x660)
emit_read_cmp("hB", 3, 0x660, None)       # CD F8 90 via second handle
emit_read_cmp("hmain", 2, 0x43E, None)    # first handle position independent

L.append(" MOV DX, msg_pass")
L.append(" MOV AH, 9")
L.append(" INT 21h")
L.append(" MOV AX, 4C00h")
L.append(" INT 21h")
L.append("fail_open:")
L.append(" MOV DX, msg_open")
L.append(" MOV AH, 9")
L.append(" INT 21h")
L.append(" MOV AX, 4C01h")
L.append(" INT 21h")
for i in range(ci):
    L.append(f"fail_{i}:")
    L.append(f" MOV DX, msg_f{i}")
    L.append(" MOV AH, 9")
    L.append(" INT 21h")
    L.append(" MOV AX, 4C01h")
    L.append(" INT 21h")
L.append('fname: DB 87,73,78,77,73,78,69,46,69,88,69,0')
L.append('msg_pass: DB 82,84,50,80,65,83,83,13,10,36')
L.append('msg_open: DB 82,84,50,70,65,73,76,32,79,80,69,78,13,10,36')
for i in range(ci):
    s = f"RT2FAIL C{i}\r\n$"
    L.append(f"msg_f{i}: DB " + ",".join(str(b) for b in s.encode()))
L.append("hmain: DW 0")
L.append("hB: DW 0")
L.append("buf:")
L.append(db_lines(bytes(256)))
# expected buffers, in case order (must mirror emit_read_cmp sequence)
exp_blobs = []
ci2 = 0
for kind, hvar, mode, off, n, expstart, exp_ax in CASES:
    if kind in ("read", "cont"):
        want = exp_ax if exp_ax is not None else n
        if want:
            exp_blobs.append((ci2, expected(expstart, want)))
        ci2 += 1
    elif kind == "read0":
        ci2 += 1
        exp_blobs.append((ci2, expected(0x43E, 2)))
        ci2 += 1
exp_blobs.append((ci2, expected(0x660, 3))); ci2 += 1
exp_blobs.append((ci2, expected(0x43E, 2))); ci2 += 1
for idx, blob in exp_blobs:
    L.append(f"exp_{idx}:")
    L.append(db_lines(blob))
# big buffer last (2048 bytes, filled by the case-1 read)
L.append("bufbig:")
L.append(db_lines(bytes(2048)))

src = "\n".join(L)
# reroute the 2048-byte read (case 1) into bufbig
src = src.replace(" MOV DX, buf\n MOV CX, 2048\n", " MOV DX, bufbig\n MOV CX, 2048\n")
src = src.replace(" MOV SI, buf\n MOV DI, exp_1\n", " MOV SI, bufbig\n MOV DI, exp_1\n")
code, labels = assemble(src, org=0x100)
out = ROOT / "artifacts/RTEST2.COM"
out.write_bytes(code)
print("RTEST2.COM", len(code), "cases:", ci2)
