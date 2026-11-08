import struct,sys,collections
CBOFF=633

RETF_SEGS={2,4}
def patch_sites(i,code,rem,t5,newrecs,stats):
    seg=i+1
    u2={}
    for (t,fl,a,b),sites in rem.items():
        if a in FIX: continue
        for p in sites: u2[p]=(a,b,(t,fl,a,b))
    if not u2 and not t5: return
    cache={}; T=[None]
    def tmp():
        if T[0] is None:
            T[0]=len(code); code.extend(b'\0\0')
        return T[0]
    def vvfor(a,off):
        if (a,off) not in cache:
            v=len(code); code.extend(b'\xff\xff\0\0'); cache[(a,off)]=v
            newrecs.append(struct.pack('<BBHHH',3,0,v,0xff,CONV_ORDN(a,off)))
        return cache[(a,off)]
    def emit(b):
        at=len(code); code.extend(b); return at
    def w(x): return struct.pack('<H',x)
    def rewrite(start,length,stub):
        code[start]=0xe8; struct.pack_into('<h',code,start+1,stub-(start+3))
        for k in range(start+3,start+length): code[k]=0x90
    def consume(p):
        if p in u2:
            key=u2[p][2]; rem[key].remove(p); del u2[p]
        else:
            del t5[p]
    getsegs={}
    def getseg(a):
        if a not in getsegs:
            off=CBOFF if a==107 else CONV_ORIGLEN(a)
            v=vvfor(a,off); tt=tmp()
            st=len(code)
            emit(b'\x9c\x50\x53\x06'+b'\x2e\xff\x1e'+w(v)+b'\x2e\xc4\x1e'+w(v)+b'\x26\x8b\x47\x08'+b'\x2e\xa3'+w(tt)+b'\x07\x5b\x58\x9d\xc3')
            getsegs[a]=st
        return getsegs[a]
    # P1 push seg; push off
    for p in sorted(u2):
        if p not in u2: continue
        a,b,_=u2[p]
        if code[p-1]==0x68 and code[p+2]==0x68 and (p+3) in t5 and t5[p+3][2]==a:
            off=t5[p+3][3]; v=vvfor(a,off); tt=tmp(); st=len(code)
            emit(b'\x2e\x8f\x06'+w(tt)+b'\x2e\xff\x36'+w(v+2)+b'\x2e\xff\x36'+w(v)+b'\x2e\xff\x26'+w(tt))
            rewrite(p-1,6,st); consume(p); consume(p+3); stats['p1']+=1
    # P2 mov r1,off ; mov r2,seg
    for q in sorted(t5):
        if q not in t5: continue
        if 0xb8<=code[q-1]<=0xbf and (q+3) in u2 and 0xb8<=code[q+2]<=0xbf and u2[q+3][0]==t5[q][2]:
            a=t5[q][2]; v=vvfor(a,t5[q][3]); r1=code[q-1]-0xb8; r2=code[q+2]-0xb8; st=len(code)
            emit(b'\x2e\x8b'+bytes([0x06|r1<<3])+w(v)+b'\x2e\x8b'+bytes([0x06|r2<<3])+w(v+2)+b'\xc3')
            rewrite(q-1,6,st); consume(q); consume(q+3); stats['p2']+=1
    # P3 mov [bp+d1],off ; mov [bp+d2],seg
    for q in sorted(t5):
        if q not in t5: continue
        if code[q-3:q-1]==b'\xc7\x46' and code[q+2:q+4]==b'\xc7\x46' and (q+5) in u2:
            a=t5[q][2]; v=vvfor(a,t5[q][3]); d1=code[q-1]; d2=code[q+4]; st=len(code)
            emit(b'\x50\x2e\xa1'+w(v)+b'\x89\x46'+bytes([d1])+b'\x2e\xa1'+w(v+2)+b'\x89\x46'+bytes([d2])+b'\x58\xc3')
            rewrite(q-3,10,st); consume(q); consume(q+5); stats['p3']+=1
    # P4/P5 cmp ax,off ... cmp dx,seg
    for q in sorted(t5):
        if q not in t5: continue
        if code[q-1]==0x3d:
            a=t5[q][2]; off=t5[q][3]; v=vvfor(a,off); st=len(code)
            emit(b'\x2e\x3b\x06'+w(v)+b'\xc3'); rewrite(q-1,3,st)
            for p in sorted(u2):
                if u2[p][0]==a and 0<p-q<16 and code[p-2:p]==b'\x81\xfa':
                    st=len(code); emit(b'\x2e\x3b\x16'+w(v+2)+b'\xc3'); rewrite(p-2,4,st); consume(p); break
            consume(q); stats['p4']+=1
    # P6 lone selector loads
    for p in sorted(u2):
        if p not in u2: continue
        a,b,_=u2[p]
        if 0xb8<=code[p-1]<=0xbf:
            r=code[p-1]-0xb8
            if a==seg:
                code[p-1]=0x8c; code[p]=0xc8|r; code[p+1]=0x90
            else:
                gs=getseg(a); tt=tmp(); st=len(code)
                emit(b'\xe8'+struct.pack('<h',gs-(st+3))+b'\x2e\x8b'+bytes([0x06|r<<3])+w(tt)+b'\xc3')
                rewrite(p-1,3,st)
            consume(p); stats['p6']+=1

