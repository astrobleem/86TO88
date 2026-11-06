#!/usr/bin/env python3
"""Differential test: execute every profile site (patched, via the WM88X handlers) against the native instruction on a 386 core."""
import sys, struct, random, pathlib
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src')); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_tsr3 as bt, w8lib as W, analyze_ne as A, tempfile
from unicorn import *
from unicorn.x86_const import *
code, L = bt.build()
specs = [(int(a.split(':',1)[0]), a.split(':',1)[1]) for a in sys.argv[1:]]
lib = tempfile.mkdtemp()
files = [open(p, 'rb').read() for _, p in specs]
images = []   # (spec index, image bytes)
for mi, (d, p) in enumerate(specs):
    fn = W.add(lib, p, d, quiet=True)
    if fn: images.append((mi, open(lib + '/' + fn, 'rb').read()))
TSR_SEG, CODE_SEG, SS_SEG, DS_SEG, ES_SEG = 0x1000, 0x3000, 0x5000, 0x6000, 0x7000
def mkemu(codebytes, patched):
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x100000)
    mu.mem_write(0, bytes(0x400))
    if patched:
        mu.mem_write(TSR_SEG * 16 + 0x100, code[:L['arena'] - 0x100])
        top = L['arena']
        for k, (mi_, img) in enumerate(images):
            mu.mem_write(TSR_SEG * 16 + top, img); mu.mem_write(TSR_SEG * 16 + L['slots'] + 2 * k, struct.pack('<H', top)); top += len(img)
        for i, st in enumerate(['stub0','stub1','stub2','stub3','stub4','stub5','stub6']):
            mu.mem_write((0xF8 + i) * 4, struct.pack('<HH', L[st], TSR_SEG))
        mu.mem_write(3 * 4, struct.pack('<HH', L['int3h'], TSR_SEG))
        mu.mem_write(TSR_SEG * 16 + L['old3'], struct.pack('<HH', 0x10, 0x9000))  # chain target (should not be hit)
    mu.mem_write(CODE_SEG * 16, codebytes)
    def intr(uc, intno, ud):
        ip = uc.reg_read(UC_X86_REG_IP); sp = uc.reg_read(UC_X86_REG_SP); ss = uc.reg_read(UC_X86_REG_SS)
        fl = uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF; cs = uc.reg_read(UC_X86_REG_CS)
        # IP as seen by hook: points after INT instruction in unicorn? normalise via ud
        base = ss * 16
        sp = (sp - 6) & 0xFFFF
        uc.mem_write(base + sp, struct.pack('<HHH', ud['ret'](uc, intno), cs, fl))
        uc.reg_write(UC_X86_REG_SP, sp)
        voff, vseg = struct.unpack('<HH', bytes(uc.mem_read(intno * 4, 4)))
        uc.reg_write(UC_X86_REG_CS, vseg); uc.reg_write(UC_X86_REG_IP, voff)
        uc.reg_write(UC_X86_REG_EFLAGS, fl & ~0x300)
    def ret(uc, intno):
        ip = uc.reg_read(UC_X86_REG_IP)
        return ip   # to be validated
    mu.hook_add(UC_HOOK_INTR, intr, {'ret': ret})
    return mu
REGS = dict(AX=UC_X86_REG_AX, BX=UC_X86_REG_BX, CX=UC_X86_REG_CX, DX=UC_X86_REG_DX, SI=UC_X86_REG_SI, DI=UC_X86_REG_DI, BP=UC_X86_REG_BP, SP=UC_X86_REG_SP)
def run(mu, ip, st, flags, until=0):
    for k, v in st.items(): mu.reg_write(REGS[k], v)
    mu.reg_write(UC_X86_REG_CS, CODE_SEG); mu.reg_write(UC_X86_REG_SS, SS_SEG); mu.reg_write(UC_X86_REG_DS, DS_SEG); mu.reg_write(UC_X86_REG_ES, ES_SEG)
    mu.reg_write(UC_X86_REG_EFLAGS, flags | 2)
    try: mu.emu_start(ip, CODE_SEG * 16 + until, count=20000)  # stops at HLT via exception
    except UcError as e: pass
