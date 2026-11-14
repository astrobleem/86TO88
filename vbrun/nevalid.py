"""Validate an NE file: segment table, relocation chains, record targets, entry table."""
import re, struct, sys
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
                site.setdefault(i, {})[p] = (fl, a, b, t & 15)
                seen.add(p); p = struct.unpack_from('<H', code, p)[0]; c += 1
        else:
            site.setdefault(i, {})[off] = (fl, a, b, t & 15)
# Hand-pushed far return addresses in a MOVABLE code segment of this module, e.g.
# "push cs / push ret / ... jmp far".  The callee (VB code built for protected mode) doesn't
# mark its frame, so the kernel never patches that return address; if the segment moves
# during the call the RETF lands in the old copy (seen: VBRUN 2:4953).  Such a jump must go
# through a wrapper stub (an internal reference into a FIXED segment).
#
# Two checks.
#
# 1. Jump gate - no flow analysis, so nothing can hide from it.  The far return a direct far
#    JMP leaves for its target is whatever is on the stack, and no walk from a "push cs" can
#    be trusted to find every way there: the push need not be next to the IP push, a near
#    callee can drop its own return, a near RET is an indirect jump that can land on code
#    that re-pushes an IP above the saved CS.  So EVERY direct far JMP (EA with its fixup)
#    in a movable code segment whose target is a movable segment of this module is an error
#    unless it is on the list given with --reviewed:
#        {MODULE: {"farjmp": [{"seg", "off", "to": "seg:off", "ctx", "why"}]}}
#    An entry applies only while the target and the 8 bytes around the opcode match; an
#    entry that matches nothing is an error.  The list says, per jump, why the far return on
#    the stack there is not one this segment pushed by hand (a tail jump out of a far
#    function, a jump to the error raiser that never returns, ...).
#
# 2. Push walk - finds definite violations, which the list can never excuse.  Every
#    "0E 5x / 0E 68 / 0E 6A" byte pair is taken as a possible push of CS:IP and every path
#    from it is followed (conditional branches, near calls into the callee and past it, near
#    returns to a call the walk made).  A path that reaches a direct far jump to a movable
#    target is an error even if that jump is on the reviewed list.  Paths the walk cannot
#    follow (indirect near jump or call, near RET to an unknown address, undecodable bytes)
#    are counted and listed with --all; they are not errors, because whatever far jump they
#    might reach is covered by the gate.  Running out of the instruction budget is an error.
#
# Not covered: INDIRECT far jumps (FF /5).  Their target cannot be read from the file; they
# are reported as WARN when a walk reaches one.  Far calls and INTs are assumed to return to
# the next instruction.
warn = []; unfinished = []
BUDGET = 4096                   # instructions per push pair, over all paths
reviewed = {}; provisional = set()
if '--reviewed' in sys.argv:
    import json
    rv = json.load(open(sys.argv[sys.argv.index('--reviewed') + 1]))
    rnt = ne + struct.unpack_from('<H', d, ne + 0x26)[0]
    modname = d[rnt + 1:rnt + 1 + d[rnt]].decode('latin1').upper()
    for e in rv.get(modname, {}).get('farjmp', []):
        ts, to_ = e['to'].split(':')
        reviewed[(int(e['seg']), int(str(e['off']), 16))] = (bytes.fromhex(e['ctx']), int(ts), int(to_, 16))
        if e.get('provisional'): provisional.add((int(e['seg']), int(str(e['off']), 16)))
used = set()
try:
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
except ImportError:
    md = None
def far_target(fx):
    """(segment, offset) of an internal far fixup, or None for an import"""
    if fx[0] & 3: return None
    if fx[1] == 0xff: return ents.get(fx[2], (0, 0))
    return (fx[1], fx[2])
