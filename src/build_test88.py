import sys, pathlib, struct
sys.path.insert(0, "/Users/macsd/winmine-hack/src")
from asm88 import assemble

ROOT = pathlib.Path("/Users/macsd/winmine-hack")
tbl = (ROOT / "artifacts/sites-table.bin").read_bytes()
import json
ERRCNT_OFF = json.loads((ROOT / "artifacts/tsr-labels.json").read_text())["errcnt"]

sites = []
for i in range(len(tbl)//8):
    off, typ, reg, imm, ln, src = struct.unpack_from("<HBBHBB", tbl, i * 8)
    sites.append(dict(idx=i, key=off, type=typ, reg=reg, imm=imm, len=ln, src=src))

REG = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"]
SENT = {"AX": 0x1111, "CX": 0x2222, "DX": 0x3333, "BX": 0x4444, "SI": 0x5555, "DI": 0x6666, "BP": 0x7777}

def find(type_, reg=None, ln=None, immtest=None):
    for s in sites:
        if s["type"] != type_:
            continue
        if reg is not None and s["reg"] != reg:
            continue
        if ln is not None and s["len"] != ln:
            continue
        if immtest and not immtest(s["imm"]):
            continue
        return s
    raise SystemExit(f"site not found type={type_} reg={reg} len={ln}")

CASES = []
CASES.append(("push16", find(0, ln=3)))
CASES.append(("push8pos", find(0, ln=2, immtest=lambda v: 0 < v < 0x80)))
CASES.append(("push8neg", find(0, ln=2, immtest=lambda v: v >= 0xFF80)))
CASES.append(("shl_si", find(1, reg=6)))
CASES.append(("shl_bx", find(1, reg=3)))
CASES.append(("shl_di", find(1, reg=7)))
CASES.append(("shr_ax", find(2, reg=0)))
CASES.append(("shr_cx", find(2, reg=1)))
CASES.append(("sar_ax", find(3, reg=0)))
CASES.append(("imul_a", find(4)))
CASES.append(("imul_b", find(4)))
# CC (INT 3, relocation-resolved push) cases. All six sites form three adjacent
# pairs (push FFFF; push FFFF = callback segment+offset), so each pair is one case:
# CC,key+1..2=wordA, CC at key+3, wordB at key+4..5. In the real segment the
# second site is followed by an FF 36 (PUSH [mem]) instruction, and the fixed
# TSR verifies exactly those context bytes, so the trampoline reproduces them:
# FF 36 <scratch> at key+6, far-jump stub at key+10. The checker pops the
# scratch push, then B, then A (LIFO).
_cc = json.loads((ROOT / "artifacts/cc-sites.json").read_text())
_offs = sorted(c["off"] for c in _cc)
_pairs = [(_offs[i], _offs[i+1]) for i in range(0, len(_offs), 2)]
assert all(b == a + 3 for a, b in _pairs), _pairs
CCVAL = [(0x5A5A, 0x1234), (0xABCD, 0x0001), (0xFFFE, 0x8000)]
for _j, (_a, _b) in enumerate(_pairs):
    _va, _vb = CCVAL[_j]
    CASES.append((f"ccpair{_j}", dict(idx=("ccp", _a), key=_a, type="ccpair", reg=0, imm=_vb, imm2=_va, len=10, src=0)))

SHIFT_OP = {1: "SHL", 2: "SHR", 3: "SAR"}
OPERAND = {1: 0x5A3C, 2: 0xA5C3, 3: 0x96C3}

def db_lines(data):
    return "\n".join(" DB " + ",".join(str(b) for b in data[i:i+16]) for i in range(0, len(data), 16))

def gen(padstart):
    L = []
    L.append("ORG 100h")
    L.append("start:")
    L.append(" MOV AX, CS")
    L.append(" MOV DS, AX")
    # TSR present? sig "WM88" at ES:[BX-4] after INT 21h AH=35h AL=F8h
    L.append(" MOV AH, 35h")
    L.append(" MOV AL, 0F8h")
    L.append(" INT 21h")
    L.append(" CMP BYTE ES:[BX-4], 87")
    L.append(" JNE notsr")
    L.append(" CMP BYTE ES:[BX-3], 77")
    L.append(" JNE notsr")
    L.append(" CMP BYTE ES:[BX-2], 56")
    L.append(" JNE notsr")
    L.append(" CMP BYTE ES:[BX-1], 56")
    L.append(" JNE notsr")
    L.append(" MOV AX, ES")
    L.append(" MOV [tsrseg], AX")
    L.append(f" MOV AX, ES:[{ERRCNT_OFF}]")
    L.append(" MOV [err0], AX")
    L.append(" MOV AX, CS")
    L.append(f" ADD AX, {padstart // 16}")
    L.append(" MOV [trampseg], AX")
    # runtime-patch the segment word of each trampoline far-jmp stub
    for i, (name, s) in enumerate(CASES):
        L.append(" MOV AX, [trampseg]")
        L.append(" MOV ES, AX")
        L.append(f" MOV DI, {s['key'] + s['len'] + 3}")
        L.append(" MOV AX, CS")
        L.append(" MOV ES:[DI], AX")
    # not-found stub segment word (offset 0x10 + 2 + 3)
    L.append(" MOV AX, [trampseg]")
    L.append(" MOV ES, AX")
    L.append(" MOV DI, 21")
    L.append(" MOV AX, CS")
    L.append(" MOV ES:[DI], AX")

    for i, (name, s) in enumerate(CASES):
        L.append(f"; ---- case {i} {name} site idx={s['idx']} key={s['key']:#x} ----")
        if s["type"] in (0, "cc", "ccpair"):  # PUSH imm (F8 table or CC/INT3)
            L.append(" MOV AX, 0FFFFh")
            L.append(" ADD AX, 1")
            L.append(" PUSHF")
            L.append(" POP AX")
            L.append(" MOV [expflags], AX")
        elif s["type"] in (1, 2, 3):  # shift: native expected in AX
            L.append(f" MOV AX, {OPERAND[s['type']]}")
            L.append(f" MOV CL, {s['imm']}")
            L.append(f" {SHIFT_OP[s['type']]} AX, CL")
            L.append(" MOV [expval], AX")
            L.append(" PUSHF")
            L.append(" POP AX")
            L.append(" MOV [expflags], AX")
        else:  # IMUL dest=[reg], src=[src], imm
            srcval = 503 if name == "imul_a" else 0x2000
            L.append(f" MOV AX, {srcval}")
            L.append(f" MOV BX, {s['imm']}")
            L.append(" IMUL1 BX")
            L.append(" MOV [expval], AX")
            L.append(" PUSHF")
            L.append(" POP AX")
            L.append(" MOV [expflags], AX")
            L.append(f" MOV [srcval], {srcval}")
        # duplicate site (imul_b): re-point the shared trampoline stub at this checker
        if i > 0 and CASES[i - 1][1]["idx"] == s["idx"]:
            L.append(" MOV AX, [trampseg]")
            L.append(" MOV ES, AX")
            L.append(f" MOV DI, {s['key'] + s['len'] + 1}")
            L.append(f" MOV WORD ES:[DI], chk_{i}")
        # save SP baseline, push far return frame (CS, after_i)
        L.append(" MOV [esp0], SP")
        L.append(" PUSH CS")
        L.append(f" MOV AX, after_{i}")
        L.append(" PUSH AX")
        # far pointer setup before sentinels (uses AX as scratch)
        L.append(" MOV AX, [trampseg]")
        L.append(" MOV [farptr+2], AX")
        L.append(f" MOV WORD [farptr], {s['key']}")
        # live flags := expflags (shift/imul: native flags; push: known flags)
        L.append(" MOV AX, [expflags]")
        L.append(" PUSH AX")
        L.append(" POPF")
        # sentinels + operand (MOV does not touch flags)
        for r in ("AX", "CX", "DX", "BX", "SI", "DI", "BP"):
            L.append(f" MOV {r}, {SENT[r]}")
        if s["type"] in (1, 2, 3):
            L.append(f" MOV {REG[s['reg']]}, {OPERAND[s['type']]}")
        elif s["type"] == 4:
            L.append(f" MOV AX, [srcval]")
        L.append(" JMPL [farptr]")
        # checker, entered by far JMP from trampoline; stack: [retIP][retCS] (+imm for push)
        L.append(f"chk_{i}:")
        L.append(" MOV [g_ax], AX")
        L.append(" PUSHF")
        L.append(" POP AX")
        L.append(" MOV [gotflags], AX")
        L.append(" MOV [g_bx], BX")
        if s["type"] in (0, "cc"):
            L.append(" POP AX")
            L.append(f" CMP AX, {s['imm']}")
            L.append(f" JE vok_{i}")
            L.append(f" CALL fail_{i}")
            L.append(f"vok_{i}:")
        elif s["type"] == "ccpair":
            L.append(" POP AX")
            L.append(" CMP AX, 17767")
            L.append(f" JE sok3_{i}")
            L.append(f" CALL fail_{i}")
            L.append(f"sok3_{i}:")
            L.append(" POP AX")
            L.append(f" CMP AX, {s['imm']}")
            L.append(f" JE vok_{i}")
            L.append(f" CALL fail_{i}")
            L.append(f"vok_{i}:")
            L.append(" POP AX")
            L.append(f" CMP AX, {s['imm2']}")
            L.append(f" JE wok_{i}")
            L.append(f" CALL fail_{i}")
            L.append(f"wok_{i}:")
        checks = []
        if s["type"] in (1, 2, 3):
            checks.append((REG[s["reg"]], "[expval]"))
        elif s["type"] == 4:
            checks.append((REG[s["reg"]], "[expval]"))
            checks.append(("AX", "[srcval]"))
        for r in ("CX", "DX", "BX", "SI", "DI", "BP"):
            if s["type"] in (0, "cc", "ccpair") and r == "AX":
                continue
            if any(c[0] == r for c in checks):
                continue
            checks.append((r, SENT[r]))
        if s["type"] not in (0, "cc", "ccpair"):
            checks.append(("AX", SENT["AX"]) if not any(c[0] == "AX" for c in checks) else ("", 0))
        seen = []
        for r, v in checks:
            if not r or r in seen:
                continue
            seen.append(r)
            if r == "AX":  # AX itself holds the captured flags here; compare saved copy
                L.append(f" MOV AX, [g_ax]")
                L.append(f" CMP AX, {v}")
            else:
                L.append(f" CMP {r}, {v}")
            L.append(f" JE rok_{i}_{r}")
            L.append(f" CALL fail_{i}")
            L.append(f"rok_{i}_{r}:")
        # flags
        L.append(" MOV AX, [gotflags]")
        L.append(" CMP AX, [expflags]")
        L.append(f" JE fok_{i}")
        L.append(f" CALL fail_{i}")
        L.append(f"fok_{i}:")
        # SP: push case popped imm already -> esp0-4 ; else esp0-4 as well (ret frame only)
        L.append(" MOV AX, [esp0]")
        L.append(" SUB AX, 4")
        L.append(" CMP AX, SP")
        L.append(f" JE sok_{i}")
        L.append(f" CALL fail_{i}")
        L.append(f"sok_{i}:")
        L.append(" RETF")
        L.append(f"fail_{i}:")
        L.append(" INC BYTE [fails]")
        L.append(f" MOV BYTE [lastfail], {i}")
        L.append(" RET")
        L.append(f"after_{i}:")
        L.append(" MOV AX, [esp0]")
        L.append(" CMP AX, SP")
        L.append(f" JE aok_{i}")
        L.append(f" INC BYTE [fails]")
        L.append(f" MOV BYTE [lastfail], {50 + i}")
        L.append(f"aok_{i}:")

    # errcnt must be unchanged by valid sites
    L.append(" MOV AX, [tsrseg]")
    L.append(" MOV ES, AX")
    L.append(f" MOV AX, ES:[{ERRCNT_OFF}]")
    L.append(" CMP AX, [err0]")
    L.append(" JE nf_go")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 90")
    L.append("nf_go:")
    # not-found path: CD F8 at trampoline offset 0x10 (not a site key)
    L.append(" MOV [esp0], SP")
    L.append(" PUSH CS")
    L.append(" MOV AX, after_nf")
    L.append(" PUSH AX")
    L.append(" MOV AX, [trampseg]")
    L.append(" MOV [farptr+2], AX")
    L.append(" MOV WORD [farptr], 16")
    L.append(" JMPL [farptr]")
    L.append("chk_nf:")
    L.append(" MOV BYTE [nfhit], 1")
    L.append(" RETF")
    L.append("after_nf:")
    L.append(" MOV AX, [esp0]")
    L.append(" CMP AX, SP")
    L.append(" JE nf_sp_ok")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 91")
    L.append("nf_sp_ok:")
    L.append(" CMP BYTE [nfhit], 1")
    L.append(" JE nf_hit_ok")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 92")
    L.append("nf_hit_ok:")
    L.append(" MOV AX, [tsrseg]")
    L.append(" MOV ES, AX")
    L.append(f" MOV AX, ES:[{ERRCNT_OFF}]")
    L.append(" MOV BX, [err0]")
    L.append(" ADD BX, 1")
    L.append(" CMP AX, BX")
    L.append(" JE nf_err_ok")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 93")
    L.append("nf_err_ok:")
    # INT3 not in cctab: must chain to previous INT3 handler and resume after the CC byte
    L.append(" MOV AX, [trampseg]")
    L.append(" MOV ES, AX")
    L.append(" MOV DI, 36")
    L.append(" MOV AX, CS")
    L.append(" MOV ES:[DI], AX")
    L.append(" MOV [esp0], SP")
    L.append(" PUSH CS")
    L.append(" MOV AX, after_ccnf")
    L.append(" PUSH AX")
    L.append(" MOV AX, [trampseg]")
    L.append(" MOV [farptr+2], AX")
    L.append(" MOV WORD [farptr], 32")
    L.append(" JMPL [farptr]")
    L.append("chk_ccnf:")
    L.append(" MOV BYTE [ccnhit], 1")
    L.append(" RETF")
    L.append("after_ccnf:")
    L.append(" MOV AX, [esp0]")
    L.append(" CMP AX, SP")
    L.append(" JE ccnf_sp_ok")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 94")
    L.append("ccnf_sp_ok:")
    L.append(" CMP BYTE [ccnhit], 1")
    L.append(" JE ccnf_hit_ok")
    L.append(" INC BYTE [fails]")
    L.append(" MOV BYTE [lastfail], 95")
    L.append("ccnf_hit_ok:")
    # report
    L.append(" CMP BYTE [fails], 0")
    L.append(" JNE report_fail")
    L.append(" MOV DX, msg_pass")
    L.append(" JMP report")
    L.append("report_fail:")
    L.append(" MOV DX, msg_fail")
    L.append(" MOV AH, 9")
    L.append(" INT 21h")
    L.append(" JMP report2")
    L.append("report:")
    L.append(" MOV AH, 9")
    L.append(" INT 21h")
    L.append(" MOV AX, 4C00h")
    L.append(" INT 21h")
    L.append("report2:")
    L.append(" MOV AX, [g_ax]")
    L.append(" CALL prhex")
    L.append(" MOV DL, 32")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV AX, [g_bx]")
    L.append(" CALL prhex")
    L.append(" MOV DL, 32")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV AX, [expval]")
    L.append(" CALL prhex")
    L.append(" MOV DL, 32")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV AX, [gotflags]")
    L.append(" CALL prhex")
    L.append(" MOV DL, 32")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV AX, [expflags]")
    L.append(" CALL prhex")
    L.append(" MOV DL, 32")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV DL, [lastfail]")
    L.append(" MOV DH, 48")
    L.append("r2_tens:")
    L.append(" CMP DL, 10")
    L.append(" JB r2_done")
    L.append(" SUB DL, 10")
    L.append(" INC DH")
    L.append(" JMP r2_tens")
    L.append("r2_done:")
    L.append(" PUSH DX")
    L.append(" MOV DL, DH")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" POP DX")
    L.append(" ADD DL, 48")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV DL, 13")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV DL, 10")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" MOV AX, 4C01h")
    L.append(" INT 21h")
    L.append("prhex:")  # print AX as 4 hex digits
    L.append(" MOV BX, AX")
    L.append(" MOV CX, 4")
    L.append("prh1:")
    L.append(" PUSH CX")
    L.append(" MOV CL, 4")
    L.append(" ROL BX, CL")
    L.append(" MOV DL, BL")
    L.append(" AND DL, 15")
    L.append(" ADD DL, 48")
    L.append(" CMP DL, 57")
    L.append(" JBE prh2")
    L.append(" ADD DL, 7")
    L.append("prh2:")
    L.append(" MOV AH, 2")
    L.append(" INT 21h")
    L.append(" POP CX")
    L.append(" LOOP prh1")
    L.append(" RET")
    L.append("notsr:")
    L.append(" MOV DX, msg_notsr")
    L.append(" MOV AH, 9")
    L.append(" INT 21h")
    L.append(" MOV AX, 4C02h")
    L.append(" INT 21h")
    L.append('msg_pass: DB 84,56,56,80,65,83,83,13,10,36')
    L.append('msg_fail: DB 84,56,56,70,65,73,76,32,76,61,36')
    L.append('msg_notsr: DB 84,56,56,78,79,84,83,82,13,10,36')
    L.append("tsrseg: DW 0")
    L.append("trampseg: DW 0")
    L.append("err0: DW 0")
    L.append("esp0: DW 0")
    L.append("expflags: DW 0")
    L.append("gotflags: DW 0")
    L.append("expval: DW 0")
    L.append("srcval: DW 0")
    L.append("farptr: DW 0,0")
    L.append("fails: DB 0")
    L.append("g_ax: DW 0")
    L.append("g_bx: DW 0")
    L.append("lastfail: DB 0")
    L.append("nfhit: DB 0")
    L.append("ccnhit: DB 0")
    L.append("scratch: DW 17767")
    return "\n".join(L)

