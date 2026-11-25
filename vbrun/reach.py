"""Recursive-descent reachability inside one NE segment: does a far function,
while active, ever transfer control in a way that can let the kernel move or
discard memory (far call, far jump, INT 3Fh thunk, indirect transfer)?"""
import capstone
from capstone import x86

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
md.detail = True

def explore(code, entry, limit=20000):
    seen = set(); work = [entry]; events = set(); n = 0
    while work and n < limit:
        pc = work.pop()
        while pc not in seen and 0 <= pc < len(code):
            seen.add(pc); n += 1
            try:
                ins = next(md.disasm(bytes(code[pc:pc + 16]), pc, 1))
            except StopIteration:
                events.add('baddecode'); break
            m = ins.mnemonic; nxt = pc + ins.size
            ops = ins.operands
            if m in ('ret', 'retf', 'iret'):
                break
            if m == 'int':
                if ops and ops[0].imm == 0x3f: events.add('int3f')
                pc = nxt; continue
            if m in ('lcall', 'ljmp') or (m in ('call', 'jmp') and 'far' in ins.op_str):
                events.add('far')
                if m.endswith('jmp'): break
                pc = nxt; continue
            if m == 'call':
                if ops and ops[0].type == x86.X86_OP_IMM:
                    work.append(ops[0].imm & 0xffff)
                else:
                    events.add('indirect')
                pc = nxt; continue
            if m == 'jmp':
                if ops and ops[0].type == x86.X86_OP_IMM:
                    pc = ops[0].imm & 0xffff; continue
                events.add('indirect'); break
            if m.startswith('j') or m in ('loop', 'loope', 'loopne', 'jcxz'):
                if ops and ops[0].type == x86.X86_OP_IMM:
                    work.append(ops[0].imm & 0xffff)
                pc = nxt; continue
            pc = nxt
    if n >= limit: events.add('limit')
    return events, seen
