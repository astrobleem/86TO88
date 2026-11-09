"""Validate an NE file: segment table, relocation chains, record targets, entry table."""
import struct, sys
d = open(sys.argv[1], 'rb').read()
ne = struct.unpack_from('<I', d, 0x3c)[0]
sto, = struct.unpack_from('<H', d, ne + 0x22); al, = struct.unpack_from('<H', d, ne + 0x32)
n, = struct.unpack_from('<H', d, ne + 0x1c); nmod, = struct.unpack_from('<H', d, ne + 0x1e)
segs = [struct.unpack_from('<HHHH', d, ne + sto + 8 * i) for i in range(n)]
err = []; fixed = []; movable = []
for i, (o, l, f, m) in enumerate(segs):
    (movable if f & 0x10 else fixed).append(i + 1)
    if o and (o << al) + (l or 0x10000) > len(d): err.append('seg %d beyond EOF' % (i + 1))
# entry table
eto, etl = struct.unpack_from('<HH', d, ne + 4); q = ne + eto; o = 1; ents = {}; nmov = 0
while d[q]:
    c, t = d[q], d[q + 1]; q += 2
    for k in range(c):
        if t == 0: pass
        elif t == 0xff:
            fl, i3f, sg, off = d[q], struct.unpack_from('<H', d, q + 1)[0], d[q + 3], struct.unpack_from('<H', d, q + 4)[0]
            if i3f != 0x3fcd: err.append('ord %d bad int3f' % o)
            if not 1 <= sg <= n: err.append('ord %d bad seg' % o)
            elif not segs[sg - 1][2] & 0x10: err.append('ord %d movable entry for FIXED seg %d' % (o, sg))
            elif off >= (segs[sg - 1][1] or 0x10000): err.append('ord %d offset %x beyond seg %d len' % (o, off, sg))
            ents[o] = (sg, off); nmov += 1; q += 6
        else:
            if segs[t - 1][2] & 0x10 and segs[t - 1][2] & 0x1000:
                pass  # fixed-type entry into a movable segment (original export); noted below
            ents[o] = (t, struct.unpack_from('<H', d, q + 1)[0]); q += 3
        o += 1
# fast-load (gang-load) area: the real-mode loader copies every segment it loads with the
# module (PRELOAD or FIXED) out of the fast-load buffer, without a bounds check, when the
# area is present.  A load-time segment outside it gets whatever memory follows the buffer.
gs, gl = struct.unpack_from('<HH', d, ne + 0x38)
if d[ne + 0x37] & 0x08 and gl:
    lo, hi = gs << al, (gs + gl) << al
    for i, (o, l, f, m) in enumerate(segs):
        if o and (f & 0x40 or not f & 0x10) and not (lo <= (o << al) and (o << al) + (l or 0x10000) <= hi):   # length 0 = 64 KiB
            err.append('seg %d loaded with the module but outside the fast-load area' % (i + 1))
if q - (ne + eto) + 1 != etl: err.append('entry table length field %d vs parsed %d' % (etl, q - (ne + eto) + 1))
if struct.unpack_from('<H', d, ne + 0x30)[0] != nmov: err.append('movable count field %d vs %d' % (struct.unpack_from('<H', d, ne + 0x30)[0], nmov))
# relocations
stats = {'recs': 0, 'ord_refs': 0, 'int_fixed': 0, 'int_movable': 0, 'imports': 0}
site = {}   # seg index -> {fixup offset: (flags, target seg/module, offset/ordinal)}
for i, (o, l, f, m) in enumerate(segs):
    if not (o and f & 0x100): continue
    ln = l or 0x10000; base = o << al; cnt, = struct.unpack_from('<H', d, base + ln)
    code = d[base:base + ln]; seen = set()
    for k in range(cnt):
        t, fl, off, a, b = struct.unpack_from('<BBHHH', d, base + ln + 2 + 8 * k); stats['recs'] += 1
        kind = fl & 3
        if kind == 0:
            if a == 0xff:
                stats['ord_refs'] += 1
                if b not in ents: err.append('seg %d rec %d ordinal %d missing' % (i + 1, k, b))
            else:
                if not 1 <= a <= n: err.append('seg %d rec %d bad target seg %d' % (i + 1, k, a)); continue
                stats['int_movable' if segs[a - 1][2] & 0x10 else 'int_fixed'] += 1
        elif kind in (1, 2):
            stats['imports'] += 1
            if not 1 <= a <= nmod: err.append('seg %d rec %d bad module %d' % (i + 1, k, a))
        if not fl & 4 and (t & 15) in (2, 3, 5, 11, 13):
            p = off; c = 0
            while p != 0xffff:
                if p >= ln - 1 or p in seen or c > 5000: err.append('seg %d rec %d chain bad at %x' % (i + 1, k, p)); break
                site.setdefault(i, {})[p] = (fl, a, b)
                seen.add(p); p = struct.unpack_from('<H', code, p)[0]; c += 1
        else:
            site.setdefault(i, {})[off] = (fl, a, b)