res = collections = None
import collections
fails = collections.Counter(); total = collections.Counter(); samples = []
random.seed(1)
entries = []
for mi_, img in images:
    n = struct.unpack_from('<H', img, 4)[0]
    for i in range(n):
        segoff, typ, reg, imm, ln, srcreg, fl, fh, mv = struct.unpack_from('<HBBHBBHBB', img, 66 + 12 * i)
        entries.append(dict(segoff=segoff, type=typ, reg=reg, imm=imm, len=ln, srcreg=srcreg, foff=fl | fh << 16, mod=mi_, vec=mv & 15))
for e in entries:
    if e['type'] == 8: continue
    data = files[e['mod']]
    # reconstruct segment image: find the segment whose file range contains foff
    ne = A.NE(data); seg = None
    for s in ne.segs:
        if s['fo'] <= e['foff'] < s['fo'] + s['ln'] and e['foff'] - s['fo'] == e['segoff']: seg = s
    sd = bytearray(ne.segdata(seg['n'])); sd = sd + bytes(0x10000 - len(sd))
    off = e['segoff']; ln = e['len'] & 15
    orig = bytes(sd[off:off + ln])
    # trailing HLT
    nat = bytearray(sd)
    pat = bytearray(sd)
    # patch every site of this segment, as the TSR does at load (INT 3 context bytes see neighbours' patches)
    for o2 in entries:
        if o2['mod'] != e['mod'] or not (seg['fo'] <= o2['foff'] < seg['fo'] + seg['ln']): continue
        so = o2['foff'] - seg['fo']
        if o2['type'] in (5, 6): pat[so] = 0xCC
        else: pat[so] = 0xCD; pat[so + 1] = 0xF8 + o2['vec']
    # cc-push: native needs the pushed word at +1..+2: use the real bytes (relocation unresolved in file); fine, same bytes both
    # In a real load the loader writes resolved word; here both sides see identical bytes.
    for trial in range(10):
        sp = random.choice([0x7000, 0x7FFE, 0x8000, 0x9000]) & ~1
        st = {k: random.getrandbits(16) for k in REGS}
        st['SP'] = sp
        st['BP'] = random.choice([sp + random.randrange(0, 200) * 2, random.getrandbits(16)])
        if e['type'] == 6: st['BP'] = sp + random.randrange(0, 40) * 2 + 2
        flags = random.getrandbits(16) & 0x0CD5 | 0x200
        mus = []
        for patched, img in ((False, nat), (True, pat)):
            mu = mkemu(bytes(img), patched)
            rnd = random.Random(trial * 977 + off)
            mu.mem_write(DS_SEG * 16, bytes(rnd.getrandbits(8) for _ in range(0x10000)))
            mu.mem_write(SS_SEG * 16, bytes(rnd.getrandbits(8) for _ in range(0x10000)))
            run(mu, off, st, flags, off + ln)
            mus.append(mu)
        a, b = mus
        ra = {k: a.reg_read(v) for k, v in REGS.items()}; rb = {k: b.reg_read(v) for k, v in REGS.items()}
        fa = a.reg_read(UC_X86_REG_EFLAGS); fb = b.reg_read(UC_X86_REG_EFLAGS)
        if e['type'] in (1, 2, 3):
            mask = 0x0C5 if (e['imm'] & 31) != 1 else 0x8C5   # CF PF ZF SF (+OF when count==1)
            if (e['imm'] & 31) == 0: mask = 0x8C5
        elif e['type'] in (4, 7, 9): mask = 0x801
        else: mask = 0x8D5
        # stack contents compare around SP
        sa = a.mem_read(SS_SEG * 16 + ra['SP'], 16)
        sb = b.mem_read(SS_SEG * 16 + rb['SP'], 16)
        ok = ra == rb and (fa & mask) == (fb & mask) and (e['type'] in (1, 2, 3, 4, 7, 9) or bytes(sa) == bytes(sb) or e['type'] == 6)
        # for LEAVE the stack garbage below the new SP differs (handler frame) - registers decide
        total[e['type']] += 1
        if not ok:
            fails[e['type']] += 1
            if len(samples) < 1: samples.append((e, ra, rb, hex(fa & mask), hex(fb & mask)))
print('errcnt', struct.unpack('<H', bytes(b.mem_read(TSR_SEG*16+L['errcnt'],2)))[0], 'vecidx', b.mem_read(TSR_SEG*16+L['vecidx'],1)[0], 'site_off', struct.unpack('<H', bytes(b.mem_read(TSR_SEG*16+L['site_off'],2)))[0], 'ip',hex(b.reg_read(UC_X86_REG_IP)))
print('total', dict(total)); print('FAIL', dict(fails))
for s in samples: print(s)
