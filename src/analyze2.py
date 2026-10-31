import sys, pathlib, json, collections
sys.path.insert(0,"/tmp/unpack-main/oemdisplay-tandy-main/tools/W31CHECK")
from w31check import NEImage

def exports_of(path):
    im=NEImage(pathlib.Path(path).read_bytes(), str(path))
    byname,ords,complete=im.exports()
    # invert
    inv={}
    for k,v in byname.items(): inv.setdefault(v,[]).append(k)
    return byname,ords,complete,inv

winmine=NEImage(pathlib.Path("/Users/macsd/winmine-hack/upstream/extract31/WINDOWS/WINMINE.EXE").read_bytes(),"winmine")
mods30={
 "KERNEL": "/Users/macsd/winmine-hack/upstream/extract30/WINDOWS/SYSTEM/KERNEL.EXE",
 "USER": "/Users/macsd/winmine-hack/upstream/extract30/WINDOWS/SYSTEM/USER.EXE",
 "GDI": "/Users/macsd/winmine-hack/upstream/extract30/WINDOWS/SYSTEM/GDI.EXE",
 "SOUND": "/Users/macsd/winmine-hack/upstream/extract30/WINDOWS/SYSTEM/SOUND.DRV",
}
cache={}
for m,p in mods30.items():
    byname,ords,complete,inv=exports_of(p)
    cache[m]=(byname,ords,inv)
    print(m, "exports complete", complete, "ordinal count", len(ords))

missing=[]
rows=[]
for imp in winmine.imports:
    mod=imp.module.upper()
    if mod=="SHELL":
        rows.append((mod,imp.ordinal,"ShellAbout (Win3.1 SHELL.22)","MISSING - no SHELL.DLL in Win3.0"))
        missing.append("SHELL.22 ShellAbout")
        continue
    byname,ords,inv=cache[mod]
    name=inv.get(imp.ordinal,["?"])
    status="OK" if imp.ordinal in ords else "MISSING"
    if status=="MISSING": missing.append(f"{mod}.{imp.ordinal} {name}")
    rows.append((mod,imp.ordinal,",".join(name),status))
for r in rows: print(r)
print("MISSING in Win3.0:", missing)

# segment flags decode
for s in winmine.segments:
    f=s.flags
    print(f"seg{s.number} flags {f:#06x} type={'DATA' if f&1 else 'CODE'} iter={bool(f&8)} reloc={bool(f&0x100)} preload={bool(f&0x40)} loadoncall={bool(f&0x4000)} discard={bool(f&0x1000)} shareable={bool(f&0x2000)} moveable={bool(f&0x10)} readonly={bool(f&0x8000 if s.is_data else False)}")
# resources parse manually
import struct
data=winmine.data; h=winmine.ne_offset
rt_off=h+winmine.resource_table_offset
shift=struct.unpack_from("<H", data, rt_off)[0]
print(f"resource table at {rt_off:#x} shift {shift}")
pos=rt_off+2
res=[]
while True:
    tid, n, _ = struct.unpack_from("<HHI", data, pos); pos+=8
    if tid==0: break
    for i in range(n):
        off,len_,flags,rid,resv = struct.unpack_from("<HHHI I".replace(" ",""), data, pos); pos+=12
        res.append((tid,rid,off<<shift, len_<<shift, flags))
        print(f" resource type {tid} ({ {1:'CURSOR',2:'BITMAP',3:'ICON',4:'MENU',5:'DIALOG',6:'STRING',9:'ACCEL',14:'GROUP_CURSOR',16:'VERSION'}.get(tid,tid)}) id {rid} off {off<<shift:#x} len {len_<<shift} flags {flags:#x}")
print("resources total", len(res))
pathlib.Path("/Users/macsd/winmine-hack/artifacts/imports-win30.json").write_text(json.dumps([{"module":r[0],"ordinal":r[1],"win30_name":r[2],"status":r[3]} for r in rows],indent=2))