import os,json
def _fix():
    v=os.environ.get('FIXSEGS','')
    if not v: return set()
    if v=='all': return set(range(1,107))
    if v.startswith('@'): return {int(x) for x in json.load(open(v[1:]))}
    return {int(x) for x in v.split(',')}
FIX=_fix()
# WRAP=@callees.json : route far calls to unmarked callees that can move memory
# through a wrapper (in FIXED segment WRAPSEG) that locks the caller's code
# segment for the duration of the call.
WRAPJ=os.environ.get('WRAP','')
WRAPSEG=int(os.environ.get('WRAPSEG','24'))
if WRAPJ: FIX.add(WRAPSEG)
def _lock():
    v=os.environ.get('LOCKSEGS','')
    if not v: return set()
    if v=='all': return set(range(1,107))
    if v.startswith('@'): return {int(x) for x in json.load(open(v[1:]))}
    return {int(x) for x in v.split(',')}
LOCK=_lock()
NODISCARD=os.environ.get('NODISCARD')=='1'
VB=True
def conv(src, dst, report=True, vb=True):
    global VB,RETF_SEGS,TABS
    VB=vb
    TABS={15,33,80,103,107} if vb else {4}
    if not vb: RETF_SEGS=set()
    d=bytearray(open(src,'rb').read())
    ne=struct.unpack_from('<I',d,0x3c)[0]
    st=struct.unpack_from('<H',d,ne+0x22)[0]; al=struct.unpack_from('<H',d,ne+0x32)[0]
    N=struct.unpack_from('<H',d,ne+0x1c)[0]
    nres=struct.unpack_from('<H',d,ne+0x34)[0]
    assert nres==0 or True
    ents=[struct.unpack_from('<HHHH',d,ne+st+i*8) for i in range(N)]
    first=min(e[0] for e in ents if e[0])<<al
    last_end=max((e[0]<<al)+((e[1] or 0x10000)+ (2+8*struct.unpack_from('<H',d,(e[0]<<al)+(e[1] or 0x10000))[0] if e[2]&0x100 else 0)) for e in ents if e[0])
    blobs=[]; newents=[]
    stats=collections.Counter()
    ords={}
    ORD0=[101]; MOVCNT=[0]
    def ordn(seg,off):
        k=(seg,off)
        if k not in ords: ords[k]=ORD0[0]+len(ords)
        return ords[k]
    global CONV_ORDN,CONV_ORIGLEN
    CONV_ORDN=ordn; CONV_ORIGLEN=lambda a: max(ents[a-1][1],ents[a-1][3])
    eto0,etl0=struct.unpack_from('<HH',d,ne+4)
    tot=0; q=ne+eto0
    while d[q]:
        c,ty=d[q],d[q+1]; q+=2
        if ty==0: pass
        elif ty==0xff: q+=6*c
        else: q+=3*c
        tot+=c
    ORD0[0]=tot+1
    for i,(o,l,f,m) in enumerate(ents):
        if o==0:
            blobs.append(None); newents.append([0,l,f,m]); continue
        base=o<<al; ln=l or 0x10000
        code=bytearray(d[base:base+ln])
        if m and m>ln: code+=b'\0'*(m-ln)   # implicit zero tail up to minalloc must survive appended stubs
        recs=[]
        if f&0x100:
            n=struct.unpack_from('<H',d,base+ln)[0]
            recs=[bytes(d[base+ln+2+k*8:base+ln+10+k*8]) for k in range(n)]
        newrecs=[]; rem=collections.defaultdict(list); t5={}
        for r in recs:
            t,fl,off,a,b=struct.unpack('<BBHHH',r)
            if t&15==2 and fl&3==0:
                p=off; sites=[]
                while True:
                    nxt=struct.unpack_from('<H',code,p)[0]; sites.append(p)
                    if nxt==0xffff: break
                    p=nxt
                for p in sites:
                    op=code[p-3] if p>=3 else None
                    # far pointer: 9A/EA call/jmp, or a table entry (non-reg-load opcode): treat 9A/EA and 'tables' as convertible
                    prev=code[p-1] if p>=1 else 0
                    conv_ok = (a not in FIX) and (VB and (i+1,p)==(4,0x268)) or (a not in FIX) and (op in (0x9a,0xea) or ((i+1) in TABS and not (0xb8<=prev<=0xbf or prev==0x68)))
                    if VB and i==0 and p in (59,182):
                        continue
                    if conv_ok:
                        lit=struct.unpack_from('<H',code,p-2)[0]
                        newrecs.append(struct.pack('<BBHHH',3,0,p-2,0xff,ordn(a,lit))); stats['call']+=1
                        struct.pack_into('<HH',code,p-2,0xffff,0)
                    else:
                        rem[(r[0],r[1],a,b)].append(p); stats['left']+=1
                        if os.environ.get('DBG'): print('LEFT seg',i+1,'site',hex(p),'tgt',a,'off',hex(b),'ctx',code[max(0,p-4):p+4].hex())
            elif t&15==5 and fl&3==0 and not fl&4 and a!=0xff and ents[a-1][2]&0x10 and a not in FIX:
                p=off
                while True:
                    nxt=struct.unpack_from('<H',code,p)[0]; t5[p]=(r[0],r[1],a,b)
                    if nxt==0xffff: break
                    p=nxt
            else:
                newrecs.append(r)
        if (i+1) in RETF_SEGS and (i+1) not in FIX: code+=b'\xcb'
        patch_sites(i,code,rem,t5,newrecs,stats)
        for p,(t,fl,a,b) in sorted(t5.items()): rem[(t,fl,a,b)].append(p)
        if VB and i==104:
            # seg 105 grow-segment routine: callers keep the old segment value (selector
            # semantics); in real mode GMEM_MOVEABLE lets GlobalReAlloc move the locked
            # block. Mask MOVEABLE as well as NOCOMPACT so it grows in place or fails.
            assert bytes(code[0xe5:0xe9])==bytes.fromhex('806606fb'), code[0xe5:0xe9].hex()
            code[0xe8]=0xf9; stats['seg105']=1
            if os.environ.get('VBALLOCFIXED'):
                # alloc entry: GMEM_FIXED instead of locked GMEM_MOVEABLE (packs low)
                assert bytes(code[0x3b:0x3f])==bytes.fromhex('806606fb'), code[0x3b:0x3f].hex()
                code[0x3e]=0xf9; stats['allocfixed']=1
            if os.environ.get('VBSTRRES'):
                # bit 0x08 of the flags marks the program's data/string segment (seg 5
                # below); clear it before GlobalAlloc
                code[0x3e]&=0xf7
            if os.environ.get('VBALLOCLOW'):
                # alloc entry: also clear bit 0 (kernel GA_ALLOCHIGH in real mode)
                assert bytes(code[0x3b:0x3f])==bytes.fromhex('806606fb'), code[0x3b:0x3f].hex()
                code[0x3e]=0xfa; code[0xe8]=0xf8; stats['alloclow']=1
            # allocate entry (0x0000): reserve headroom so later grows stay in place
            res=int(os.environ.get('VBHEAPRES','0'),0)
            if res:
                assert bytes(code[0x30:0x33])==bytes.fromhex('8b4608'), code[0x30:0x33].hex()
                stub5=len(code)
                if os.environ.get('VBSTRRES'):
                    # flagged allocation (seg 5 program data/string segment): at least VBSTRRES
                    sr=int(os.environ['VBSTRRES'],0)
                    code+=bytes.fromhex('f6460608740c8b4608')+b'\x3d'+struct.pack('<H',sr)+b'\x73\x03\xb8'+struct.pack('<H',sr)+b'\xc3'
                if os.environ.get('VBHEAPGROW')=='2':
                    # 2*size (growth headroom), at least res
                    code+=bytes.fromhex('8b460803c07303b8e0ff')+b'\x3d'+struct.pack('<H',res)+b'\x73\x03'+b'\xb8'+struct.pack('<H',res)+b'\xc3'
                elif os.environ.get('VBHEAPGROW')=='8':
                    # size + size/8 (growth headroom), at least res
                    code+=bytes.fromhex('8b46088bd0d1ead1ead1ea03c27303b8e0ff')+b'\x3d'+struct.pack('<H',res)+b'\x73\x03'+b'\xb8'+struct.pack('<H',res)+b'\xc3'
                elif os.environ.get('VBHEAPGROW'):
                    # size + size/4 (growth headroom), at least res
                    code+=bytes.fromhex('8b46088bd0d1ead1ea03c27303b8e0ff')+b'\x3d'+struct.pack('<H',res)+b'\x73\x03'+b'\xb8'+struct.pack('<H',res)+b'\xc3'
                else:
                    code+=bytes.fromhex('8b4608')+b'\x3d'+struct.pack('<H',res)+b'\x73\x03'+b'\xb8'+struct.pack('<H',res)+b'\xc3'
                code[0x30]=0xe8; struct.pack_into('<h',code,0x31,stub5-0x33)
                stats['heapres']=res
        if VB and i==4 and os.environ.get('VBSTRRES'):
            # seg 5 (EXE loader) allocates the program's data segment with the size stored
            # in the EXE (JIGSAWED: 0xA8). The string manager (seg 106) later grows it in
            # 0x200 steps through seg 105's in-place grow; it is GMEM_FIXED, held in
            # [0x2e0a] and in callers' DS, so it cannot move. Mark the allocation so seg
            # 105 gives it VBSTRRES bytes up front.
            assert bytes(code[0x1ff:0x203])==bytes.fromhex('50506a02'), code[0x1ff:0x203].hex()
            code[0x202]=0x0a; stats['strres']=1
        if VB and i==74 and os.environ.get('VBLHEAP'):
            # seg 75: VB's general local heap starts at 0x800 and is kept locked, so it
            # can only grow in place in real mode; give it headroom up front
            assert bytes(code[0x695:0x69a])==bytes.fromhex('6a10680008'), code[0x695:0x69a].hex()
            struct.pack_into('<H',code,0x698,int(os.environ['VBLHEAP'],0)); stats['lheap']=1
        if VB and i==70 and os.environ.get('VBPROBE'):
            # seg 71 form/module create: allocates 8000 bytes from the general local
            # heap and frees them at once, a probe that forces the (locked) heap to
            # carry 8 KB of free space for good; probe a smaller amount instead
            assert bytes(code[0x58:0x5b])==bytes.fromhex('68401f'), code[0x58:0x5b].hex()
            struct.pack_into('<H',code,0x59,int(os.environ['VBPROBE'],0)); stats['probe']=1
        if VB and i in (70,87) and (os.environ.get('VBLHEAP2') or os.environ.get('VBLHEAP%d'%(i+1))):
            # other VB local heaps created with 0x400 bytes (seg 71 temp heap, seg 88 heap)
            at={70:0x90,87:0x10}[i]
            assert bytes(code[at:at+3])==bytes.fromhex('680004'), (i,code[at:at+3].hex())
            v=os.environ.get('VBLHEAP%d'%(i+1)) or os.environ['VBLHEAP2']
            struct.pack_into('<H',code,at+1,int(v,0)); stats['lheap2']+=1
        if VB and i==76:
            # seg 77 grow-table helper: 'test cl,1 / jne' rejects even values as invalid
            # selectors (PM RPL bits); real-mode segment values can be even
            assert bytes(code[0xdb:0xe0])==bytes.fromhex('f6c1017504'), code[0xdb:0xe0].hex()
            code[0xde]=0xeb; stats['seg77sel']=1
        if VB and i==16:
            assert bytes(code[0x1b4:0x1b8])==bytes.fromhex('3bc7750c'), code[0x1b4:0x1b8].hex()
            code[0x1b6]=0x90; code[0x1b7]=0x90   # integrity-check compare (header CRC) can never match a rewritten NE header
            stats['crc']=1
        if VB and i==0:
            L=len(code)
            code[0xb4]=0xc3                       # skip INT 0 handler install (needs selector of seg 2)
            vv=L+0x1c
            stub=bytearray()
            stub+=b'\x53'                         # push bx
            stub+=b'\x2e\xff\x1e'+struct.pack('<H',vv)   # call far [cs:vv]  (thunk call loads seg 107, hits RETF)
            stub+=b'\x2e\xc4\x1e'+struct.pack('<H',vv)   # les bx,[cs:vv]
            stub+=b'\x26\x8b\x47\x08'                 # mov ax,[es:bx+3]  = real segment from patched thunk
            stub+=b'\x5b'                         # pop bx
            stub+=b'\x8e\xd8\x33\xf6'                 # mov ds,ax ; xor si,si
            jb=L+len(stub)+3
            stub+=b'\xe9'+struct.pack('<h',0x42-jb)  # jmp back to 0x42
            assert len(stub)<=0x1c, len(stub)
            stub+=b'\x90'*(0x1c-len(stub))
            stub+=b'\xff\xff\0\0'               # chain terminator for the vv reloc site
            code[0x3a:0x42]=b'\xe9'+struct.pack('<h',L-0x3d)+b'\x90'*5
            code+=stub
            newrecs.append(struct.pack('<BBHHH',3,0,vv,0xff,ordn(107,CBOFF)))
            stats['crt0patch']+=1
        # relink remaining chains
        for (t,fl,a,b),sites in rem.items():
            if not sites: continue
            sites.sort()
            for j,p in enumerate(sites):
                struct.pack_into('<H',code,p,sites[j+1] if j+1<len(sites) else 0xffff)
            newrecs.append(struct.pack('<BBHHH',t,fl,sites[0],a,b))
        # defer: lock stubs may still be appended once all ordinals are known
        if NODISCARD: f&=~0x1000
        if (i+1) in FIX: f&=~0x1010
        blobs.append((code,newrecs)); newents.append([None,len(code),f,m])
    if WRAPJ and VB: wrap_pass(d,ne,blobs,ordn,ords,stats)
    if VB and os.environ.get('TABGROW'): tabgrow_pass(d,ne,blobs,stats)
    if VB and os.environ.get('GROWKEEP'): growkeep_pass(d,ne,blobs,stats)
    if VB and os.environ.get('CTXGROW'): ctxgrow_pass(d,ne,blobs,ordn,stats)
    if VB and os.environ.get('FSHRINK'): fshrink_pass(d,ne,blobs,stats)
    if os.environ.get('FSW8087'): fsw_pass(blobs,stats)
    # header: old up to entry table, new entry table, then align
    eto,etl=struct.unpack_from('<HH',d,ne+4)
    oldet=bytes(d[ne+eto:ne+eto+etl])
    assert oldet[-1]==0
    # parse the old table into per-ordinal entries, append converter ordinals,
    # demote movable entries into FIXED segments to fixed entries, re-bundle
    L=[]; q=0
    while oldet[q]:
        c,ty=oldet[q],oldet[q+1]; q+=2
        for k in range(c):
            if ty==0: L.append(None)
            elif ty==0xff: L.append(('M',oldet[q+3],oldet[q],struct.unpack_from('<H',oldet,q+4)[0])); q+=6
            else: L.append(('F',ty,oldet[q],struct.unpack_from('<H',oldet,q+1)[0])); q+=3
    assert len(L)==ORD0[0]-1
    for (seg,off),o in sorted(ords.items(), key=lambda kv: kv[1]):
        assert o==len(L)+1; L.append(('M',seg,1,off))
    L=[('F',e[1],e[2],e[3]) if e and e[0]=='M' and e[1] in FIX else e for e in L]
    if LOCK:
        nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
        mods=[bytes(d[ne+io+struct.unpack_from('<H',d,ne+mo+2*k)[0]+1:ne+io+struct.unpack_from('<H',d,ne+mo+2*k)[0]+1+d[ne+io+struct.unpack_from('<H',d,ne+mo+2*k)[0]]]).upper() for k in range(nmods)]
        KIDX=mods.index(b'KERNEL')+1
        lockr={}; stubs={}
        def lockroutine(sg):
            if sg not in lockr:
                code,recs=blobs[sg-1]
                F=len(code); code.append(0)
                L0=len(code)
                body=bytearray()
                body+=b'\x2e\x80\x3e'+struct.pack('<H',F)+b'\x00'      # cmp byte [cs:F],0
                body+=b'\x75\x00'                                         # jne done (patched)
                body+=b'\x9c\x50\x53\x51\x52\x06'                     # pushf; push ax bx cx dx es
                body+=b'\x2e\xc6\x06'+struct.pack('<H',F)+b'\x01'      # mov byte [cs:F],1
                body+=b'\x0e'                                              # push cs
                site=L0+len(body)+1
                body+=b'\x9a\xff\xff\x00\x00'                          # call far KERNEL.LockSegment
                body+=b'\x07\x5a\x59\x5b\x58\x9d'                     # pop es dx cx bx ax; popf
                done=len(body); body+=b'\xc3'
                assert body[6]==0x75; body[7]=done-8                       # jne rel8 -> done
                code+=body
                recs.append(struct.pack('<BBHHH',3,1,site,KIDX,23))
                lockr[sg]=L0; stats['lockseg']+=1
            return lockr[sg]
        def stub(sg,off):
            if (sg,off) not in stubs:
                lk=lockroutine(sg); code,recs=blobs[sg-1]
                S=len(code)
                code+=b'\xe8'+struct.pack('<H',(lk-(S+3))&0xffff)+b'\xe9'+struct.pack('<H',(off-(S+6))&0xffff)
                stubs[(sg,off)]=S; stats['lockstub']+=1
            return stubs[(sg,off)]
        L=[(e[0],e[1],e[2],stub(e[1],e[3])) if e and e[1] in LOCK else e for e in L]
    for k,b in enumerate(blobs):
        if b is None: continue
        code,recs=b
        e=newents[k]; f=e[2]; m=e[3]
        blob=bytes(code)
        if recs: blob+=struct.pack('<H',len(recs))+b''.join(recs); f|=0x100
        else: f&=~0x100
        blobs[k]=blob; newents[k]=[None,len(code),f,m if m==0 else max(m,len(code))]
    et=bytearray(); i0=0
    def key(e): return 0 if e is None else (0xff if e[0]=='M' else e[1])
    while i0<len(L):
        k=key(L[i0]); j=i0
        while j<len(L) and key(L[j])==k and j-i0<255: j+=1
        et+=bytes([j-i0,k])
        for e in L[i0:j]:
            if k==0: pass
            elif k==0xff: et+=bytes([e[2],0xcd,0x3f,e[1]])+struct.pack('<H',e[3])
            else: et+=bytes([e[2]])+struct.pack('<H',e[3])
        i0=j
    et+=b'\0'
    MOVCNT[0]=sum(1 for e in L if e and e[0]=='M')
    nrs=struct.unpack_from('<I',d,ne+0x2c)[0]; nrsz=struct.unpack_from('<H',d,ne+0x20)[0]
    head=bytearray(d[:ne+eto])+et
    struct.pack_into('<H',head,ne+6,len(et))
    struct.pack_into('<I',head,ne+0x2c,len(head))
    head+=d[nrs:nrs+nrsz]+b'\0'*16
    out=head
    for blob,e in zip(blobs,newents):
        if blob is None: continue
        pad=(-len(out))%(1<<al); out+=b'\0'*pad
        e[0]=len(out)>>al
        out+=blob
    pad=(-len(out))%(1<<al); out+=b'\0'*pad
    rt=struct.unpack_from('<H',d,ne+0x24)[0]; rn=struct.unpack_from('<H',d,ne+0x26)[0]
    if rt!=rn:
        ra=struct.unpack_from('<H',d,ne+rt)[0]
        out+=b'\0'*((last_end-len(out))%(1<<ra))
        delta=len(out)-last_end; assert delta%(1<<ra)==0
        q=ne+rt+2
        while True:
            tid,cnt=struct.unpack_from('<HH',out,q)
            if tid==0: break
            q+=8
            for k in range(cnt):
                o0=struct.unpack_from('<H',out,q)[0]
                if (o0<<ra)>=last_end: struct.pack_into('<H',out,q,o0+(delta>>ra))
                q+=12
        stats['res_delta']=delta
    tail=bytes(d[last_end:]); out+=tail
    for i,e in enumerate(newents): struct.pack_into('<HHHH',out,ne+st+i*8,*e)
    stats['entries']=len(ords)
    struct.pack_into('<H',out,ne+0x30,MOVCNT[0])
    nz=[e[0] for e in newents if e[0]]; g0=nz[0]-1; g1=nz[1] if len(nz)>1 else nz[0]+1
    struct.pack_into('<HH',out,ne+0x38,g0,g1-g0)
    # 0x0008 = protected-mode-only: the real-mode loader refuses such modules
    struct.pack_into('<H',out,ne+0xc,struct.unpack_from('<H',out,ne+0xc)[0]&~0x0008)
    open(dst,'wb').write(out)
    if report: print(dict(stats),'size',len(d),'->',len(out),'nres',nres,'tail',len(tail))
