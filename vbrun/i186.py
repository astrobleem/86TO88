"""80186 instructions -> 8088 code, rewritten in place by the converter.

The VB runtime (and FIELD100) use PUSH imm, SHL/SHR/SAR r,imm8, ENTER, LEAVE and
IMUL r,r/m,imm.  On a stock 8088 these opcodes do not fault, they alias (6A runs as a
conditional jump, C1 as RET, C8 as RETF), so every one that can execute has to be gone
before the code runs.  Each site is replaced by code of the same length, so no other
instruction moves and no jump target inside a segment changes:

  PUSH imm16  (68 iw, 3 bytes)   CALL near  -> per-segment trampoline for that value
                                              (per site when a relocation covers iw)
  PUSH imm8   (6A ib, 2 bytes)   INT 3 / ib -> resident handler (asm/i186.asm) pushes
                                              the sign-extended byte and skips it
  SHx r,imm8  (C0/C1, 3 bytes)   CALL near  -> per-segment trampoline: SHx r,1 n times
  ENTER n,0   (C8, 4 bytes)      JMP near   -> PUSH BP / MOV BP,SP / LEA SP,[BP-n] / JMP back
  LEAVE+RETF n (C9 CA, 4 bytes)  JMP near   -> MOV SP,BP / POP BP / RETF n
  IMUL r,m,imm (6B/69)           JMP near   -> AX/DX saved, IMUL m by AX = imm, result to r

Flags: CALL/RET/JMP/PUSH/POP/MOV/XCHG/LEA leave the flags alone, so a site whose
original leaves them alone (PUSH, ENTER, LEAVE) still does; the shift and IMUL
trampolines set them the way the original instruction does (defined flags).

Which bytes are code comes from a recursive descent from every entry, relocation target,
PUSH CS/CALL target and CS: jump table, which stops after calls into the runtime's
error raiser (they never return, and the bytes after them are handler metadata).
"""
import struct, collections, sys
import capstone
from capstone import x86

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
u16 = lambda b, o: struct.unpack_from('<H', b, o)[0]


def load(d):
    ne = struct.unpack_from('<I', d, 0x3c)[0]
    sto, = struct.unpack_from('<H', d, ne + 0x22); al, = struct.unpack_from('<H', d, ne + 0x32)
    n, = struct.unpack_from('<H', d, ne + 0x1c)
    segs = []
    for i in range(n):
        o, l, f, m = struct.unpack_from('<HHHH', d, ne + sto + 8 * i)
        base = o << al; ln = l or (0x10000 if o else 0)
        code = bytes(d[base:base + ln]) if o else b''
        recs = []
        if o and f & 0x100:
            cnt = u16(d, base + ln)
            recs = [struct.unpack_from('<BBHHH', d, base + ln + 2 + 8 * k) for k in range(cnt)]
        segs.append(dict(n=i + 1, flags=f, code=code, recs=recs))
    ent = {}
    eto, = struct.unpack_from('<H', d, ne + 4); q = ne + eto; o = 1
    while d[q]:
        c, t = d[q], d[q + 1]; q += 2
        for k in range(c):
            if t == 0: pass
            elif t == 0xff: ent[o] = (d[q + 3], u16(d, q + 4)); q += 6
            else: ent[o] = (t, u16(d, q + 1)); q += 3
            o += 1
    csip = (u16(d, ne + 0x16), u16(d, ne + 0x14))
    return segs, ent, csip


def chain(code, off, additive):
    if additive: return [off]
    out = []; p = off
    while p != 0xffff and p + 1 < len(code) and len(out) < 10000:
        out.append(p); p = u16(code, p)
    return out


def prologue(code, o):
    """a far procedure entry: optional DS-load/nop preamble, then (inc bp) push bp/mov bp,sp or enter"""
    b = code[o:o + 12]; i = 0
    for pre in (b'\x8c\xd8\x90', b'\x1e\x58\x90', b'\x8c\xd0\x90', b'\x90\x90\x90'):
        if b.startswith(pre): i = 3; break
    else:
        if b[:1] == b'\xb8': i = 3
    if b[i:i + 1] == b'\x45': i += 1
    return b[i:i + 3] == b'\x55\x8b\xec' or b[i:i + 1] == b'\xc8'


