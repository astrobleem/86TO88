#!/usr/bin/env python3
"""Accurate 80186+ site census for 16-bit NE modules (EXE/DLL/VBX).

Linear sweep is not safe for patching: data inside code segments decodes as
instructions.  This does a recursive-descent pass from real code roots:
  * the entry point (CS:IP) and every exported entry-table entry
  * every internal relocation target (far pointers to procs, window procs...)
  * jump-table targets (JMP word ptr cs:[bx+TABLE] -> read TABLE words)
and records, per segment, which bytes are reached code.  Sites are reported only
inside reached code; unreached-but-linear-sweep-hits are listed separately so a
human can judge them (data vs. missed code).

usage: analyze_ne.py FILE [--json out.json]
"""
import sys, struct, json, collections
import capstone
from capstone import x86_const as X

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
md.detail = True

u16 = lambda b, o: struct.unpack_from('<H', b, o)[0]
u32 = lambda b, o: struct.unpack_from('<I', b, o)[0]

REG16 = {'ax': 0, 'cx': 1, 'dx': 2, 'bx': 3, 'sp': 4, 'bp': 5, 'si': 6, 'di': 7}
TYPES = {'push': 0, 'shl': 1, 'shr': 2, 'sar': 3, 'imul': 4}


class NE:
    def __init__(self, data):
        self.b = data
        h = u32(data, 0x3c)
        assert data[h:h + 2] == b'NE', 'not NE'
        self.h = h
        self.align = u16(data, h + 0x32)
        self.nseg = u16(data, h + 0x1c)
        self.csip = (u16(data, h + 0x16), u16(data, h + 0x14))
        segtab = h + u16(data, h + 0x22)
        self.segs = []  # dict per segment, 1-based index = list idx+1
        for i in range(self.nseg):
            off, ln, fl, al = struct.unpack_from('<HHHH', data, segtab + 8 * i)
            fo = off << self.align if off else 0
            ln = ln or (0x10000 if off else 0)
            seg = dict(n=i + 1, fo=fo, ln=ln, fl=fl, code=not (fl & 1), relocs=[])
            if fl & 0x100 and off:
                p = fo + (ln if ln != 0x10000 else 0x10000)
                p = fo + ln
                cnt = u16(data, p)
                for r in range(cnt):
                    at, rf, ro, mi, val = struct.unpack_from('<BBHHH', data, p + 2 + 8 * r)
                    seg['relocs'].append((at, rf, ro, mi, val))
                seg['reloc_end'] = p + 2 + 8 * cnt
            self.segs.append(seg)
        # entry table -> ordinal -> (segment, offset)
        self.ent = {}
        o = h + u16(data, h + 4)
        end = o + u16(data, h + 6)
        ordn = 1
        while o < end and data[o]:
            cnt, sg = data[o], data[o + 1]
            o += 2
            if sg == 0:
                ordn += cnt
                continue
            for _ in range(cnt):
                if sg == 0xff:
                    self.ent[ordn] = (data[o + 3], u16(data, o + 4))
                    o += 6
                else:
                    self.ent[ordn] = (sg, u16(data, o + 1))
                    o += 3
                ordn += 1
        self.entries = list(self.ent.values())

    def segdata(self, n):
        s = self.segs[n - 1]
        return self.b[s['fo']:s['fo'] + s['ln']]