def fsw_pass(blobs,stats):
    # FNSTSW AX (DF E0) is a 287 instruction: an 8087 and WIN87EM's 8087 emulator
    # reject it (FPE 0x87, unemulated), which VB reports as error 5. Replace each
    # 'wait; fnstsw ax' by a near call to a per-segment stub doing fnstsw m16.
    for si,b in enumerate(blobs):
        if b is None: continue
        c,rr=b; stub=None; keep=[]
        for r in rr:
            t,fl,off,a,x=struct.unpack('<BBHHH',r)
            if fl&3==3 and bytes(c[off:off+3])==b'\x9b\xdf\xe0':
                if stub is None:
                    while len(c)&1: c.append(0x90)
                    stub=len(c)
                    # push bp / mov bp,sp / push ax / wait; fnstsw [bp-2] / pop ax / pop bp / ret
                    c+=bytes.fromhex('5589e5509bdd7efe585dc3')
                    keep.append(struct.pack('<BBHHH',t,fl,stub+4,a,x))
                c[off]=0xe8; struct.pack_into('<h',c,off+1,stub-(off+3))
                stats['fsw_sites']+=1
                continue
            keep.append(r)
        rr[:]=keep

def growkeep_pass(d,ne,blobs,stats):
    # seg 105 grow: don't GlobalReAlloc a block that already has the requested size
    # (keeps the headroom of GMEM_FIXED heaps); see asm/growkeep.asm
    import subprocess,tempfile
    nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
    def mname(k):
        o=struct.unpack_from('<H',d,ne+mo+2*k)[0]; return bytes(d[ne+io+o+1:ne+io+o+1+d[ne+io+o]]).upper()
    KIDX=[mname(k) for k in range(nmods)].index(b'KERNEL')+1
    c,rr=blobs[104]
    assert bytes(c[0xec:0xf1])==bytes.fromhex('9affff0000'), c[0xec:0xf1].hex()
    j=[k for k,r in enumerate(rr) if struct.unpack('<BBHHH',r)[2]==0xed]
    assert len(j)==1 and struct.unpack('<BBHHH',rr[j[0]])[3:]==(KIDX,16), [struct.unpack('<BBHHH',rr[k]) for k in j]
    while len(c)&1: c.append(0x90)
    base=len(c); here=os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(['nasm','-f','bin','-DBASE=%d'%base,'--before','[map symbols %s/m]'%td,os.environ.get('VBW_ASM',here+'/asm')+'/growkeep.asm','-o',td+'/b'])
        code=open(td+'/b','rb').read(); sym={}
        for l in open(td+'/m'):
            pr=l.split()
            if len(pr)==3:
                try: sym[pr[2]]=int(pr[1],16)
                except ValueError: pass
    c+=code
    del rr[j[0]]
    rr.append(struct.pack('<BBHHH',3,1,sym['..@gra']+1,KIDX,16))
    rr.append(struct.pack('<BBHHH',3,1,sym['..@gs']+1,KIDX,20))
    c[0xec]=0xe8; struct.pack_into('<h',c,0xed,base-0xef); c[0xef]=0x90; c[0xf0]=0x90
    stats['growkeep']=1

