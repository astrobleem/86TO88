"""Tiny two-pass 8086 assembler for the subset used by WM88TSR/SHELL/TEST88.

Syntax (one per line, ';' comments):
  label:            MOV AX, [BP+4]     DB 1,2,"str"   DW label  ORG 100h
Registers: AX CX DX BX SP BP SI DI, AL CL DL BL AH CH DH BH, CS DS ES SS
Memory: [expr], [BX], [BP+disp], [SI+4], [disp16], CS:[..] etc.
Immediates: numbers (decimal/0x..), 'c', label
Instructions supported: the set emitted by our builders (see OPC map below).
Output: flat binary from ORG base (default 0). Labels are absolute (org+offset).
"""
import re, struct

REGS16 = {"AX":0,"CX":1,"DX":2,"BX":3,"SP":4,"BP":5,"SI":6,"DI":7}
REGS8 = {"AL":0,"CL":1,"DL":2,"BL":3,"AH":4,"CH":5,"DH":6,"BH":7}
SREGS = {"ES":0,"CS":1,"SS":2,"DS":3}
JCC = {"JE":0x74,"JZ":0x74,"JNE":0x75,"JNZ":0x75,"JB":0x72,"JNAE":0x72,"JAE":0x73,"JNB":0x73,
       "JBE":0x76,"JA":0x77,"JL":0x7C,"JGE":0x7D,"JLE":0x7E,"JG":0x7F,"JC":0x72,"JNC":0x73,
       "JS":0x78,"JNS":0x79,"JO":0x70,"JNO":0x71}

class AsmError(Exception): pass

def parse_num(tok, labels):
    tok = tok.strip()
    if tok in labels: return labels[tok]
    if labels is not None and getattr(parse_num,'probe',False) and tok.isidentifier(): return 0
    # simple label +/- number expressions
    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*([+-])\s*(.+)", tok)
    if m and (m.group(1) in labels or getattr(parse_num,'probe',False)):
        base = labels.get(m.group(1), 0)
        rest = parse_num(m.group(3), labels)
        return base + rest if m.group(2) == "+" else base - rest
    if tok.startswith("'") and tok.endswith("'") and len(tok) == 3: return ord(tok[1])
    sign = 1
    if tok.startswith("-"): sign, tok = -1, tok[1:]
    if tok.lower().startswith("0x"): v = int(tok, 16)
    elif tok.endswith("h") and re.fullmatch(r"[0-9A-Fa-f]+h", tok): v = int(tok[:-1], 16)
    elif tok.isdigit(): v = int(tok)
    else: raise AsmError(f"bad number/label {tok!r}")
    return sign * v