def roots_of(segs, ent, csip):
    roots = collections.defaultdict(set)
    if csip[0]: roots[csip[0]].add(csip[1])
    for o, (s, off) in ent.items(): roots[s].add(off)
    for s in segs:
        code = s['code']
        for t, fl, off, a, b in s['recs']:
            if fl & 3: continue
            if a == 0xff:
                if b in ent: roots[ent[b][0]].add(ent[b][1])
                continue
            if not 1 <= a <= len(segs) or segs[a - 1]['flags'] & 1: continue
            add = bool(fl & 4)
            if t & 15 == 3:
                for p in chain(code, off, add):
                    roots[a].add(u16(code, p) if add else b)
            elif t & 15 == 5:          # offset of a procedure (push offset / mov reg,offset)
                for p in chain(code, off, add):
                    roots[a].add(u16(code, p) if add else b)
            elif t & 15 == 2:          # selector of a far call/jmp or of a far pointer (dw off, seg):
                for p in chain(code, off, add):    # the offset is the 2 bytes before
                    if p < 2: continue
                    o = u16(code, p - 2); tc = segs[a - 1]['code']
                    if p >= 3 and not s['flags'] & 1 and code[p - 3] in (0x9a, 0xea): roots[a].add(o)
                    elif o < len(tc) and prologue(tc, o): roots[a].add(o)
        if not s['flags'] & 1:
            for p in range(len(code) - 4):          # push cs / call near: same-segment far procs
                if code[p] == 0x0e and code[p + 1] == 0xe8:
                    roots[s['n']].add((p + 4 + struct.unpack_from('<h', code, p + 2)[0]) & 0xffff)
    return roots


def switch_count(code, pc):
    """entries of the MSC switch table used by the jump at pc: 'cmp ax,N' within the 12
    bytes before (then 'ja default' or 'jbe ok / jmp default', 'shl ax,1 / xchg bx,ax')"""
    for k in range(4, 13):
        q = pc - k
        if q < 0: break
        if code[q] == 0x3d: return u16(code, q + 1) + 1
        if code[q] == 0x83 and code[q + 1] == 0xf8 and code[q + 2] < 0x80: return code[q + 2] + 1
    return 0


INT3_IMM = False      # analysing converted output: CC is INT 3 + the PUSH imm8 byte

def descend(code, roots, noreturn=(), blocked=frozenset()):
    """-> (insns: off -> ins, targets: set of direct branch/call targets, ft_only: offsets
    reached only by falling through a near or far call)"""
    insns = {}; targets = set(roots); todo = [(r, False) for r in roots]; tabs = set()
    via = collections.defaultdict(set)
    while todo:
        pc, after_call = todo.pop()
        while 0 <= pc < len(code):
            if pc in blocked: break                 # would start inside known code: wrong path
            via[pc].add(after_call)
            if pc in insns: break
            ins = next(md.disasm(code[pc:pc + 16], pc, 1), None)
            if ins is None: break
            insns[pc] = ins
            m = ins.mnemonic; b = ins.bytes; nxt = pc + ins.size; after_call = False
            if INT3_IMM and b[0] == 0xcc: nxt += 1
            if b[0] in (0xc2, 0xc3, 0xca, 0xcb, 0xcf, 0xf4) or m in ('ret', 'retf', 'iret', 'hlt'): break
            if b[0] == 0xea: break
            if m == 'jmp':
                op = ins.operands[0]
                if op.type == x86.X86_OP_IMM:
                    t = op.imm & 0xffff; targets.add(t); todo.append((t, False))
                elif op.type == x86.X86_OP_MEM and ins.reg_name(op.mem.segment) == 'cs' and op.mem.disp and \
                        (op.mem.base or op.mem.index) and (op.mem.disp & 0xffff) not in tabs:
                    # MSC switch: the table follows the jump and ends where the first case begins
                    tab = op.mem.disp & 0xffff; tabs.add(tab); p = tab; lim = len(code)
                    if not nxt <= tab <= nxt + 2: break
                    cnt = switch_count(code, pc)
                    if cnt:                  # bounded by the compare: exactly cnt entries
                        for k in range(cnt):
                            t = u16(code, tab + 2 * k)
                            if t < len(code): targets.add(t); todo.append((t, False))
                        break
                    while p + 2 <= lim and (p - tab) < 1024:
                        t = u16(code, p)
                        if not p + 2 <= t < len(code): break
                        lim = min(lim, t); targets.add(t); todo.append((t, False)); p += 2
                break
            if (0x70 <= b[0] <= 0x7f or b[0] in (0xe0, 0xe1, 0xe2, 0xe3)) and ins.operands[0].type == x86.X86_OP_IMM:
                t = ins.operands[0].imm & 0xffff; targets.add(t); todo.append((t, False))
            elif b[0] == 0xe8:
                t = ins.operands[0].imm & 0xffff; targets.add(t); todo.append((t, False))
                if t in noreturn: break
                after_call = True
            elif b[0] == 0x9a:
                if (code[pc + 1:pc + 5]) in noreturn: break
                after_call = True
            pc = nxt
    ft_only = {o for o, v in via.items() if v == {True}}
    return insns, targets, ft_only