def ctxgrow_pass(d,ne,blobs,ordn,stats):
    # VB module contexts (seg 4 grow paths) keep their data segment in [di+2]. Route
    # their grows through seg 105 'grow2', which falls back to a moving GlobalReAlloc
    # and returns the new segment in DX; store it back into [di+2].
    import subprocess,tempfile
    nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
    def mname(k):
        o=struct.unpack_from('<H',d,ne+mo+2*k)[0]; return bytes(d[ne+io+o+1:ne+io+o+1+d[ne+io+o]]).upper()
    KIDX=[mname(k) for k in range(nmods)].index(b'KERNEL')+1
    c,rr=blobs[104]
    while len(c)&1: c.append(0x90)
    base=len(c); here=os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(['nasm','-f','bin','-DBASE=%d'%base,'-DGROW=0x8a','--before','[map symbols %s/m]'%td,os.environ.get('VBW_ASM',here+'/asm')+'/grow2.asm','-o',td+'/b'])
        code=open(td+'/b','rb').read(); sym={}
        for l in open(td+'/m'):
            pr=l.split()
            if len(pr)==3:
                try: sym[pr[2]]=int(pr[1],16)
                except ValueError: pass
    c+=code
    for nm,o in (('..@gh1',21),('..@gra',16),('..@gh2',21),('..@gs',20)):
        rr.append(struct.pack('<BBHHH',3,1,sym[nm]+1,KIDX,o))
    og=ordn(105,base)
    c,rr=blobs[3]
    def retarget(lc):
        assert c[lc]==0x9a, hex(lc)
        for j,r in enumerate(rr):
            t,fl,off,x,y=struct.unpack('<BBHHH',r)
            if off==lc+1 and t==3 and fl==0 and x==0xff:
                rr[j]=struct.pack('<BBHHH',3,0,off,0xff,og); return
        raise AssertionError('no ordinal reloc at 4:%x'%lc)
    retarget(0xaa); retarget(0x156)
    assert bytes(c[0xaf:0xb6])==bytes.fromhex('0bc07414c1e804'), c[0xaf:0xb6].hex()
    sa=len(c)
    stub=bytearray(bytes.fromhex('895502')+b'\x0b\xc0\x74\x04'+bytes.fromhex('c1e804')+b'\xc3'+b'\x83\xc4\x02\xe9\x00\x00')
    struct.pack_into('<h',stub,len(stub)-2,0xc7-(sa+len(stub)))
    c+=stub
    c[0xaf]=0xe8; struct.pack_into('<h',c,0xb0,sa-0xb2)
    for k in range(0xb2,0xb6): c[k]=0x90
    assert bytes(c[0x15b:0x160])==bytes.fromhex('8bc8c1e804'), c[0x15b:0x160].hex()
    sb=len(c); c+=bytes.fromhex('8955028bc8c1e804c3')
    c[0x15b]=0xe8; struct.pack_into('<h',c,0x15c,sb-0x15e); c[0x15e]=0x90; c[0x15f]=0x90
    stats['ctxgrow']=1

