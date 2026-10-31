import sys, pathlib, json, struct
# gen_sites needs the NEImage parser from the Windows XT tools (w31check) and capstone;
# put w31check on PYTHONPATH. The generated tables are committed under artifacts/, so
# rebuilding the TSR/DLL does not require this script.
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from w31check import NEImage
import capstone
from capstone import x86_const

ROOT = pathlib.Path(__file__).resolve().parent.parent
data=pathlib.Path(sys.argv[1]).read_bytes()  # usage: gen_sites.py <path-to-WINMINE.EXE>
img=NEImage(data,"w"); seg=img.segments[0]
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16); md.detail=True

def sweep(start,end):
    off=start; sites=[]
    while off<end:
        ins=list(md.disasm(seg.data[off:end],off,count=1))
        assert ins, hex(off)
        ins=ins[0]; raw=bytes(ins.bytes)
        typ=None; reg=0; srcreg=0; imm=0
        if ins.mnemonic=="push" and len(ins.operands)==1 and ins.operands[0].type==x86_const.X86_OP_IMM:
            typ=0; imm=ins.operands[0].imm & 0xFFFF
        elif ins.mnemonic in ("shl","shr","sar") and raw[0] in (0xC0,0xC1):
            typ={"shl":1,"shr":2,"sar":3}[ins.mnemonic]; reg=ins.operands[0].reg
            # map capstone reg to x86 code via name
            regname=ins.reg_name(reg).upper(); reg={"AX":0,"CX":1,"DX":2,"BX":3,"SP":4,"BP":5,"SI":6,"DI":7}[regname]
            imm=ins.operands[1].imm
        elif ins.mnemonic=="imul" and len(ins.operands)==3:
            typ=4; reg={"AX":0,"CX":1,"DX":2,"BX":3,"SP":4,"BP":5,"SI":6,"DI":7}[ins.reg_name(ins.operands[0].reg).upper()]
            srcreg={"AX":0,"CX":1,"DX":2,"BX":3,"SP":4,"BP":5,"SI":6,"DI":7}[ins.reg_name(ins.operands[1].reg).upper()]
            imm=ins.operands[2].imm & 0xFFFF
        if typ is not None:
            sites.append({"off":off,"type":typ,"reg":reg,"srcreg":srcreg,"imm":imm,"len":ins.size,"orig":raw.hex(),"text":f"{ins.mnemonic} {ins.op_str}"})
        off+=ins.size
    return sites

sites=sweep(0,0x2561)+sweep(0x2563,len(seg.data))
# --- relocation overlap analysis (segment 1) ---
import struct as _st
neoff=_st.unpack_from("<I",data,0x3C)[0]
segtab=_st.unpack_from("<H",data,neoff+0x22)[0]
align=_st.unpack_from("<H",data,neoff+0x32)[0]
_seg1off,_seg1len= _st.unpack_from("<HH",data,neoff+segtab)
seg1_file=_seg1off<<align
rp=seg1_file+_seg1len
nrec=_st.unpack_from("<H",data,rp)[0]; rp+=2
WIDTH={0:1,1:2,2:2,3:4,5:2}
recs=[]
for _ in range(nrec):
    st,ff,off,mod,val=_st.unpack_from("<BBHHH",data,rp); rp+=8
    recs.append((st,ff,off,mod,val))
print("seg1 relocations:",nrec)
cc_sites=[]
f8_sites=[]
for s in sites:
    is_cc=False
    if s["type"]==0 and s["len"]==3:
        for (st,ff,off,mod,val) in recs:
            if off==s["off"]+1 and WIDTH[st]==2:
                assert ff==0 and st in (2,5), (st,ff,off)
                is_cc=True
                s["cc_ordinal"]=val
    if is_cc:
        cc_sites.append(s)
    else:
        f8_sites.append(s)
# no other reloc field may touch any site range
def ranges_overlap(a0,a1,b0,b1): return a0<b1 and b0<a1
for (st,ff,off,mod,val) in recs:
    w=WIDTH[st]
    for s in sites:
        if ranges_overlap(off,off+w,s["off"],s["off"]+s["len"]):
            ok = s in cc_sites and off==s["off"]+1 and w==2
            assert ok, ("unexpected reloc/site overlap",st,ff,hex(off),hex(mod),hex(val),s)
print("CC sites (in-place resolved push):", [(hex(s["off"]), s["cc_ordinal"]) for s in cc_sites])
sites=f8_sites
# chain-walk: every internal chain node must terminate and avoid patched bytes
patched=set()
for s in sites:
    for i in range(s["len"]): patched.add(s["off"]+i)
for s in cc_sites: patched.add(s["off"])
for (st,ff,off,mod,val) in recs:
    if ff!=0 or st not in (2,5): continue
    node=off; steps=0
    while True:
        assert node+1 < _seg1len, ("chain leaves segment", hex(node))
        assert node not in patched and node+1 not in patched, ("chain node patched", hex(node))
        w=_st.unpack_from("<H",seg.data,node)[0]
        if w==0xFFFF: break
        node=w; steps+=1
        assert steps<10000, "chain too long"
print("all internal chains OK; patched seg offsets:", len(patched))

# second region asserted zero in analysis; keep assert
print("sites",len(sites))
# handler table binary: off DW, type DB, reg DB, imm DW, len DB, srcreg DB = 8
tbl=bytearray()
for s in sites:
    tbl+=struct.pack("<HBBHBB", s["off"], s["type"], s["reg"], s["imm"], s["len"], s["srcreg"])
# patch bytes: version + sites
patch=[]
patch.append((0x43E,0x00)); patch.append((0x43F,0x03))
for s in sites:
    fo=0x620+s["off"]
    patch.append((fo,0xCD)); patch.append((fo+1,0xF8))
    for i in range(2,s["len"]): patch.append((fo+i,0x90))
for s in cc_sites:
    patch.append((0x620+s["off"],0xCC))
patch.sort()
pb=bytearray()
for off,b in patch: pb+=struct.pack("<HBx",off,b)
(ROOT/"artifacts/sites-table.bin").write_bytes(bytes(tbl))
(ROOT/"artifacts/patchbytes.bin").write_bytes(bytes(pb))
(ROOT/"artifacts/sites-final.json").write_text(json.dumps(sites,indent=1))
print("table bytes",len(tbl),"patch entries",len(patch),"patch bytes",len(pb))
print(sites[:3], sites[-3:])
ccb=bytearray()
for s in cc_sites: ccb+=struct.pack("<H", s["off"])
(ROOT/"artifacts/cc-sites.bin").write_bytes(bytes(ccb))
(ROOT/"artifacts/cc-sites.json").write_text(json.dumps([{"off":s["off"],"ordinal":s["cc_ordinal"]} for s in cc_sites],indent=1))
print("f8 sites", len(sites), "cc sites", len(cc_sites))