def kind(ins):
    """('push16'|'push8'|'shift'|'enter'|'leave'|'imul'|'other186'|None)"""
    b = bytes(ins.bytes); p = 0
    while p < len(b) and b[p] in (0x26, 0x2e, 0x36, 0x3e, 0xf0, 0xf2, 0xf3): p += 1
    op = b[p] if p < len(b) else 0
    if op == 0x68: return 'push16'
    if op == 0x6a: return 'push8'
    if op in (0xc0, 0xc1): return 'shift'
    if op == 0xc8: return 'enter'
    if op == 0xc9: return 'leave'
    if op in (0x69, 0x6b): return 'imul'
    if op in (0x60, 0x61, 0x62, 0x6c, 0x6d, 0x6e, 0x6f, 0x0f) or 0x64 <= op <= 0x67: return 'other186'
    return None


SIMPLE = {'mov', 'pop', 'push', 'xor', 'sub', 'add', 'or', 'and', 'inc', 'dec', 'cwd', 'cbw', 'xchg', 'lea'}
BAD = {'in', 'out', 'insb', 'insw', 'outsb', 'outsw', 'hlt', 'arpl', 'bound', 'into', 'iret', 'lock', 'int1', 'salc'}

def plausible(code, t, limit=300):
    """straight-line decode from t reaches an unconditional transfer without undecodable
    bytes, 80186-only forms other than the ones the runtime uses, or I/O and other
    instructions that do not occur in this code"""
    pc = t
    for _ in range(limit):
        ins = next(md.disasm(code[pc:pc + 16], pc, 1), None)
        if ins is None or ins.mnemonic in BAD or kind(ins) == 'other186': return False
        b = ins.bytes[0]
        if b in (0xc2, 0xc3, 0xca, 0xcb, 0xe9, 0xeb, 0xea) or ins.mnemonic == 'jmp': return True
        pc += ins.size
        if pc >= len(code): return False
    return False


def heuristic_roots(segs):
    """code the descent cannot see: far procedures (MSC prologues) reached through tables the
    runtime builds itself, and p-code handlers, which are only reached from the program's
    p-code (threaded code: the handler offsets are in the EXE). A handler starts after an
    unconditional jump, usually with a descriptor word (high byte 0) in front of it, some
    (2:3765) without one; so code right after any unconditional jump or return is a
    candidate too."""
    out = collections.defaultdict(set)
    for s in segs:
        c = s['code']
        if s['flags'] & 1 or not c: continue
        def after_jump(o):
            return (c[o - 2:o] == b'\xff\xe0' or (o >= 2 and c[o - 2] == 0xeb) or (o >= 3 and c[o - 3] == 0xe9)
                    or c[o - 1] in (0xc3, 0xcb) or (o >= 3 and c[o - 3] in (0xc2, 0xca)))
        for o in range(4, len(c) - 4):
            if c[o] == 0xc8:                       # ENTER n,0 right after a return/jump
                ok = c[o + 3] == 0 and after_jump(o)
            else:
                ok = prologue(c, o)
            if ok and plausible(c, o): out[s['n']].add(o)
            if after_jump(o):
                if c[o + 1] == 0 and plausible(c, o + 2): out[s['n']].add(o + 2)
                elif plausible(c, o): out[s['n']].add(o)      # code right after a jump/return
    return out


