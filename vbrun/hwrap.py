"""Per-callee analysis for the marked-wrapper (H) rewrite of same-segment push cs/call near sites."""
import sys, json, struct, collections, capstone
from capstone import x86
from endanger import analyse, classify
from reach import explore
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
DANG = {'far', 'int3f', 'indirect', 'limit', 'baddecode'}

def entries(fn):
    d = open(fn, 'rb').read(); ne = struct.unpack_from('<I', d, 0x3c)[0]
    eto, = struct.unpack_from('<H', d, ne + 4); q = ne + eto; o = 1; out = {}
    while d[q]:
        c, t = d[q], d[q + 1]; q += 2
        for k in range(c):
            if t == 0: pass
            elif t == 0xff: out[o] = (d[q + 3], struct.unpack_from('<H', d, q + 4)[0]); q += 6
            else: out[o] = (t, struct.unpack_from('<H', d, q + 1)[0]); q += 3
            o += 1
    return out

def callee_info(code, off):
    ev, seen = explore(code, off)
    rets = set(); issues = []; framed = False
    cls = classify(code, off)
    for pc in sorted(seen):
        try: ins = next(md.disasm(bytes(code[pc:pc + 16]), pc, 1))
        except StopIteration: issues.append('baddecode @%x' % pc); continue
        m = ins.mnemonic
        if m == 'retf': rets.add(ins.operands[0].imm if ins.operands else 0)
        elif m == 'ret': issues.append('near ret @%x' % pc)
        elif m == 'iret': issues.append('iret @%x' % pc)
        if m in ('ljmp',) or (m == 'jmp' and 'far' in ins.op_str): issues.append('far jmp @%x' % pc)
        for o in ins.operands:
            if o.type == x86.X86_OP_REG and o.access & capstone.CS_AC_WRITE and ins.reg_name(o.reg) == 'ds':
                issues.append('writes ds @%x %s %s' % (pc, m, ins.op_str))
        if m == 'pop' and ins.op_str == 'ds': issues.append('pop ds @%x' % pc)
        for o in ins.operands:
            if o.type == x86.X86_OP_MEM:
                base = ins.reg_name(o.mem.base) if o.mem.base else ''
                if base == 'bp' and cls == 'frameless': issues.append('caller-bp ref @%x %s %s' % (pc, m, ins.op_str))
                if base == 'bp' and cls == 'unmarked' and o.mem.disp >= 6 + max(rets | {0}) and o.mem.disp > 0:
                    issues.append('bp+%d beyond args @%x' % (o.mem.disp, pc))
                if base == 'bp' and cls == 'unmarked' and o.mem.disp == 4: issues.append('reads ret CS @%x' % pc)
        if m == 'mov' and ins.op_str.endswith(', sp'):
            issues.append('sp copy @%x %s %s' % (pc, m, ins.op_str))
    return dict(cls=cls, ev=sorted(ev), rets=sorted(rets), issues=issues)

if __name__ == '__main__':
    fn = sys.argv[1]
    segs, calls, ptrs = analyse(fn)
    res = {}
    for c in calls:
        k = (c[2], c[3])
        if k in res: continue
        code = segs[k[0] - 1]['code']
        cl = classify(code, k[1])
        if cl == 'marked': continue
        ev, _ = explore(code, k[1])
        if not ev & DANG: continue
        res[k] = callee_info(code, k[1])
    bad = {k: v for k, v in res.items() if len(v['rets']) != 1 or v['issues']}
    print('dangerous callees', len(res), 'clean', len(res) - len(bad))
    for k, v in sorted(bad.items()):
        print(k, v['cls'], 'rets', v['rets'], v['issues'][:6])
    # exported entries: classify targets
    ent = entries(fn); ec = collections.Counter(); edang = []
    for o, (s, off) in ent.items():
        if segs[s - 1]['flags'] & 1: continue
        cl = classify(segs[s - 1]['code'], off); ec[cl] += 1
        if cl != 'marked':
            ev, _ = explore(segs[s - 1]['code'], off)
            if ev & DANG: edang.append((o, s, off, cl, sorted(ev)))
    print('entry targets', dict(ec), 'dangerous non-marked exports', len(edang))
    for e in edang[:40]: print('  ', e)
    json.dump({'%d:%d' % k: v for k, v in res.items()}, open(sys.argv[2], 'w'))
