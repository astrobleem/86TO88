import sys, pathlib, json, collections, struct
sys.path.insert(0,"/tmp/unpack-main/oemdisplay-tandy-main/tools/W31CHECK")
from w31check import NEImage
import capstone

data=pathlib.Path("/Users/macsd/winmine-hack/upstream/extract31/WINDOWS/WINMINE.EXE").read_bytes()
img=NEImage(data,"winmine")
seg=img.segments[0]
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail=True

# Linear sweep is unreliable; use w31check reachable list
import json as J
uns=J.loads(pathlib.Path("/Users/macsd/winmine-hack/artifacts/unsupported-win30.json").read_text())
print("total unsupported", len(uns))
kinds=collections.Counter(); pushforms=collections.Counter(); shiftforms=collections.Counter(); sites=[]
for u in uns:
    off=u["offset"]; ins=list(md.disasm(seg.data[off:off+8], off, count=1))[0]
    raw=bytes(ins.bytes)
    if ins.mnemonic=="push":
        form = "imm16(68)" if raw[0]==0x68 else "imm8(6A)" if raw[0]==0x6A else f"op{raw[0]:02x}"
        pushforms[form]+=1; kind="push_"+form
    elif ins.mnemonic=="imul":
        shiftforms[ins.op_str]+=1; kind="imul"
    else:
        # shift: opcode C0/C1, modrm
        modrm=raw[1] if len(raw)>1 else 0
        regfield=(modrm>>3)&7
        opname={0:"ROL",1:"ROR",2:"RCL",3:"RCR",4:"SHL/SAL",5:"SHR",7:"SAR"}.get(regfield,regfield)
        size="byte" if raw[0]==0xC0 else "word"
        mod=modrm>>6; rm=modrm&7
        operand="reg" if mod==3 else "mem"
        shiftforms[f"{opname} {size} {operand} rm={rm} mod={mod} count={ins.operands[1].imm if len(ins.operands)>1 else '?'}"]+=1
        kind="shift"
    kinds[kind]+=1
    sites.append({"offset":off,"bytes":raw.hex(),"mnemonic":ins.mnemonic,"op_str":ins.op_str,"size":ins.size})
print(kinds)
print("push forms", pushforms)
print("shift/imul forms")
for k,v in shiftforms.most_common(): print(" ",v,k)
# operand values for push
vals=collections.Counter()
for s in sites:
    if s["mnemonic"]=="push": vals[s["op_str"]]+=1
print("top push operands", vals.most_common(20))
# distribution: how many in first bytes / entry path offsets
print("min/max offset", hex(min(s['offset'] for s in sites)), hex(max(s['offset'] for s in sites)))
pathlib.Path("/Users/macsd/winmine-hack/artifacts/sites.json").write_text(json.dumps(sites,indent=1))
# check slack at end of seg1: trailing zeros?
d=seg.data
i=len(d)
while i>0 and d[i-1]==0: i-=1
print("seg1 trailing zero bytes:", len(d)-i, "last nonzero at", hex(i))
# exports entry offsets (callbacks) - those are in seg1 too
print("entry points", img.entry_points)
