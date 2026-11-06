import sys, struct
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src')); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_tsr3 as bt, w8lib as W, analyze_ne as A, tempfile, os
from unicorn import *
from unicorn.x86_const import *
code, L = bt.build()
specs = [(int(a.split(':',1)[0]), a.split(':',1)[1]) for a in sys.argv[1:]]
files = [open(p, 'rb').read() for _, p in specs]
lib = tempfile.mkdtemp(); imgs = {}
for mi, (d, p) in enumerate(specs):
    fn = W.add(lib, p, d, quiet=True)
    if fn: imgs[mi] = open(lib + '/' + fn, 'rb').read()
libfiles = {f.upper(): open(lib + '/' + f, 'rb').read() for f in os.listdir(lib)}
TS, UC, DSEG, SSEG = 0x1000, 0x9000, 0x6000, 0x5000
mu = Uc(UC_ARCH_X86, UC_MODE_16); mu.mem_map(0, 0x100000)
mu.mem_write(TS*16+0x100, code[:L['arena']-0x100])
def w16(l, v): mu.mem_write(TS*16+L[l], struct.pack('<H', v))
V20 = bool(int(os.environ.get('V20', '0')))   # V20=1: run the installer's /V mode (only type 8 compatibility patches are applied)
mu.mem_write(TS*16+L['v20'], bytes([int(V20)]))
w16('arena_top', L['arena']); w16('arena_end', L['arena'] + int(os.environ.get('ARENA', '12000')))
lp = b'C:\\W8X\\'; mu.mem_write(TS*16+L['lpath'], lp); w16('libend', L['lpath'] + len(lp))
mu.mem_write(TS*16+L['old21'], struct.pack('<HH', 0, UC))
mu.mem_write(TS*16+L['handles'], b'\xff\xff\0\0\0\0\0\0'*12)
state = {'pos': 0, 'file': None}
# "DOS": fake file system by path
def dosfile(path):
    if path.upper()[-4:-1] == '.W8':
        return libfiles.get(path.upper().split('\\')[-1])
    for (d, p), data in zip(specs, files):
        if path.upper().endswith(p.split('/')[-1].upper()): return data
def intr_dos(uc, addr, size, ud):
    ax = uc.reg_read(UC_X86_REG_AX); ah = ax >> 8; al = ax & 255
    bx = uc.reg_read(UC_X86_REG_BX); cx = uc.reg_read(UC_X86_REG_CX); dx = uc.reg_read(UC_X86_REG_DX)
    ds = uc.reg_read(UC_X86_REG_DS); cf = 0
    if ah == 0x3d:
        p = b''; o = 0
        while uc.mem_read(ds*16+dx+o, 1)[0]: o += 1
        p = bytes(uc.mem_read(ds*16+dx, o)).decode()
        f = dosfile(p); state['file'] = f; state['pos'] = 0; uc.reg_write(UC_X86_REG_AX, 5)
        if f is None: cf = 1
    elif ah == 0x42:
        if al == 2: state['pos'] = len(state['file'])
        elif al == 0: state['pos'] = (cx << 16) | dx
        else: state['pos'] += (cx << 16) | dx
        uc.reg_write(UC_X86_REG_AX, state['pos'] & 0xFFFF); uc.reg_write(UC_X86_REG_DX, state['pos'] >> 16)
    elif ah == 0x3f:
        d = state['file'][state['pos']:state['pos'] + cx]; uc.mem_write(ds*16+dx, d); state['pos'] += len(d); uc.reg_write(UC_X86_REG_AX, len(d))
    elif ah == 0x62: uc.reg_write(UC_X86_REG_BX, 0x1234)
    sp = uc.reg_read(UC_X86_REG_SP); ss = uc.reg_read(UC_X86_REG_SS)
    ip, cs, fl = struct.unpack('<HHH', bytes(uc.mem_read(ss*16+sp, 6)))
    uc.reg_write(UC_X86_REG_SP, sp+6); uc.reg_write(UC_X86_REG_CS, cs); uc.reg_write(UC_X86_REG_IP, ip)
    uc.reg_write(UC_X86_REG_EFLAGS, (fl & ~1) | cf | 2)