# pass 1: discover tramp offset
src1 = gen(0x100) + "\n" + "tramp:\n" + db_lines(bytes(0x2700)) + "\n"
code, labels = assemble(src1, org=0x100)
tramp = labels["tramp"]
pad = (16 - tramp % 16) % 16
maxkey = max(s["key"] + s["len"] + 8 for _, s in CASES)
print("tramp raw", hex(tramp), "pad", pad, "maxkey", hex(maxkey))
src2 = gen(tramp + pad)
if pad:
    src2 += "\n" + db_lines(bytes(pad))
src2 += "\n" + "tramp:\n" + db_lines(bytes(0x2700)) + "\n"
code, labels = assemble(src2, org=0x100)
assert labels["tramp"] % 16 == 0, hex(labels["tramp"])
img = bytearray(code)
written = set()
for i, (name, s) in enumerate(CASES):
    if s["idx"] in written:
        continue
    written.add(s["idx"])
    fo = labels["tramp"] + s["key"] - 0x100
    assert img[fo] == 0 and img[fo+1] == 0
    if s["type"] == "ccpair":
        img[fo] = 0xCC
        struct.pack_into("<H", img, fo + 1, s["imm2"])
        img[fo+3] = 0xCC
        struct.pack_into("<H", img, fo + 4, s["imm"])
        img[fo+6] = 0xFF
        img[fo+7] = 0x36
        struct.pack_into("<H", img, fo + 8, labels["scratch"])
        img[fo+10] = 0xEA
        struct.pack_into("<H", img, fo + 11, labels[f"chk_{i}"])
    else:
        img[fo] = 0xCD
        img[fo+1] = 0xF8
        img[fo+s["len"]] = 0xEA
        struct.pack_into("<H", img, fo + s["len"] + 1, labels[f"chk_{i}"])
fo = labels["tramp"] + 0x10 - 0x100
img[fo] = 0xCD
img[fo+1] = 0xF8
img[fo+2] = 0xEA
struct.pack_into("<H", img, fo + 3, labels["chk_nf"])
fo = labels["tramp"] + 0x20 - 0x100
img[fo] = 0xCC
img[fo+1] = 0xEA
struct.pack_into("<H", img, fo + 2, labels["chk_ccnf"])
out = ROOT / "artifacts/TEST88.COM"
out.write_bytes(bytes(img))
print("TEST88.COM", len(img), "tramp", hex(labels["tramp"]))
for name, s in CASES:
    print(" case", name, "idx", s["idx"], "key", hex(s["key"]), "type", s["type"], "reg", s["reg"], "imm", hex(s["imm"]), "len", s["len"])
