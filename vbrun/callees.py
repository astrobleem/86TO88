"""List dangerous (unmarked/frameless, can-move-memory) far callees in the ORIGINAL DLL,
with the far-call sites and external references (entries, far pointers) that reach them,
and flag accesses to the return-address slots inside the callee's own body."""
import sys, json, struct, collections, capstone
from capstone import x86
from endanger import analyse, classify
from reach import explore
from hwrap import entries
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail = True
DANG = {'far', 'int3f', 'indirect', 'limit', 'baddecode'}
fn = sys.argv[1]
segs, calls, ptrs = analyse(fn)
ent = entries(fn)
def body(code, off):
    """own body: recursive over jumps only (not near calls), stop at ret/retf"""
    seen=set(); work=[off]; ins_l=[]
    while work:
        pc=work.pop()
        while pc not in seen and 0<=pc<len(code):
            seen.add(pc)
            try: i=next(md.disasm(bytes(code[pc:pc+16]),pc,1))
            except StopIteration: break
            ins_l.append(i); m=i.mnemonic; nxt=pc+i.size
            if m in ('ret','retf','iret') or m=='ljmp' or (m=='jmp' and i.operands and i.operands[0].type!=x86.X86_OP_IMM): break
            if m=='jmp': pc=i.operands[0].imm&0xffff; continue
            if (m.startswith('j') or m.startswith('loop')) and i.operands and i.operands[0].type==x86.X86_OP_IMM:
                work.append(i.operands[0].imm&0xffff)
            pc=nxt
    return ins_l
out={}
tgt=collections.defaultdict(lambda: dict(sites=[],ext=[]))
for c in calls:
    if c[4]=='jmpf': continue
    tgt[(c[2],c[3])]['sites'].append((c[0],c[1],c[4]))
for o,(s,off) in ent.items():
    if not segs[s-1]['flags']&1: tgt[(s,off)]['ext'].append('ord%d'%o)
for p in ptrs: tgt[(p[2],p[3])]['ext'].append('ptr%d:%x'%(p[0],p[1]))
for k,v in tgt.items():
    code=segs[k[0]-1]['code']
    if k[1]>=len(code): continue
    cl=classify(code,k[1])
    if cl=='marked': continue
    ev,_=explore(code,k[1])
    if not ev&DANG: continue
    b=body(code,k[1]); rets=set(); flags=[]; framed=False
    for i in b:
        if i.mnemonic=='retf': rets.add(i.operands[0].imm if i.operands else 0)
        if i.mnemonic=='ret': flags.append('nearret@%x'%i.address)
        if i.mnemonic=='mov' and i.op_str=='bp, sp': framed=True
        for o in i.operands:
            if o.type==x86.X86_OP_MEM:
                base=i.reg_name(o.mem.base) if o.mem.base else ''
                if base=='bp' and framed and o.mem.disp in (2,4): flags.append('[bp+%d]@%x %s'%(o.mem.disp,i.address,i.mnemonic))
                if base=='bp' and not framed: flags.append('callerbp@%x'%i.address)
                if base=='bx' and any(x.mnemonic=='mov' and x.op_str=='bx, sp' for x in b): flags.append('bx-sp@%x'%i.address)
        if i.mnemonic in ('pop',) and i.op_str in ('ax','bx','cx','dx','si','di') and not framed: flags.append('pops@%x'%i.address)
    out['%d:%d'%k]=dict(cls=cl,rets=sorted(rets),flags=flags[:8],sites=v['sites'],ext=v['ext'],ev=sorted(ev))
json.dump(out,open(sys.argv[2],'w'),indent=0)
c=collections.Counter()
for k,v in out.items():
    ok = len(v['rets'])==1 and not v['flags']
    c['clean' if ok else 'review']+=1
print('dangerous callees',len(out),dict(c),'sites',sum(len(v['sites']) for v in out.values()),'with external refs',sum(1 for v in out.values() if v['ext']))
for k,v in sorted(out.items(),key=lambda x:tuple(map(int,x[0].split(':')))):
    if not(len(v['rets'])==1 and not v['flags']): print(k,v['cls'],v['rets'],v['flags'][:5],'nsites',len(v['sites']),v['ext'][:3])