def fshrink_pass(d,ne,blobs,stats):
    # trim each form's / system container's local heap to its live size plus
    # headroom once it is built; see asm/fshrink.asm
    import subprocess,tempfile
    nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
    def mname(k):
        o=struct.unpack_from('<H',d,ne+mo+2*k)[0]; return bytes(d[ne+io+o+1:ne+io+o+1+d[ne+io+o]]).upper()
    KIDX=[mname(k) for k in range(nmods)].index(b'KERNEL')+1
    here=os.path.dirname(os.path.abspath(__file__))
    def add(si,var):
        c,rr=blobs[si]
        while len(c)&1: c.append(0x90)
        base=len(c)
        with tempfile.TemporaryDirectory() as td:
            subprocess.check_call(['nasm','-f','bin','-D'+var,'-DBASE=%d'%base,'-DMINHEAD=%s'%os.environ.get('FSHRINKMIN','0x800'),'--before','[map symbols %s/m]'%td,os.environ.get('VBW_ASM',here+'/asm')+'/fshrink.asm','-o',td+'/b'])
            code=open(td+'/b','rb').read(); sym={}
            for l in open(td+'/m'):
                pr=l.split()
                if len(pr)==3:
                    try: sym[pr[2]]=int(pr[1],16)
                    except ValueError: pass
        c+=code
        rr.append(struct.pack('<BBHHH',3,1,sym['..@ls']+1,KIDX,121))
        return c,base
    c,base=add(75,'FORM')
    assert bytes(c[0x30c:0x319])==bytes.fromhex('833e6c39027506c7061e370100'), c[0x30c:0x319].hex()
    c[0x30c]=0xe8; struct.pack_into('<h',c,0x30d,base-0x30f)
    c[0x30f]=0xeb; c[0x310]=0x319-0x311
    for k in range(0x311,0x319): c[k]=0x90
    c,base=add(74,'SYS')
    assert bytes(c[0x403:0x40f])==bytes.fromhex('8b46fe893e0a37a30c372bc0'), c[0x403:0x40f].hex()
    c[0x403]=0xe8; struct.pack_into('<h',c,0x404,base-0x406)
    stats['fshrink']=2