mu.hook_add(UC_HOOK_CODE, intr_dos, None, UC*16, UC*16)
def call21(regs, ds_data=None):
    # emulate caller: INT 21h from CS=0x3000:0 ; vector 21 -> hook21
    mu.mem_write(0x21*4, struct.pack('<HH', L['hook21'], TS))
    for k, v in regs.items(): mu.reg_write(getattr(__import__('unicorn.x86_const').x86_const, 'UC_X86_REG_'+k), v)
    mu.reg_write(UC_X86_REG_SS, SSEG); mu.reg_write(UC_X86_REG_SP, 0x8000)
    mu.mem_write(0x3000*16, b'\xcd\x21\xf4')
    mu.reg_write(UC_X86_REG_CS, 0x3000); mu.reg_write(UC_X86_REG_DS, regs.get('DS', DSEG)); mu.reg_write(UC_X86_REG_ES, 0x7000)
    def intr(uc, intno, ud):
        ip = uc.reg_read(UC_X86_REG_IP); sp = (uc.reg_read(UC_X86_REG_SP) - 6) & 0xFFFF
        uc.mem_write(SSEG*16+sp, struct.pack('<HHH', ip, uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF))
        uc.reg_write(UC_X86_REG_SP, sp); vo, vs = struct.unpack('<HH', bytes(uc.mem_read(intno*4, 4)))
        uc.reg_write(UC_X86_REG_CS, vs); uc.reg_write(UC_X86_REG_IP, vo)
    if not getattr(call21, 'hooked', False): mu.hook_add(UC_HOOK_INTR, intr); call21.hooked = True
    mu.emu_start(0, 0x3000*16+2, count=200000)
    return mu.reg_read(UC_X86_REG_AX), mu.reg_read(UC_X86_REG_EFLAGS) & 1
for mi, (d, path) in enumerate(specs):
    name = path.split('/')[-1]
    full = ('C:\\WINDOWS\\' + ('SYSTEM\\' if d else '') + name).encode() + b'\0'
    mu.mem_write(DSEG*16+0x100, full)
    ax, cf = call21({'AX': 0x3d00, 'DX': 0x100, 'DS': DSEG})
    print(name, 'open ax', ax, 'cf', cf, 'handles[0]', bytes(mu.mem_read(TS*16+L['handles'], 8)).hex())
    h = ax
    data = files[mi]; ne = A.NE(data)
    # read whole file in 1 KB.. 20 KB chunks like a loader: per segment
    hdr = dict(n='hdr', fo=0, ln=struct.unpack_from('<I', data, 0x3c)[0] + 0x40)   # the NE header read carries the version-stamp / protected-mode flag patches
    for s in [hdr] + list(ne.segs):
        if not s['ln']: continue
        mu.mem_write(0x3000*16+0x2000, b'')  # noop
        call21({'AX': 0x4200, 'BX': h, 'CX': s['fo'] >> 16, 'DX': s['fo'] & 0xFFFF, 'DS': DSEG})
        CH = int(__import__('os').environ.get('CHUNK', '0')) or s['ln']
        done = 0; ax = 0
        while done < s['ln']:
            n = min(CH, s['ln'] - done)
            a, cf = call21({'AX': 0x3f00, 'BX': h, 'CX': n, 'DX': 0x4000 + done, 'DS': DSEG}); done += a; ax = done
            if a == 0: break
        got = bytes(mu.mem_read(DSEG*16+0x4000, ax))
        exp = bytearray(data[s['fo']:s['fo']+s['ln']])
        # expected patches
        img = imgs.get(mi, b'')
        for i in range(struct.unpack_from('<H', img, 4)[0] if img else 0):
            segoff, typ, reg, imm, ln, srcreg, fl, fh, mv = struct.unpack_from('<HBBHBBHBB', img, 66 + 12*i)
            fo = fl | fh << 16
            if not (s['fo'] <= fo < s['fo']+s['ln']): continue
            o = fo - s['fo']
            if V20 and typ != 8: continue
            if typ == 8:
                exp[o] = imm & 255
                if ln != 1: exp[o+1] = imm >> 8
            elif typ in (5, 6): exp[o] = 0xCC
            else: exp[o] = 0xCD; exp[o+1] = 0xF8 + (mv & 7)
        print('  seg', s['n'], 'len', s['ln'], 'read', ax, 'match' if got == bytes(exp) else 'MISMATCH', sum(1 for a, b in zip(got, exp) if a != b))
    call21({'AX': 0x3e00, 'BX': h, 'DS': DSEG})
print('slots', struct.unpack('<6H', bytes(mu.mem_read(TS*16+L['slots'], 12))), 'arena_top', hex(struct.unpack('<H', bytes(mu.mem_read(TS*16+L['arena_top'], 2)))[0]))