# hand-pushed far return addresses: "push cs / push ret / ... jmp far" in a MOVABLE code
# segment of this module.  Its callees (VB code built for protected mode) don't mark their
# frames, so the kernel never patches that return address; the jump must go through a
# wrapper stub (internal reference into a FIXED segment).  A jump to a movable target of
# this module leaves a stale CS if the segment moves during the call (seen: VBRUN 2:4953).
# Indirect jumps can't be checked statically and are only reported as WARN.
warn = []
try:
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
except ImportError:
    md = None
for i, (o, l, f, m) in enumerate(segs):
    if md is None or not o or f & 1 or not f & 0x10: continue
    ln = l or 0x10000; code = d[(o << al):(o << al) + ln]; rel = site.get(i, {})
    for p in range(ln - 2):
        if code[p] != 0x0e or not (0x50 <= code[p + 1] <= 0x57 or code[p + 1] in (0x68, 0x6a)): continue
        work = [p + 1]; done = set(); n_ins = 0
        while work and n_ins < 64:
            q = work.pop()
            while q not in done and q < ln and n_ins < 64:
                done.add(q); n_ins += 1
                try: ins = next(md.disasm(code[q:q + 16], q, 1))
                except StopIteration: break
                op = ins.bytes[0]
                if op == 0xea:
                    fx = rel.get(q + 1)
                    # imports (KERNEL/USER/GDI...) are compiled for real mode and mark their frames,
                    # so the kernel patches the pushed address like any far-call return
                    if fx is None or not fx[0] & 3 and (fx[1] == 0xff or not (1 <= fx[1] <= n) or segs[fx[1] - 1][2] & 0x10):
                        err.append('seg %d pushes a return address at %x and jumps far at %x to a movable target' % (i + 1, p, q))
                    break
                if op in (0x2e, 0x26, 0x36, 0x3e) and len(ins.bytes) > 1 and ins.bytes[1] == 0xff and (ins.bytes[2] >> 3) & 7 == 5 or \
                   op == 0xff and (ins.bytes[1] >> 3) & 7 == 5:
                    warn.append('seg %d pushes a return address at %x and jumps far indirectly at %x' % (i + 1, p, q)); break
                if ins.mnemonic in ('ret', 'retf', 'iret', 'call', 'lcall', 'ljmp', 'int', 'hlt') or op == 0xff: break
                if ins.mnemonic == 'jmp':
                    if ins.operands[0].type == capstone.x86.X86_OP_IMM: q = ins.operands[0].imm & 0xffff; continue
                    break
                if ins.mnemonic.startswith('j') and ins.operands and ins.operands[0].type == capstone.x86.X86_OP_IMM:
                    work.append(ins.operands[0].imm & 0xffff)
                q += ins.size
if warn: print('WARN', warn[:10])
print('segments fixed %d movable %d; entries %d (movable %d); %s' % (len(fixed), len(movable), len(ents), nmov, stats))
print('ERRORS' if err else 'OK', err[:20])