def classify(ins):
    """Return (type, reg, srcreg, imm) if ins is an 80186 form the bridge emulates.
    Return ('unsup-...', None, None, rawhex) for any other form that an 8088 cannot execute (80186-only forms the
    bridge does not handle, plus 80286/386 forms: 0F xx, ARPL, FS/GS and 66/67 size prefixes).  None = plain 8088 code."""
    raw = bytes(ins.bytes)
    m = ins.mnemonic
    # strip prefixes for opcode lookup; 64-67 are 386 prefixes and never valid on an 8088 (they alias INC/DEC/POPs... or are undefined)
    i = 0
    pre = set()
    while i < len(raw) and raw[i] in (0x26, 0x2e, 0x36, 0x3e, 0xf0, 0xf2, 0xf3, 0x64, 0x65, 0x66, 0x67):
        pre.add(raw[i])
        i += 1
    if pre & {0x64, 0x65, 0x66, 0x67}:
        return ('unsup-386-prefix', None, None, raw.hex())
    if i >= len(raw):
        return ('unsup-prefix-only', None, None, raw.hex())
    op = raw[i]
    if op == 0x0f:
        return ('unsup-0f', None, None, raw.hex())
    if op == 0x63:
        return ('unsup-arpl', None, None, raw.hex())
    if op in (0x68, 0x6a):
        return ('push', 0, 0, ins.operands[0].imm & 0xFFFF)
    if op in (0xc0, 0xc1):
        modrm = raw[i + 1]
        if (modrm >> 6) != 3:
            return ('unsup-mem-shift', None, None, raw.hex())
        r = modrm >> 3 & 7
        nm = {4: 'shl', 5: 'shr', 7: 'sar', 6: 'shl'}.get(r)
        if nm is None:
            return ('unsup-shift', None, None, raw.hex())
        if op == 0xc1 and (modrm & 7) == 4:      # SP: the handler has no slot for it
            return ('unsup-sp-reg', None, None, raw.hex())
        return (nm, (modrm & 7) | (8 if op == 0xc0 else 0), 0, raw[i + 2] & 31)   # reg bit 3 = byte register form (C0)
    if op in (0x69, 0x6b):
        modrm = raw[i + 1]
        if (modrm >> 6) != 3:
            if (modrm >> 3 & 7) == 4:
                return ('unsup-sp-reg', None, None, raw.hex())
            return ('unsup-mem-imul', None, None, raw.hex())
        if (modrm >> 3 & 7) == 4 or (modrm & 7) == 4:
            return ('unsup-sp-reg', None, None, raw.hex())
        imm = raw[i + 2] | (raw[i + 3] << 8) if op == 0x69 else (raw[i + 2] - 256 if raw[i + 2] > 127 else raw[i + 2]) & 0xFFFF
        return ('imul', modrm >> 3 & 7, modrm & 7, imm)
    if op in (0x60, 0x61, 0x62, 0xc8, 0xc9, 0x6c, 0x6d, 0x6e, 0x6f):
        return ('unsup-' + ins.mnemonic, None, None, raw.hex())
    return None


def descend(seg_bytes, roots, seglen):
    """Recursive descent.  Returns (reached: dict off->ins, bad: list of (off, why))."""
    reached = {}
    bad = []
    todo = list(roots)
    tab_todo = []            # jump-table targets: lower confidence, decoded after all direct flow, never allowed to overlap it
    seen_roots = set()
    jt_done = set()
    cov = {}
    low = False
    while todo or tab_todo:
        if not todo:
            todo = tab_todo; tab_todo = []; low = True
        off = todo.pop()
        if off in seen_roots:
            continue
        seen_roots.add(off)
        while 0 <= off < seglen:
            if off in reached:
                break
            if low and off in cov:        # lands inside an instruction already decoded from direct flow
                break
            ins = next(md.disasm(seg_bytes[off:off + 16], off, 1), None)
            if ins is None:
                bad.append((off, 'undecodable'))
                break
            if low and any((off + k) in cov for k in range(ins.size)):
                break
            reached[off] = ins
            for k in range(ins.size): cov[off + k] = off
            nxt = off + ins.size
            m = ins.mnemonic
            grp = set(ins.groups)
            raw = bytes(ins.bytes)
            if m in ('ret', 'retf', 'iret', 'hlt') or raw[0] in (0xc2, 0xc3, 0xca, 0xcb, 0xcf):
                break
            if m == 'jmp':
                opn = ins.operands[0]
                if opn.type == X.X86_OP_IMM:
                    todo.append(opn.imm & 0xFFFF)
                elif opn.type == X.X86_OP_MEM:
                    # jump table: jmp word ptr cs:[bx+TABLE]
                    mem = opn.mem
                    if ins.reg_name(mem.segment) == 'cs' and mem.disp and (mem.base or mem.index):
                        tab = mem.disp & 0xFFFF
                        if tab not in jt_done:
                            jt_done.add(tab)
                            p = tab
                            while p + 2 <= seglen:
                                t = u16(seg_bytes, p)
                                if t >= seglen or t == 0:
                                    break
                                # must decode at t
                                if next(md.disasm(seg_bytes[t:t + 16], t, 1), None) is None:
                                    break
                                tab_todo.append(t)
                                p += 2
                                if (p - tab) // 2 > 512:
                                    break
                break
            if raw[0] in (0xe9, 0xeb) or (0x70 <= raw[0] <= 0x7f) or raw[0] in (0xe0, 0xe1, 0xe2, 0xe3) or \
                    (raw[0] == 0x0f and 0x80 <= raw[1] <= 0x8f):
                opn = ins.operands[0]
                if opn.type == X.X86_OP_IMM:
                    todo.append(opn.imm & 0xFFFF)
                if raw[0] in (0xe9, 0xeb):
                    break
            elif raw[0] == 0xe8:
                opn = ins.operands[0]
                if opn.type == X.X86_OP_IMM:
                    todo.append(opn.imm & 0xFFFF)
            off = nxt
    return reached, bad