def tabgrow_pass(d,ne,blobs,stats):
    # seg 77:00CA grows a slot table in place (GlobalReAlloc without MOVEABLE). In
    # real mode in-place growth fails whenever the next block is in use. Let it move,
    # return the new segment in DX, and make each caller store it back into the
    # DGROUP variable it pushed (the only holder: callers reload ES from it).
    import capstone
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16)
    nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
    def mname(k):
        o=struct.unpack_from('<H',d,ne+mo+2*k)[0]; return bytes(d[ne+io+o+1:ne+io+o+1+d[ne+io+o]]).upper()
    KIDX=[mname(k) for k in range(nmods)].index(b'KERNEL')+1
    c,rr=blobs[76]
    assert bytes(c[0x104:0x106])==b'\x6a\x40' and bytes(c[0x10b:0x112])==bytes.fromhex('0bc074d1b80100') or True
    assert c[0x104]==0x6a and c[0x105]==0x40, c[0x104:0x106].hex()
    c[0x105]=0x42
    st=len(c)
    stub=bytearray(b'\x0b\xc0\x74\x0b\x50\x9a\xff\xff\x00\x00\xb8\x01\x00\xc3\x90\x33\xc0\x33\xd2\xc3')
    # or ax,ax / jz f / push ax / call far GlobalHandle / mov ax,1 / ret / f: xor ax,ax / xor dx,dx / ret
    stub[3]=0x0f-4
    c+=stub
    rr.append(struct.pack('<BBHHH',3,1,st+6,KIDX,21))
    ins=list(md.disasm(bytes(c[0x10b:0x112]),0x10b))
    assert ins[0].mnemonic=='or' and ins[1].mnemonic=='je' and ins[2].mnemonic=='mov', [(i.mnemonic,i.op_str) for i in ins]
    c[0x10b]=0xe8; struct.pack_into('<h',c,0x10c,st-0x10e); c[0x10e]=0xeb; c[0x10f]=0x02; c[0x110]=0x90; c[0x111]=0x90
    stats['tabgrow77']=1
    for sg,lc in ((50,0x58),(90,0x31b),(97,0x5b)):
        c,rr=blobs[sg-1]
        assert c[lc]==0x9a, (sg,hex(lc),c[lc])
        pil=2 if c[lc-2]==0x6a else 3
        assert pil==2 or c[lc-3]==0x68, (sg,hex(lc))
        pva=lc-pil-4
        assert c[pva]==0xff and c[pva+1]==0x36, (sg,c[pva:lc].hex())
        class _I: pass
        pv=_I(); pv.address=pva; pv.size=4; pi=_I(); pi.address=lc-pil; pi.size=pil
        var=struct.unpack_from('<H',c,pv.address+2)[0]
        after=[i for i in md.disasm(bytes(c[lc+5:lc+9]),lc+5)]
        assert after[0].mnemonic=='or' and after[0].op_str=='ax, ax' and after[1].mnemonic=='je', (sg,after[0].op_str)
        start=pv.address; end=lc+5+after[0].size
        st=len(c)
        body=bytes(c[pv.address:pv.address+pv.size])+bytes(c[pi.address:pi.address+pi.size])+bytes(c[lc:lc+5])+b'\x0b\xc0\x74\x04\x89\x16'+struct.pack('<H',var)+b'\xc3'
        c+=body
        newcall=st+pv.size+pi.size
        for j,r in enumerate(rr):
            t,fl,off,x,y=struct.unpack('<BBHHH',r)
            if off==lc+1: rr[j]=struct.pack('<BBHHH',t,fl,newcall+1,x,y); break
        else: raise AssertionError('no reloc at call %d:%x'%(sg,lc))
        c[start]=0xe8; struct.pack_into('<h',c,start+1,st-(start+3))
        for k in range(start+3,end): c[k]=0x90
        stats['tabgrow_callers']+=1