def census(d, noreturn_by_seg=None, cur=None, heuristic=True):
    """80186 sites reachable in the module d (the original file).  With cur = the current
    segment list (same numbering, code possibly patched and extended by the converter),
    descend the current code instead: from the original roots plus every relocation
    target the converter added beyond a segment's original end (its appended stubs)."""
    segs0, ent, csip = load(d)
    roots = roots_of(segs0, ent, csip)
    segs = segs0
    if cur is not None:
        r2 = roots_of(cur, ent, csip)
        for s in segs0:
            roots[s['n']] |= {t for t in r2[s['n']] if t >= len(s['code'])}
        segs = cur
    cand_by_seg = heuristic_roots(segs0) if heuristic else {}
    out = []
    for s in segs:
        if s['flags'] & 1 or not s['code']: continue
        k = s['n']; c = s['code']; nr = (noreturn_by_seg or {}).get(k, set())
        insns, targets, ft = descend(c, roots[k], nr)          # definite code
        if roots[k] and cand_by_seg.get(k):
            # heuristic roots, accepted one at a time if their code agrees with the code
            # already accepted (definite first); their paths stop where they would start
            # inside a known instruction
            starts = set(insns); cover = set()
            for o, i in insns.items(): cover.update(range(o + 1, o + i.size))
            hroots = set()
            for t in sorted(cand_by_seg[k]):
                if t in starts or t in cover or t >= len(segs0[k - 1]['code']): continue
                hi, _, _ = descend(c, {t}, nr, cover)
                if any(kind(i) in ('other186', 'imul') or i.mnemonic in BAD or
                       (o not in starts and set(range(o + 1, o + i.size)) & starts) for o, i in hi.items()):
                    continue
                hroots.add(t); starts |= set(hi)
                for o, i in hi.items(): cover.update(range(o + 1, o + i.size))
            if hroots:
                hi, ht, hft = descend(c, hroots, nr, cover - set(insns))
                for o, i in hi.items(): insns.setdefault(o, i)
                targets = targets | ht
        for off, ins in sorted(insns.items()):
            kd = kind(ins)
            if not kd: continue
            # the instruction just before (moved together with LEAVE + RET/RETF when needed)
            prev = next((p for p in range(off - 1, max(off - 7, -1), -1) if p in insns and p + insns[p].size == off), None)
            simple = prev is not None and insns[prev].mnemonic in SIMPLE and not any(
                o in targets for o in range(prev + 1, off + 2))
            out.append(dict(seg=k, off=off, kind=kd, ins=ins, targets=targets, ft=off in ft,
                            prev=prev if simple else None))
    return out, segs


# ---------------------------------------------------------------------------------------- rewrite

class Relocs:
    """The relocation records of one segment as (type, flags, [sites], a, b); chains are
    followed in the segment's current code and re-linked on output."""
    def __init__(self, code, recs):
        self.items = []
        for r in recs:
            t, fl, off, a, b = struct.unpack('<BBHHH', r)
            self.items.append([t, fl, chain(code, off, bool(fl & 4)), a, b])
    def find(self, site):
        for it in self.items:
            if site in it[2]: return it
        return None
    def move(self, code, old, new):
        it = self.find(old); assert it is not None
        if it[1] & 4:
            code[new:new + 2] = code[old:old + 2]; it[2] = [new]
        else:
            it[2].remove(old); self.items.append([it[0], it[1], [new], it[3], it[4]])
    def records(self, code):
        out = []
        for t, fl, sites, a, b in self.items:
            if not sites: continue
            if fl & 4:
                for s in sites: out.append(struct.pack('<BBHHH', t, fl, s, a, b))
                continue
            sites = sorted(sites)
            for j, p in enumerate(sites):
                struct.pack_into('<H', code, p, sites[j + 1] if j + 1 < len(sites) else 0xffff)
            out.append(struct.pack('<BBHHH', t, fl, sites[0], a, b))
        return out


def merge_chains(code, recs):
    """One record per (type, flags, target) for chained (non-additive) selector, offset and
    far-pointer fixups: the converter leaves many single-site records with the same target,
    and the real-mode loader reads every record of a segment into a buffer at load time."""
    rel = Relocs(code, recs)
    groups = {}; out = []
    for it in rel.items:
        t, fl, sites, a, b = it
        if fl & 4 or t & 15 not in (2, 3, 5) or not sites:
            out.append(it); continue
        k = (t, fl, a, b)
        if k in groups: groups[k][2].extend(sites)
        else: groups[k] = [t, fl, list(sites), a, b]; out.append(groups[k])
    rel.items = out
    return rel.records(code)


def t_push16(imm):
    # push ax / push bp / mov bp,sp / mov ax,[bp+4] / mov word [bp+4],imm / xchg ax,[bp+2] / pop bp / ret
    c = b'\x50\x55\x8b\xec\x8b\x46\x04\xc7\x46\x04' + struct.pack('<H', imm) + b'\x87\x46\x02\x5d\xc3'
    return c, 10                                    # offset of imm (relocation site)