def analyze(data):
    ne = NE(data)
    roots = collections.defaultdict(set)
    cs, ip = ne.csip
    if cs:
        roots[cs].add(ip)
    for sg, off in ne.entries:
        roots[sg].add(off)
    # internal relocation targets (additive flag 4 ignored: target stored in val)
    for s in ne.segs:
        for at, rf, ro, mi, val in s['relocs']:
            if (rf & 3) == 0 and 1 <= mi <= ne.nseg:
                # internal ref: mi = segment (or 0xff for movable entry), val = offset
                if mi == 0xff:
                    if val in ne.ent:
                        sg2, off2 = ne.ent[val]
                        roots[sg2].add(off2)
                    continue
                roots[mi].add(val)
            # also chains: location offsets carry the next-link; targets are above
    result = {'segments': []}
    for s in ne.segs:
        if not s['code'] or not s['ln']:
            continue
        sb = ne.segdata(s['n'])
        reached, bad = descend(sb, sorted(roots[s['n']]), len(sb))
        sites = []
        unsup = []
        for off, ins in sorted(reached.items()):
            c = classify(ins)
            if not c:
                continue
            if c[0].startswith('unsup'):
                unsup.append(dict(off=off, kind=c[0], raw=c[3]))
                continue
            sites.append(dict(off=off, type=TYPES[c[0]], name=c[0], reg=c[1], srcreg=c[2], imm=c[3],
                              len=ins.size, orig=bytes(ins.bytes).hex()))
        # unreached linear sweep hits (diagnostic)
        covered = bytearray(len(sb))
        for off, ins in reached.items():
            for k in range(ins.size):
                covered[off + k] = 1
        unreached_hits = []
        p = 0
        while p < len(sb):
            if covered[p]:
                p += 1
                continue
            ins = next(md.disasm(sb[p:p + 16], p, 1), None)
            if ins is None:
                p += 1
                continue
            c = classify(ins)
            if c:
                unreached_hits.append(dict(off=p, raw=bytes(ins.bytes).hex(), kind=c[0]))
            p += ins.size
        # relocation overlap: reloc locations that fall inside a site
        rel = [(ro, 2 if at in (2, 5) else 4 if at == 3 else 1, at, rf) for at, rf, ro, mi, val in s['relocs']]
        ovl = []
        for st in sites:
            for ro, w, at, rf in rel:
                if ro < st['off'] + st['len'] and st['off'] < ro + w:
                    ovl.append(dict(site=st['off'], reloc=ro, at=at, rf=rf))
        result['segments'].append(dict(seg=s['n'], length=len(sb), reached_bytes=int(sum(covered)),
                                       roots=len(roots[s['n']]), sites=sites, unsup=unsup, bad=bad[:20],
                                       unreached_hits=unreached_hits, reloc_overlap=ovl))
    return result


if __name__ == '__main__':
    path = sys.argv[1]
    data = open(path, 'rb').read()
    r = analyze(data)
    tot = 0
    for sg in r['segments']:
        n = len(sg['sites'])
        tot += n
        print('seg%d len=%d reached=%d roots=%d sites=%d unsup=%d bad=%d unreached_hits=%d reloc_overlap=%d' % (
            sg['seg'], sg['length'], sg['reached_bytes'], sg['roots'], n, len(sg['unsup']), len(sg['bad']),
            len(sg['unreached_hits']), len(sg['reloc_overlap'])))
    print('TOTAL sites', tot)
    if '--json' in sys.argv:
        json.dump(r, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
