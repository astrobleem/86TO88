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
#
# The check fails closed.  EVERY "0E 5x / 0E 68 / 0E 6A" byte pair in a movable code segment
# is treated as a possible push site, whether or not any disassembly reaches it: code is
# entered through jump tables and computed jumps (2:4953 itself is), so "not reached" and
# "looks like the middle of another instruction" prove nothing.  From each pair every path
# is followed - both sides of conditional branches, direct jumps, and near calls INTO the
# callee as well as past it (a callee can drop its own return address and jump far with the
# hand-pushed one on top of the stack).  A site is an error when
#   - a path reaches a direct far jump to a movable target of this module, or
#   - the walk cannot be finished: instruction budget, undecodable bytes, an indirect near
#     jump or call, or running off the segment.
# The only way past an unfinished walk is a reviewed entry in the file given with
# --reviewed (JSON: module -> [{"seg","off","ctx","why"}]); "ctx" is the 8 bytes around the
# pair, so an entry stops applying if the code changes.  A far jump to a movable target, or
# running out of the instruction budget, is never waived.  Indirect FAR jumps can't be resolved statically and are reported as WARN.
# Assumed, not checked: far calls and INTs return to the next instruction; a near RET outside
# any followed callee consumes the pushed IP and ends the hand-pushed far return.
warn = []
BUDGET = 4096                   # instructions per push site, over all paths
reviewed = {}
if '--reviewed' in sys.argv:
    import json
    rv = json.load(open(sys.argv[sys.argv.index('--reviewed') + 1]))
    rnt = ne + struct.unpack_from('<H', d, ne + 0x26)[0]
    modname = d[rnt + 1:rnt + 1 + d[rnt]].decode('latin1').upper()
    for e in rv.get(modname, []):
        reviewed[(int(e['seg']), int(str(e['off']), 16))] = bytes.fromhex(e['ctx'])
used = set()
try:
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
except ImportError:
    md = None
for i, (o, l, f, m) in enumerate(segs):
    if not o or f & 1 or not f & 0x10: continue
    if md is None:
        err.append('pushed-return check not run (capstone missing)'); break
    ln = l or 0x10000; code = d[(o << al):(o << al) + ln]; rel = site.get(i, {})
    def follow(p):
        """Walk every path from the push pair at p.  Returns ([direct far jumps to a movable
        target], [indirect far jumps], first reason a path could not be finished or None,
        whether a reviewed entry may accept that).  A path that cannot be continued is
        dropped and the others are still walked, so an accepted site has had every reachable
        far jump checked; running out of budget leaves paths unwalked and is never accepted."""
        work = [(p + 2 if code[p + 1] != 0x68 else p + 4, 0)] if code[p + 1] != 0x6a else [(p + 3, 0)]
        done = set(); n_ins = 0; bad = []; ind = []; why = None
        while work:
            q, depth = work.pop()                   # depth: near calls entered since the push
            while (q, depth) not in done:
                if q >= ln: why = why or 'runs off the segment end'; break
                if n_ins >= BUDGET: return bad, ind, 'more than %d instructions to follow' % BUDGET, False
                done.add((q, depth)); n_ins += 1
                try: ins = next(md.disasm(code[q:q + 16], q, 1))
                except StopIteration: why = why or 'undecodable bytes at %x' % q; break
                b = ins.bytes; k = 0
                while k < len(b) - 1 and b[k] in (0x26, 0x2e, 0x36, 0x3e, 0xf0, 0xf2, 0xf3): k += 1    # prefixes
                op = b[k]; mn = ins.mnemonic
                if op == 0xea:
                    fx = rel.get(q + k + 1)
                    # imports (KERNEL/USER/GDI...) are compiled for real mode and mark their frames,
                    # so the kernel patches the pushed address like any far-call return
                    if fx is None or not fx[0] & 3 and (fx[1] == 0xff or not (1 <= fx[1] <= n) or segs[fx[1] - 1][2] & 0x10):
                        bad.append(q)
                    break
                if op == 0xff and len(b) > k + 1:
                    reg = (b[k + 1] >> 3) & 7
                    if reg == 5: ind.append(q); break
                    if reg == 4: why = why or 'indirect near jump at %x' % q; break
                    if reg == 2: why = why or 'indirect near call at %x' % q; break
                if mn in ('retf', 'iret', 'hlt'): break       # the far return is consumed here: path ends
                if mn == 'ret': break     # in a callee: back to a call site that is walked anyway; at
                                          # depth 0 it consumes the pushed IP, so no far return is left
                if op in (0xe9, 0xeb):
                    q = ins.operands[0].imm & 0xffff; continue                  # direct near/short jump
                if op == 0xe8:
                    work.append((ins.operands[0].imm & 0xffff, min(depth + 1, 8)))   # into the near callee
                elif mn.startswith(('j', 'loop')) and ins.operands and ins.operands[0].type == capstone.x86.X86_OP_IMM:
                    work.append((ins.operands[0].imm & 0xffff, depth))
                q += ins.size                       # far calls and ints are assumed to return here
        return bad, ind, why, True
    for p in range(ln - 2):
        if code[p] != 0x0e or not (0x50 <= code[p + 1] <= 0x57 or code[p + 1] in (0x68, 0x6a)): continue
        bad, ind, why, waivable = follow(p)
        for q in bad:
            err.append('seg %d pushes a return address at %x and jumps far at %x to a movable target' % (i + 1, p, q))
        for q in ind:
            warn.append('seg %d pushes a return address at %x and jumps far indirectly at %x' % (i + 1, p, q))
        if why:
            ctx = bytes(code[max(0, p - 3):p + 5])
            if waivable and reviewed.get((i + 1, p)) == ctx: used.add((i + 1, p))
            else: err.append('seg %d pushes a return address at %x; check incomplete: %s' % (i + 1, p, why))
for k in sorted(set(reviewed) - used):
    err.append('reviewed entry seg %d off %x matches no unfinished site (stale or wrong ctx)' % k)
if used: print('REVIEWED %d unfinished sites accepted from the reviewed list' % len(used))
if warn: print('WARN', sorted(set(warn)))
print('segments fixed %d movable %d; entries %d (movable %d); %s' % (len(fixed), len(movable), len(ents), nmov, stats))
print('ERRORS' if err else 'OK', err if '--all' in sys.argv else err[:20])
sys.exit(1 if err else 0)