class Assembler:
    def __init__(self, org=0):
        self.org = org
        self.labels = {}
        self.out = bytearray()
        self.pc = org

    # ---------- operand parsing ----------
    def parse_operand(self, s):
        s = s.strip()
        size = None
        m = re.match(r"^(WORD|BYTE)\s+", s, flags=re.I)
        if m: size, s = m.group(1).upper(), s[m.end():]
        seg = None
        m = re.match(r"^(CS|DS|ES|SS):(.*)$", s, re.I)
        if m: seg, s = m.group(1).upper(), m.group(2).strip()
        u = s.upper()
        if u in REGS16: return ("r16", REGS16[u], seg, size)
        if u in REGS8: return ("r8", REGS8[u], seg, size)
        if u in SREGS: return ("sreg", SREGS[u], seg, size)
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            terms = re.findall(r"[+-]?[^+-]+", inner.replace(" ", ""))
            bases = []; disp_terms = []
            for p in terms:
                pu = p.upper().lstrip("+-")
                if pu in REGS16 and not p.startswith("-"):
                    bases.append(REGS16[pu])
                else:
                    disp_terms.append(p)
            base = tuple(sorted(bases)) if bases else None
            disp_tok = "".join(disp_terms) if disp_terms else "0"
            if disp_tok.startswith("+"): disp_tok = disp_tok[1:]
            return ("mem", (base, disp_tok), seg, size)
        return ("imm", s, seg, size)

    def modrm(self, regfield, memop):
        """Return (prefix_modrm_bytes) for mem operand given reg field."""
        base, disp_tok = memop[1]
        has_label = bool(re.search(r"[A-Za-z_]", str(disp_tok)))
        disp = parse_num(disp_tok, self.labels) if self.labels is not None else 0
        if base is None:
            return bytes([(0 << 6) | (regfield << 3) | 6]) + struct.pack("<H", disp & 0xFFFF), 2
        rmmap_combo = {(3,6):0,(3,7):1,(5,6):2,(5,7):3,(6,):4,(7,):5,(5,):6,(3,):7}
        if base not in rmmap_combo: raise AsmError(f"bad addressing {base}")
        rm = rmmap_combo[base]
        if base == (5,):  # BP: needs mod>=1
            mod = 1 if -128 <= disp <= 127 else 2
            if mod == 1: return bytes([(1 << 6) | (regfield << 3) | rm, disp & 0xFF]), 1
            return bytes([(2 << 6) | (regfield << 3) | rm]) + struct.pack("<H", disp & 0xFFFF), 2
        if disp == 0 and not has_label:
            return bytes([(0 << 6) | (regfield << 3) | rm]), 0
        if -128 <= disp <= 127 and not has_label:
            return bytes([(1 << 6) | (regfield << 3) | rm, disp & 0xFF]), 1
        return bytes([(2 << 6) | (regfield << 3) | rm]) + struct.pack("<H", disp & 0xFFFF), 2

    def seg_prefix(self, seg):
        return {"ES":0x26,"CS":0x2E,"SS":0x36,"DS":0x3E}[seg] if seg else None

    def emit(self, b): self.out += b; self.pc += len(b)

    def encode(self, mnem, ops, size_probe=False):
        """Encode one instruction; with dummy labels (size_probe) immediates use 0."""
        o = [self.parse_operand(x) for x in ops] if ops else []
        M = mnem.upper()
        out = bytearray()
        def segp(op):
            p = self.seg_prefix(op[2])
            if p is not None: out.append(p)
        if M == "NOP": out = bytearray([0x90])
        elif M == "RET": out = bytearray([0xC3])
        elif M == "RETF":
            if o: out = bytearray([0xCA]) + struct.pack("<H", parse_num(o[0][1], self.labels) & 0xFFFF)
            else: out = bytearray([0xCB])
        elif M == "RETN":
            if o: out = bytearray([0xC2]) + struct.pack("<H", parse_num(o[0][1], self.labels) & 0xFFFF)
            else: out = bytearray([0xC3])
        elif M == "IRET": out = bytearray([0xCF])
        elif M == "INT": out = bytearray([0xCD, parse_num(o[0][1], self.labels) & 0xFF])
        elif M == "HLT": out = bytearray([0xF4])
        elif M in ("CLC","STC","CLD","STD","CLI","STI","CMC"): out = bytearray([{"CLC":0xF8,"STC":0xF9,"CLD":0xFC,"STD":0xFD,"CLI":0xFA,"STI":0xFB,"CMC":0xF5}[M]])
        elif M == "PUSHF": out = bytearray([0x9C])
        elif M == "POPF": out = bytearray([0x9D])
        elif M == "PUSHA": raise AsmError("PUSHA is 186")
        elif M == "PUSH":
            if o[0][0] == "r16": out = bytearray([0x50 + o[0][1]])
            elif o[0][0] == "sreg": out = bytearray([0x06 + o[0][1]*8])
            elif o[0][0] == "mem":
                segp(o[0]); mb, _ = self.modrm(6, o[0]); out += bytearray([0xFF]) + mb
            else: raise AsmError("PUSH imm not allowed (186)")
        elif M == "POP":
            if o[0][0] == "r16": out = bytearray([0x58 + o[0][1]])
            elif o[0][0] == "sreg": out = bytearray([0x07 + o[0][1]*8])
            elif o[0][0] == "mem":
                segp(o[0]); mb, _ = self.modrm(0, o[0]); out += bytearray([0x8F]) + mb
            else: raise AsmError("bad POP")
        elif M == "JMP":
            target = parse_num(o[0][1], self.labels); rel = target - (self.pc + 3)
            out = bytearray([0xE9]) + struct.pack("<H", rel & 0xFFFF)
        elif M in JCC or M == "JCXZ" or M == "LOOP":
            opcode = {"JCXZ":0xE3, "LOOP":0xE2}.get(M, JCC.get(M))
            target_tok = o[0][1]
            target = self.labels.get(target_tok, None) if isinstance(target_tok, str) else None
            if target is None:
                try: target = parse_num(target_tok, self.labels)
                except AsmError: target = self.pc + 2
            rel = target - (self.pc + 2)
            if M in JCC and not (-100 <= rel <= 100):
                # long form: inverted Jcc +3, then near JMP (8086 has no near Jcc)
                rel16 = target - (self.pc + 5)
                out = bytearray([opcode ^ 1, 0x03, 0xE9]) + struct.pack("<H", rel16 & 0xFFFF)
            else:
                if not size_probe and not (-128 <= rel <= 127): raise AsmError(f"short jump out of range {M} -> {o[0][1]} at pc {self.pc:#x} rel {rel}")
                out = bytearray([opcode, rel & 0xFF])
        elif M == "JMPF":
            # JMP FAR label  (EA ptr32)
            target = parse_num(o[0][1], self.labels); segv = parse_num(o[1][1], self.labels)
            out = bytearray([0xEA]) + struct.pack("<HH", target & 0xFFFF, segv & 0xFFFF)
        elif M == "JMPL":  # jmp dword ptr [mem] far indirect FF /5
            p = self.seg_prefix(o[0][2]); mb, _ = self.modrm(5, o[0])
            out = (bytearray([p]) if p is not None else bytearray()) + bytearray([0xFF]) + mb
        elif M == "CALL":
            if o[0][0] == "mem": raise AsmError("use CALLF/CALLI")
            target = parse_num(o[0][1], self.labels); rel = target - (self.pc + 3)
            out = bytearray([0xE8]) + struct.pack("<H", rel & 0xFFFF)
        elif M == "CALLF":  # call far immediate: CALLF off, seg
            off = parse_num(o[0][1], self.labels); segv = parse_num(o[1][1], self.labels)
            out = bytearray([0x9A]) + struct.pack("<HH", off & 0xFFFF, segv & 0xFFFF)
        elif M == "CALLI":  # call dword ptr [mem] FF /3
            p = self.seg_prefix(o[0][2]); mb, _ = self.modrm(3, o[0])
            out = (bytearray([p]) if p is not None else bytearray()) + bytearray([0xFF]) + mb
        elif M == "MOV":
            d, s = o
            if d[0] == "r16" and s[0] == "imm": out = bytearray([0xB8 + d[1]]) + struct.pack("<H", parse_num(s[1], self.labels) & 0xFFFF)
            elif d[0] == "r8" and s[0] == "imm": out = bytearray([0xB0 + d[1], parse_num(s[1], self.labels) & 0xFF])
            elif d[0] == "r16" and s[0] == "r16": out = bytearray([0x8B, (3 << 6) | (d[1] << 3) | s[1]])
            elif d[0] == "r8" and s[0] == "r8": out = bytearray([0x8A, (3 << 6) | (d[1] << 3) | s[1]])
            elif d[0] == "r16" and s[0] == "sreg": out = bytearray([0x8C, (3 << 6) | (s[1] << 3) | d[1]])
            elif d[0] == "sreg" and s[0] == "r16": out = bytearray([0x8E, (3 << 6) | (d[1] << 3) | s[1]])
            elif d[0] == "r16" and s[0] == "mem":
                segp(s); mb, _ = self.modrm(d[1], s); out += bytearray([0x8B]) + mb
            elif d[0] == "r8" and s[0] == "mem":
                segp(s); mb, _ = self.modrm(d[1], s); out += bytearray([0x8A]) + mb
            elif d[0] == "mem" and s[0] == "r16":
                segp(d); mb, _ = self.modrm(s[1], d); out += bytearray([0x89]) + mb
            elif d[0] == "mem" and s[0] == "r8":
                segp(d); mb, _ = self.modrm(s[1], d); out += bytearray([0x88]) + mb
            elif d[0] == "mem" and s[0] == "imm":
                segp(d)
                if len(d) > 3 and d[3] == "BYTE":
                    mb, _ = self.modrm(0, d); out += bytearray([0xC6]) + mb + bytes([parse_num(s[1], self.labels) & 0xFF])
                else:
                    # default word if no size hint (we always use word in our code with MOVW)
                    mb, _ = self.modrm(0, d); out += bytearray([0xC7]) + mb + struct.pack("<H", parse_num(s[1], self.labels) & 0xFFFF)
            elif d[0] == "r16" and s[0] == "mem": pass
            else: raise AsmError(f"unsupported MOV {ops}")
        elif M in ("MOVW","MOVB"):  # explicit-size mem,imm and mem loads handled via MOV above
            d, s = o
            if s[0] == "imm" and d[0] == "mem":
                segp(d); mb, _ = self.modrm(0, d)
                if M == "MOVW": out += bytearray([0xC7]) + mb + struct.pack("<H", parse_num(s[1], self.labels) & 0xFFFF)
                else: out += bytearray([0xC6]) + mb + bytes([parse_num(s[1], self.labels) & 0xFF])
            else: raise AsmError("MOVW/MOVB only mem,imm")
        elif M == "LEA":
            d, s = o; segp(s); mb, _ = self.modrm(d[1], s); out += bytearray([0x8D]) + mb
        elif M in ("ADD","SUB","CMP","AND","OR","XOR","TEST"):
            grp = {"ADD":0,"OR":1,"AND":4,"SUB":5,"XOR":6,"CMP":7,"TEST":None}[M]
            d, s = o
            if M == "TEST":
                if d[0]=="r16" and s[0]=="r16": out = bytearray([0x85, (3<<6)|(s[1]<<3)|d[1]])
                elif d[0]=="mem" and s[0]=="imm":
                    segp(d); mb,_=self.modrm(0,d)
                    if len(d) > 3 and d[3] == "BYTE":
                        out += bytearray([0xF6])+mb+bytes([parse_num(s[1],self.labels)&0xFF])
                    else:
                        out += bytearray([0xF7])+mb+struct.pack("<H", parse_num(s[1],self.labels)&0xFFFF)
                elif d[0]=="r16" and s[0]=="imm": out = bytearray([0xF7,(3<<6)|(0<<3)|d[1]])+struct.pack("<H", parse_num(s[1],self.labels)&0xFFFF)
                else: raise AsmError(f"TEST {ops}")
            elif d[0] == "r16" and s[0] == "r16":
                opc = {"ADD":0x03,"SUB":0x2B,"CMP":0x3B,"AND":0x23,"OR":0x0B,"XOR":0x33}[M]
                out = bytearray([opc, (3 << 6) | (d[1] << 3) | s[1]])
            elif d[0] == "r8" and s[0] == "r8":
                opc = {"ADD":0x02,"SUB":0x2A,"CMP":0x3A,"AND":0x22,"OR":0x0A,"XOR":0x32}[M]
                out = bytearray([opc, (3 << 6) | (d[1] << 3) | s[1]])
            elif d[0] == "r16" and s[0] == "mem":
                opc = {"ADD":0x03,"SUB":0x2B,"CMP":0x3B,"AND":0x23,"OR":0x0B,"XOR":0x33}[M]
                segp(s); mb, _ = self.modrm(d[1], s); out += bytearray([opc]) + mb
            elif d[0] == "mem" and s[0] == "r16":
                opc = {"ADD":0x01,"SUB":0x29,"CMP":0x39,"AND":0x21,"OR":0x09,"XOR":0x31}[M]
                segp(d); mb, _ = self.modrm(s[1], d); out += bytearray([opc]) + mb
            elif d[0] == "mem" and s[0] == "r8":
                opc = {"ADD":0x00,"SUB":0x28,"CMP":0x38,"AND":0x20,"OR":0x08,"XOR":0x30}[M]
                segp(d); mb, _ = self.modrm(s[1], d); out += bytearray([opc]) + mb
            elif d[0] == "r8" and s[0] == "mem":
                opc = {"ADD":0x02,"SUB":0x2A,"CMP":0x3A,"AND":0x22,"OR":0x0A,"XOR":0x32}[M]
                segp(s); mb, _ = self.modrm(d[1], s); out += bytearray([opc]) + mb
            elif d[0] in ("r16","mem") and s[0] == "imm":
                v = parse_num(s[1], self.labels)
                if d[0] == "r16" and -128 <= v <= 127 and M != "TEST":
                    out = bytearray([0x83, (3 << 6) | (grp << 3) | d[1], v & 0xFF])
                elif d[0] == "r16":
                    if d[1] == 0 and M in ("ADD","SUB","CMP","AND","OR","XOR"):
                        acc = {"ADD":0x05,"SUB":0x2D,"CMP":0x3D,"AND":0x25,"OR":0x0D,"XOR":0x35}[M]
                        out = bytearray([acc]) + struct.pack("<H", v & 0xFFFF)
                    else:
                        out = bytearray([0x81, (3 << 6) | (grp << 3) | d[1]]) + struct.pack("<H", v & 0xFFFF)
                elif d[0] == "mem" and len(d) > 3 and d[3] == "BYTE":
                    segp(d); mb, _ = self.modrm(grp, d); out += bytearray([0x80]) + mb + bytes([v & 0xFF])
                else:
                    segp(d); mb, _ = self.modrm(grp, d); out += bytearray([0x81]) + mb + struct.pack("<H", v & 0xFFFF)
            elif d[0] == "r8" and s[0] == "imm":
                out = bytearray([0x80, (3 << 6) | (grp << 3) | d[1], parse_num(s[1], self.labels) & 0xFF])
            else: raise AsmError(f"unsupported {M} {ops}")
        elif M in ("INC","DEC"):
            if o[0][0] == "r16": out = bytearray([(0x40 if M=="INC" else 0x48) + o[0][1]])
            elif o[0][0] == "mem":
                segp(o[0]); mb, _ = self.modrm(0 if M=="INC" else 1, o[0])
                out += bytearray([0xFE if len(o[0]) > 3 and o[0][3] == "BYTE" else 0xFF]) + mb
            elif o[0][0] == "r8": out = bytearray([0xFE, (3<<6)|((0 if M=="INC" else 1)<<3)|o[0][1]])
            else: raise AsmError(M)
        elif M in ("SHL","SHR","SAR","ROL","ROR"):
            op = {"ROL":0,"ROR":1,"SHL":4,"SHR":5,"SAR":7}[M]
            d, s = o
            if s[0] == "imm" and parse_num(s[1], self.labels) == 1:
                if d[0]=="r16": out = bytearray([0xD1, (3<<6)|(op<<3)|d[1]])
                elif d[0]=="r8": out = bytearray([0xD0, (3<<6)|(op<<3)|d[1]])
                elif d[0]=="mem": segp(d); mb,_=self.modrm(op,d); out += bytearray([0xD0 if len(d) > 3 and d[3] == "BYTE" else 0xD1])+mb
                else: raise AsmError(M)
            elif s[0] == "r8" and s[1] == 1:  # CL
                if d[0]=="r16": out = bytearray([0xD3, (3<<6)|(op<<3)|d[1]])
                elif d[0]=="r8": out = bytearray([0xD2, (3<<6)|(op<<3)|d[1]])
                elif d[0]=="mem": segp(d); mb,_=self.modrm(op,d); out += bytearray([0xD2 if len(d) > 3 and d[3] == "BYTE" else 0xD3])+mb
                else: raise AsmError(M)
            else: raise AsmError(f"{M} needs 1 or CL")
        elif M == "IMUL1":  # IMUL r16 (F7 /5) one-operand, DX:AX = AX * r/m
            if o[0][0]=="r16": out = bytearray([0xF7, (3<<6)|(5<<3)|o[0][1]])
            elif o[0][0]=="mem": segp(o[0]); mb,_=self.modrm(5,o[0]); out += bytearray([0xF7])+mb
            else: raise AsmError(M)
        elif M == "MUL1":
            if o[0][0]=="r16": out = bytearray([0xF7, (3<<6)|(4<<3)|o[0][1]])
            else: raise AsmError(M)
        elif M in ("NEG","NOT"):
            grp = 3 if M=="NEG" else 2
            if o[0][0]=="r16": out = bytearray([0xF7,(3<<6)|(grp<<3)|o[0][1]])
            else: raise AsmError(M)
        elif M == "XCHG":
            d,s=o
            if d[0]=="r16" and s[0]=="r16":
                if d[1]==0: out=bytearray([0x90+s[1]])
                elif s[1]==0: out=bytearray([0x90+d[1]])
                else: out=bytearray([0x87,(3<<6)|(d[1]<<3)|s[1]])
            else: raise AsmError("XCHG")
        elif M == "LODSB": out=bytearray([0xAC])
        elif M == "STOSB": out=bytearray([0xAA])
        elif M == "MOVSB": out=bytearray([0xA4])
        elif M == "SCASB": out=bytearray([0xAE])
        elif M == "CBW": out=bytearray([0x98])
        elif M == "CWD": out=bytearray([0x99])
        elif M == "IN":
            if o[0][1]==0: out=bytearray([0xEC]) if len(o)>1 else bytearray([0xEC])
            else: raise AsmError("IN")
        elif M == "OUT":
            out=bytearray([0xEE])  # OUT DX, AL (only form used)
        else: raise AsmError(f"unsupported instruction {M} {ops}")
        return bytes(out)

    def assemble(self, text):
        lines = []
        for raw in text.splitlines():
            line = raw.split(";")[0].rstrip()
            if not line.strip(): continue
            lines.append(line)
        # Iterating passes: labels from the previous pass size the next;
        # far Jcc auto-expansion shifts labels, so iterate to a fixpoint.
        labels = {}
        for iteration in range(15):
            parse_num.probe = (iteration == 0)
            self.labels = labels
            self.out = bytearray(); self.pc = self.org
            new_labels = {}
            for line in lines:
                s = line.strip()
                while True:
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", s)
                    if m:
                        new_labels[m.group(1)] = self.pc
                        s = m.group(2).strip()
                        if not s: break
                    else: break
                if not s: continue
                if s.upper().startswith("ORG "):
                    self.org = parse_num(s.split(None,1)[1], self.labels); self.pc = self.org; continue
                if s.upper().startswith("DB ") or s.upper().startswith("DW ") or s.upper().startswith("DD "):
                    kind = s[:2].upper(); rest = s[3:].strip()
                    items = [x.strip() for x in rest.split(",")]
                    for it in items:
                        if kind == "DB":
                            if it.startswith('"') and it.endswith('"'): b = it[1:-1].encode()
                            elif it == "?": b = b"\x00"
                            else: b = bytes([parse_num(it, self.labels) & 0xFF])
                            self.emit(b)
                        elif kind == "DW":
                            self.emit(struct.pack("<H", parse_num(it, self.labels) & 0xFFFF))
                        else:
                            self.emit(struct.pack("<I", parse_num(it, self.labels) & 0xFFFFFFFF))
                    continue
                parts = s.split(None, 1)
                mnem = parts[0]; ops = []
                if len(parts) > 1:
                    ops = [x.strip() for x in parts[1].split(",")]
                enc = self.encode(mnem, ops, size_probe=(iteration == 0))
                self.emit(enc)
            if new_labels == labels and iteration > 0:
                labels = new_labels
                break
            labels = new_labels
        parse_num.probe = False
        self.labels = labels
        return bytes(self.out)

def assemble(text, org=0):
    a = Assembler(org)
    data = a.assemble(text)
    return data, a.labels
