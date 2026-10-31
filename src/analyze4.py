import sys, pathlib, json
sys.path.insert(0,"/tmp/unpack-main/oemdisplay-tandy-main/tools/W31CHECK")
from w31check import NEImage, _disassemble_reachable
import capstone
data=pathlib.Path("/Users/macsd/winmine-hack/upstream/extract31/WINDOWS/WINMINE.EXE").read_bytes()
img=NEImage(data,"w"); seg=img.segments[0]
res=_disassemble_reachable(img)
# reconstruct covered bytes by re-running decode logic? Instead: linear sweep decode and compare offsets
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail=True
# Get reachable instruction offsets from unsupported + we need all: monkey - redo simple BFS like w31check is complex.
# Alternative: linear sweep whole segment
off=0; lin=[]
while off < len(seg.data):
    ins=list(md.disasm(seg.data[off:], off, count=1))
    if not ins: print("linear fail at", hex(off)); break
    lin.append(ins[0]); off+=ins[0].size
print("linear sweep instructions", len(lin), "ends", hex(off))
from collections import Counter
c=Counter()
sites186=[]
for ins in lin:
    raw=bytes(ins.bytes)
    if ins.mnemonic=="push" and ins.operands and ins.operands[0].type==capstone.x86_const.X86_OP_IMM:
        c["push"]+=1; sites186.append(ins)
    elif ins.mnemonic=="imul" and len(ins.operands)==3:
        c["imul"]+=1; sites186.append(ins)
    elif ins.mnemonic in ("shl","shr","sar","rol","ror","rcl","rcr","sal") and raw[0] in (0xC0,0xC1):
        c["shift"]+=1; sites186.append(ins)
print("linear 186 sites", c, sum(c.values()))
reach_off={u["offset"] for u in res["unsupported_instructions"]}
lin_off={ins.address for ins in sites186}
print("linear-only 186 sites (not in reachable):", sorted(hex(x) for x in lin_off-reach_off))
for ins in sites186:
    if ins.address in lin_off-reach_off:
        print(f" {ins.address:04x}: {bytes(ins.bytes).hex()} {ins.mnemonic} {ins.op_str}")
print("reachable-only not in linear:", sorted(hex(x) for x in reach_off-lin_off)[:20])
# entry points & internal relocation targets as extra roots
print("internal relocs targets:")
for r in img.internal_relocations()[:20]: print(r)
print("count internal", len(img.internal_relocations()))