def t_shift(b):
    """b = C0/C1 modrm ib (mod 3) -> D0/D1 modrm, n times; ret"""
    op = 0xd0 if b[0] == 0xc0 else 0xd1
    return bytes([op, b[1]]) * (b[2] & 31) + b'\xc3'


def jmp(frm, to):
    return b'\xe9' + struct.pack('<H', (to - (frm + 3)) & 0xffff)


def t_enter(b, back, at):
    n = u16(b, 1); assert b[3] == 0, 'ENTER with nesting level'
    lea = b'\x8d\x66' + struct.pack('<b', -n) if n <= 128 else b'\x8d\xa6' + struct.pack('<h', -n)
    c = b'\x55\x8b\xec' + lea
    return c + jmp(at + len(c), back)


def t_leave_retf(b):
    return b'\x8b\xe5\x5d' + bytes(b[1:])           # mov sp,bp / pop bp / retf n (or ret/retf)


R16 = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']
def t_imul(b, back, at):
    """b = [prefixes] 69/6B modrm [disp] imm  ->  dest = r/m * imm (16-bit), CF/OF as IMUL"""
    p = 0
    while b[p] in (0x26, 0x2e, 0x36, 0x3e): p += 1
    pre = bytes(b[:p]); op = b[p]; modrm = b[p + 1]
    mod, reg, rm = modrm >> 6, modrm >> 3 & 7, modrm & 7
    isz = 2 if op == 0x69 else 1
    ea = bytes(b[p + 2:len(b) - isz])
    imm = u16(b, len(b) - 2) if op == 0x69 else (b[-1] - 256 if b[-1] > 127 else b[-1]) & 0xffff
    assert reg != 4 and not (mod == 3 and rm == 4)
    c = bytearray()
    save = [r for r in (0, 2) if r != reg]          # AX, DX are clobbered; the destination is not restored
    for r in save: c += bytes([0x50 + r])
    if mod == 3 and rm == 0:                        # source is AX: multiply AX by DX = imm
        c += b'\xba' + struct.pack('<H', imm) + b'\xf7\xea'                 # mov dx,imm / imul dx
    else:
        if mod == 3 and rm == 2: src = b'\xf7\xea'                          # imul dx (DX still intact)
        else: src = pre + bytes([0xf7, (mod << 6) | (5 << 3) | rm]) + ea    # imul word r/m
        c += b'\xb8' + struct.pack('<H', imm) + src                         # mov ax,imm / imul src
    if reg != 0: c += bytes([0x8b, 0xc0 | (reg << 3)])                      # mov reg,ax
    for r in reversed(save): c += bytes([0x58 + r])
    return bytes(c) + jmp(at + len(c), back)