def wrap_pass(d,ne,blobs,ordn,ords,stats):
    import subprocess,tempfile
    info=json.load(open(WRAPJ[1:] if WRAPJ.startswith('@') else WRAPJ))
    targets={}
    for k,v in info.items():
        sg,off=map(int,k.split(':'))
        nearonly=any(f.startswith('nearret') for f in v['flags']) and not v['rets'] and not any(x[2]=='callf' for x in v['sites'])
        if nearonly: continue                     # push cs is an argument, not a return address
        targets[(sg,off)]=v
    nmods=struct.unpack_from('<H',d,ne+0x1e)[0]; mo=struct.unpack_from('<H',d,ne+0x28)[0]; io=struct.unpack_from('<H',d,ne+0x2a)[0]
    def mname(k):
        o=struct.unpack_from('<H',d,ne+mo+2*k)[0]; return bytes(d[ne+io+o+1:ne+io+o+1+d[ne+io+o]]).upper()
    KIDX=[mname(k) for k in range(nmods)].index(b'KERNEL')+1
    NSEG=len(blobs)
    F=WRAPSEG; code,recs=blobs[F-1]
    while len(code)&1: code.append(0x90)
    base=len(code)
    here=os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(['nasm','-f','bin','-DBASE=%d'%base,'-DNSLOT=96','-DNSEG=%d'%NSEG]+(['-DSTATS'] if os.environ.get('WRAPSTATS') else [])+['--before','[map symbols %s/m]'%td,
                               os.environ.get('VBW_ASM',here+'/asm')+'/wrapcore.asm','-o',td+'/b'])
        core=open(td+'/b','rb').read(); sym={}
        for l in open(td+'/m'):
            pr=l.split()
            if len(pr)==3:
                try: sym[pr[2]]=int(pr[1],16)
                except ValueError: pass
    code+=core
    for nm,o in (('..@lockcall',23),('..@unl1',24),('..@unl2',24),('..@gch',93),('..@gh',21)):
        recs.append(struct.pack('<BBHHH',3,1,sym[nm]+1,KIDX,o))
    xused=set(); wk={}
    def W(t,X):
        if (t,X) not in wk:
            at=len(code)
            code.extend(b'\xe8'+struct.pack('<h',sym['center']-(at+3))+b'\xff\xff\0\0'+struct.pack('<H',X))
            if t[0] in FIX: recs.append(struct.pack('<BBHHH',3,0,at+3,t[0],t[1]))
            else: recs.append(struct.pack('<BBHHH',3,0,at+3,0xff,ordn(*t)))
            wk[(t,X)]=at; stats['wrap_stubs']+=1
            if X: xused.add(X)
        return wk[(t,X)]
    byord={o:k for k,o in ords.items()}
    for si,b in enumerate(blobs):
        if b is None or si+1==F: continue
        c,rr=b
        for j,r in enumerate(rr):
            t,fl,off,a,o=struct.unpack('<BBHHH',r)
            if t==3 and fl==0 and a==0xff and o in byord and byord[o] in targets:
                op=c[off-1] if off>=1 else 0
                if op==0xea: continue                     # tail jump: no return address of ours
                if op==0x9a:
                    if si+1 in FIX: continue             # fixed caller cannot move
                    X=si+1
                else: X=0                                 # far pointer (callback table): caller unknown
                rr[j]=struct.pack('<BBHHH',3,0,off,F,W(byord[o],X)); stats['wrap_far' if X else 'wrap_ptr']+=1
    for (sg,off),v in targets.items():
        for (cs_,p,kind) in v['sites']:
            if kind!='pushcs' or cs_ in FIX: continue
            c,rr=blobs[cs_-1]
            assert c[p-1]==0x0e and c[p]==0xe8, (cs_,p)
            L=len(c); c.extend(b'\xea\xff\xff\0\0')
            rr.append(struct.pack('<BBHHH',3,0,L+1,F,W((sg,off),cs_)))
            struct.pack_into('<h',c,p+1,L-(p+3)); stats['wrap_pushcs']+=1
    for X in sorted(xused):
        struct.pack_into('<HH',code,sym['xthunk']+4*(X-1),0xffff,0)
        recs.append(struct.pack('<BBHHH',3,0,sym['xthunk']+4*(X-1),0xff,ordn(X,0)))
    stats['wrap_xsegs']=len(xused)
    json.dump({'%d'%v:'%d:%d/%d'%(k[0][0],k[0][1],k[1]) for k,v in wk.items()},open(os.environ.get('WRAPMAP',os.devnull),'w'))

if __name__=='__main__': conv(sys.argv[1],sys.argv[2],vb=(len(sys.argv)<4))