for i, (o, l, f, m) in enumerate(segs):
    if not o or f & 1 or not f & 0x10: continue
    ln = l or 0x10000; code = d[(o << al):(o << al) + ln]; rel = site.get(i, {})
    # 1. jump gate
    for off in sorted(rel):
        fx = rel[off]
        if fx[3] != 3 or off < 1 or code[off - 1] != 0xea: continue
        tg = far_target(fx)
        if tg is None: continue                         # import: real-mode code that marks its frames
        if 1 <= tg[0] <= n and not segs[tg[0] - 1][2] & 0x10: continue      # FIXED target (wrapper stub)
        p = off - 1; ctx = bytes(code[max(0, p - 3):p + 5])
        if reviewed.get((i + 1, p)) == (ctx, tg[0], tg[1]): used.add((i + 1, p))
        else: err.append('seg %d: far jump at %x to movable %d:%x is not on the reviewed list' % (i + 1, p, tg[0], tg[1]))
    if md is None:
        err.append('push walk not run (capstone missing)'); continue
    T16 = re.compile(rb'\x50\x55\x8b\xec\x8b\x46\x04\xc7\x46\x04..\x87\x46\x02\x5d\xc3', re.S)
    def pseudo(q):
        """length of a PUSH imm that i186.py rewrote at q (CALL to a push trampoline, or
        INT 3 + imm8), else 0"""
        if code[q] == 0xcc: return 2
        if code[q] == 0xe8 and q + 3 <= ln:
            t = (q + 3 + struct.unpack_from('<h', code, q + 1)[0]) & 0xffff
            if T16.match(code, t): return 3
        return 0
    def follow(p):
        """Walk every path from the push pair at p.  Returns ([direct far jumps to a movable
        target], [indirect far jumps], first reason a path could not be followed or None,
        False if the instruction budget ran out).  A path that cannot be continued is dropped
        and the others are still walked.

        A near RET is an indirect jump.  Each path carries a model of the words pushed above
        the hand-pushed pair: a return address of a near call the walk made itself, or DATA.
        RET continues at the address only when the top word is such a return address.  When
        it is DATA, when nothing is above the pair (the RET takes the hand-pushed IP and CS
        stays on the stack, where a later push + far jump rebuilds a far return), or when the
        model was lost (SP changed some other way, a far call or INT that may pop arguments,
        too many words), the destination is unknown and the path is unfinished."""
        D = -1
        work = [(p + 1 + (pseudo(p + 1) or {0x68: 3, 0x6a: 2}.get(code[p + 1], 1)), ())]
        done = set(); n_ins = 0; bad = []; ind = []; why = None
        def push(st, v=D, cnt=1):
            if st is None: return None
            st = st + (v,) * cnt
            return st if len(st) <= 24 else None
        def pop(st, cnt=1):
            if st is None or len(st) < cnt: return None
            return st[:len(st) - cnt]
        while work:
            q, st = work.pop()
            while (q, st) not in done:
                if q >= ln: why = why or 'runs off the segment end'; break
                if n_ins >= BUDGET: return bad, ind, 'more than %d instructions to follow' % BUDGET, False
                done.add((q, st)); n_ins += 1
                ps = pseudo(q)
                if ps: st = push(st); q += ps; continue
                try: ins = next(md.disasm(code[q:q + 16], q, 1))
                except StopIteration: why = why or 'undecodable bytes at %x' % q; break
                b = ins.bytes; k = 0
                while k < len(b) - 1 and b[k] in (0x26, 0x2e, 0x36, 0x3e, 0xf0, 0xf2, 0xf3): k += 1    # prefixes
                op = b[k]; mn = ins.mnemonic; reg = (b[k + 1] >> 3) & 7 if len(b) > k + 1 else 0
                if op == 0xea:
                    fx = rel.get(q + k + 1)
                    # imports (KERNEL/USER/GDI...) are compiled for real mode and mark their frames,
                    # so the kernel patches the pushed address like any far-call return
                    if fx is None or not fx[0] & 3 and (fx[1] == 0xff or not (1 <= fx[1] <= n) or segs[fx[1] - 1][2] & 0x10):
                        bad.append(q)
                    break
                if op == 0xff:
                    if reg == 5: ind.append(q); break
                    if reg == 4: why = why or 'indirect near jump at %x' % q; break
                    if reg == 2: why = why or 'indirect near call at %x' % q; break
                if mn in ('retf', 'iret', 'hlt'): break       # the far return is consumed here: path ends
                if op in (0xc3, 0xc2):
                    if st is None: why = why or 'near return at %x, stack contents unknown' % q; break
                    if not st: why = why or 'near return at %x takes the pushed IP' % q; break
                    if st[-1] == D: why = why or 'near return at %x to a pushed data word' % q; break
                    tgt = st[-1]; st = pop(st)
                    if op == 0xc2: st = pop(st, struct.unpack_from('<H', b, k + 1)[0] // 2)
                    q = tgt; continue
                if op in (0xe9, 0xeb):
                    q = ins.operands[0].imm & 0xffff; continue                  # direct near/short jump
                nq = q + ins.size
                if op == 0xe8:                      # near call: into the callee, and past it
                    work.append((ins.operands[0].imm & 0xffff, push(st, nq)))
                elif mn.startswith(('j', 'loop')) and ins.operands and ins.operands[0].type == capstone.x86.X86_OP_IMM:
                    work.append((ins.operands[0].imm & 0xffff, st))
                # stack model
                elif 0x50 <= op <= 0x57 or op in (0x06, 0x0e, 0x16, 0x1e, 0x68, 0x6a, 0x9c) or (op == 0xff and reg == 6): st = push(st)
                elif 0x58 <= op <= 0x5f or op in (0x07, 0x17, 0x1f, 0x9d) or (op == 0x8f and reg == 0): st = pop(st)
                elif op == 0x60: st = push(st, D, 8)
                elif op == 0x61: st = pop(st, 8)
                elif op in (0x83, 0x81) and len(b) > k + 2 and b[k + 1] in (0xec, 0xc4):      # sub/add sp,imm
                    v = b[k + 2] if op == 0x83 else struct.unpack_from('<H', b, k + 2)[0]
                    if op == 0x83 and v & 0x80: st = None
                    elif v & 1: st = None
                    else: st = push(st, D, v // 2) if b[k + 1] == 0xec else pop(st, v // 2)
                elif op in (0x9a, 0xcd, 0xcc, 0xce, 0xc8, 0xc9) or (op == 0xff and reg == 3): st = None   # far call/int may pop arguments; enter/leave
                else:
                    try: wr = ins.regs_access()[1]
                    except Exception: wr = [capstone.x86.X86_REG_SP]
                    if capstone.x86.X86_REG_SP in wr or capstone.x86.X86_REG_ESP in wr: st = None
                q = nq
        return bad, ind, why, True
    for p in range(ln - 2):
        if code[p] != 0x0e or not (0x50 <= code[p + 1] <= 0x57 or code[p + 1] in (0x68, 0x6a) or pseudo(p + 1)): continue
        bad, ind, why, in_budget = follow(p)
        for q in bad:
            err.append('seg %d pushes a return address at %x and jumps far at %x to a movable target' % (i + 1, p, q))
        for q in ind:
            warn.append('seg %d pushes a return address at %x and jumps far indirectly at %x' % (i + 1, p, q))
        if why and not in_budget:
            err.append('seg %d pushes a return address at %x; check incomplete: %s' % (i + 1, p, why))
        elif why: unfinished.append('seg %d pair at %x: %s' % (i + 1, p, why))
for k in sorted(set(reviewed) - used):
    err.append('reviewed entry seg %d off %x matches no far jump to a movable target (stale, wrong target or ctx)' % k)
if used: print('REVIEWED %d far jumps to movable targets accepted from the reviewed list (%d provisional)' % (len(used), len(used & provisional)))
if unfinished:
    print('UNFINISHED %d push walks stopped at an unknown transfer (far jumps are gated separately)' % len(unfinished))
    if '--all' in sys.argv: [print('  ', u) for u in unfinished]
if warn: print('WARN', sorted(set(warn)))
print('segments fixed %d movable %d; entries %d (movable %d); %s' % (len(fixed), len(movable), len(ents), nmov, stats))
print('ERRORS' if err else 'OK', err if '--all' in sys.argv else err[:20])
sys.exit(1 if err else 0)
