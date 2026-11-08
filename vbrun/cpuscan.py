"""CPU-target audit of an NE DLL: recursive-descent decode from every entry point and
far-call target, then classify each reachable instruction as 8086, 186 (incl. V20)
or 286+/x87-287. Usage: cpuscan.py DLL [segment ranges to report separately: N:start ...]"""
import sys, collections, capstone
from capstone import x86
from endanger import load, analyse
from hwrap import entries

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
I186 = {'pusha', 'popa', 'bound', 'enter', 'leave', 'insb', 'insw', 'outsb', 'outsw'}
I286 = {'lar', 'lsl', 'verr', 'verw', 'arpl', 'sldt', 'str', 'lldt', 'ltr', 'sgdt', 'sidt',
        'lgdt', 'lidt', 'smsw', 'lmsw', 'clts', 'loadall'}

def classify(ins):
    b = ins.bytes; m = ins.mnemonic
    p = 0
    while p < len(b) and b[p] in (0x26, 0x2e, 0x36, 0x3e, 0xf0, 0xf2, 0xf3, 0x9b): p += 1
    op = b[p] if p < len(b) else 0
    if op == 0x0f: return '286+' if m in I286 else '386+'
    if op in (0x64, 0x65, 0x66, 0x67): return '386+'
    if m in I186: return '186'
    if op in (0x68, 0x6a, 0x69, 0x6b): return '186'          # push imm, imul imm
    if op in (0xc0, 0xc1): return '186'                       # shift/rotate by imm8
    if op == 0xdf and len(b) > p + 1 and b[p + 1] == 0xe0: return '287'   # fnstsw ax
    if op in (0xdb,) and len(b) > p + 1 and b[p + 1] == 0xe4: return '287'  # fsetpm
    return '8086'

def scan(fn, segs_only=None):
    segs = load(fn); _, calls, ptrs = analyse(fn); ent = entries(fn)
    starts = collections.defaultdict(set)
    for o, (s, off) in ent.items(): starts[s].add(off)
    for c in calls: starts[c[2]].add(c[3])
    for p in ptrs: starts[p[2]].add(p[3])
    res = collections.Counter(); where = collections.defaultdict(list)
    for s, offs in starts.items():
        if segs_only and s not in segs_only: continue
        code = segs[s - 1]['code']
        if not code or segs[s - 1]['flags'] & 1 or s == len(segs): continue
        seen = set(); work = list(offs)
        while work:
            pc = work.pop()
            while pc not in seen and 0 <= pc < len(code):
                seen.add(pc)
                try: ins = next(md.disasm(bytes(code[pc:pc + 16]), pc, 1))
                except StopIteration: break
                k = classify(ins); res[k] += 1
                if k != '8086' and len(where[k]) < 4000: where[k].append((s, pc, ins.mnemonic, ins.op_str))
                m = ins.mnemonic; nxt = pc + ins.size
                if m in ('ret', 'retf', 'iret', 'hlt'): break
                if m in ('ljmp',) or (m == 'jmp' and ins.operands[0].type != x86.X86_OP_IMM): break
                if m == 'jmp': pc = ins.operands[0].imm & 0xffff; continue
                if (m.startswith('j') or m.startswith('loop') or m == 'call') and ins.operands and ins.operands[0].type == x86.X86_OP_IMM:
                    work.append(ins.operands[0].imm & 0xffff)
                pc = nxt
    return res, where

if __name__ == '__main__':
    res, where = scan(sys.argv[1])
    print(dict(res))
    for k in ('186', '286+', '386+', '287'):
        c = collections.Counter(w[2] for w in where[k])
        print(k, dict(c.most_common(12)))
        if k != '186':
            for w in where[k][:12]: print('   seg%d:%04x %s %s' % w)