def rewrite(segs_orig, blobs, sites, stats, int3=True):
    """Rewrite every site in blobs[(seg-1)] = (code bytearray, packed records).  Returns
    a list of problems (sites left alone); the caller decides whether that is fatal."""
    problems = []
    byseg = collections.defaultdict(list)
    for s in sites: byseg[s['seg']].append(s)
    for sg, lst in byseg.items():
        code, recs = blobs[sg - 1]
        rel = Relocs(code, recs)
        while len(code) & 1: code.append(0x90)
        shared = {}
        def tramp(key, body):
            if key not in shared:
                shared[key] = len(code); code.extend(body)
            return shared[key]
        def call_at(off, t):
            code[off:off + 3] = b'\xe8' + struct.pack('<h', t - (off + 3))
        for s in sorted(lst, key=lambda s: s['off']):
            off = s['off']
            ins = next(md.disasm(bytes(code[off:off + 16]), off, 1), None)   # as earlier passes left it
            if ins is None or kind(ins) is None:
                stats['i186_replaced'] += 1; continue        # an earlier pass already replaced it
            if kind(ins) != s['kind'] or ins.size != s['ins'].size:
                problems.append((sg, off, 'changed to %s' % bytes(ins.bytes).hex())); continue
            b = bytes(ins.bytes); n = len(b)
            inside = [p for p in range(off, off + n) if rel.find(p) is not None]
            k = s['kind']
            if k == 'push16' and n == 3:
                if inside and inside != [off + 1]:
                    problems.append((sg, off, 'relocation not on the immediate')); continue
                if inside:
                    body, io = t_push16(0); t = len(code); code.extend(body)
                    rel.move(code, off + 1, t + io); stats['i186_push16_reloc'] += 1
                else:
                    t = tramp(('p', u16(b, 1)), t_push16(u16(b, 1))[0])
                call_at(off, t); stats['i186_push16'] += 1
            elif inside:
                problems.append((sg, off, 'relocation inside a %s site' % k)); continue
            elif k == 'push8' and n == 2 and int3:
                code[off] = 0xcc; stats['i186_push8'] += 1
            elif k == 'shift' and n == 3 and b[1] >> 6 == 3 and not (b[0] == 0xc1 and b[1] & 7 == 4):
                call_at(off, tramp(('s', b), t_shift(b))); stats['i186_shift'] += 1
            elif k == 'enter' and n == 4 and b[3] == 0:
                t = len(code); code.extend(t_enter(b, off + 4, t))
                code[off:off + 4] = jmp(off, t) + b'\x90'; stats['i186_enter'] += 1
            elif k == 'leave' and n == 1:
                nx = bytes(code[off + 1:off + 4])
                if nx[0] == 0xca and off + 1 not in s['targets']:
                    t = len(code); code.extend(t_leave_retf(code[off:off + 4]))
                    code[off:off + 4] = jmp(off, t) + b'\x90'; stats['i186_leave'] += 1
                elif nx[0] in (0xcb, 0xc3) and s.get('prev') is not None:
                    # LEAVE + RET/RETF is 2 bytes: move the instruction before it along
                    st = s['prev']
                    if any(rel.find(p) is not None for p in range(st, off)):
                        problems.append((sg, off, 'relocation in the instruction before LEAVE')); continue
                    t = len(code)
                    code.extend(bytes(code[st:off]) + b'\x8b\xe5\x5d' + bytes([nx[0]]))
                    code[st:off + 2] = jmp(st, t) + b'\x90' * (off + 2 - st - 3); stats['i186_leave'] += 1
                else:
                    problems.append((sg, off, 'LEAVE not followed by RETF n')); continue
            elif k == 'imul' and n >= 3:
                t = len(code); code.extend(t_imul(b, off + n, t))
                code[off:off + n] = jmp(off, t) + b'\x90' * (n - 3); stats['i186_imul'] += 1
            else:
                problems.append((sg, off, 'unhandled %s %s' % (k, b.hex()))); continue
        blobs[sg - 1] = (code, rel.records(code))
    return problems


# near calls that do not return to the next byte: the error entries, and the p-code
# escape dispatchers that pop their return address and read operand bytes from it
VB_NORETURN = {2: {0x4a65, 0x4a6a, 0x4a6c, 0x48f9, 0x48fe, 0x4903, 0x4908, 0x490d, 0x4910, 0x4921, 0x4935, 0x4938}}

def check(orig, conv, noreturn=None):
    """80186 sites still reachable in the converted file (should be none)"""
    global INT3_IMM
    cur, _, _ = load(conv)
    # W stubs (call center / dd target / dw X): center never returns to the bytes after the call
    noreturn = {k: set(v) for k, v in (noreturn or {}).items()}
    for s in cur:
        for pat in (b'\x55\x55\x89\xe5\x9c\x50\x53\x51\x52\x56\x06', b'\x55\x55\x8b\xec\x9c\x50\x53\x51\x52\x56\x06'):
            i = s['code'].find(pat)
            if i >= 0: noreturn.setdefault(s['n'], set()).add(i)
    INT3_IMM = True
    try: sites, _ = census(orig, noreturn, cur)
    finally: INT3_IMM = False
    return sites


if __name__ == '__main__' and '--check' in sys.argv:
    o, c = [a for a in sys.argv[1:] if not a.startswith('--')]
    od = open(o, 'rb').read()
    left = check(od, open(c, 'rb').read(), VB_NORETURN if b'VBRUN100' in od[:0x2000] else None)
    for s in left: print('  left %d:%04x %s %s %s' % (s['seg'], s['off'], s['kind'], s['ins'].mnemonic, s['ins'].op_str))
    print('OK' if not left else 'LEFT %d' % len(left)); sys.exit(1 if left else 0)
elif __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    if '--converted' in sys.argv: INT3_IMM = True
    sites, segs = census(d, VB_NORETURN if b'VBRUN100' in d[:0x400] or 'VBRUN' in sys.argv[1].upper() else None)
    c = collections.Counter(s['kind'] for s in sites)
    print(len(sites), dict(c))
    for s in sites:
        if s['ft'] or s['kind'] == 'other186':
            print('  review %d:%04x %-8s %s %s%s' % (s['seg'], s['off'], s['kind'], s['ins'].mnemonic, s['ins'].op_str,
                  ' (only after a call)' if s['ft'] else ''))
