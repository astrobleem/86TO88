#!/usr/bin/env python3
"""Install-time command line test for WM88X3: runs the transient installer under a minimal fake DOS and checks the
CPU probe (Unicorn runs AAD 10h like an Intel 8088; nec=True makes the probe return the NEC V20/V30 result), the /V
and /8 switches, a library path after a switch, and rejection of an unknown option."""
import sys, struct, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))
import build_tsr3 as bt
from unicorn import *
from unicorn.x86_const import *
code, L = bt.build()
SEG = 0x2000


def run(tail, nec=False):
    mu = Uc(UC_ARCH_X86, UC_MODE_16); mu.mem_map(0, 0x100000)
    mu.mem_write(SEG * 16 + 0x100, code)
    t = tail.encode() + b'\r'
    mu.mem_write(SEG * 16 + 0x80, bytes([len(t) - 1]) + t)
    out = {'printed': [], 'exit': None, 'vec': {}}

    def dos(uc, intno, ud):
        if intno != 0x21: return
        ax = uc.reg_read(UC_X86_REG_AX); ah = ax >> 8; ds = uc.reg_read(UC_X86_REG_DS); dx = uc.reg_read(UC_X86_REG_DX)
        if ah == 9:
            m = bytearray(); o = ds * 16 + dx
            while uc.mem_read(o, 1)[0] != 36: m.append(uc.mem_read(o, 1)[0]); o += 1
            out['printed'].append(bytes(m).decode('latin1'))
        elif ah == 0x35:
            uc.reg_write(UC_X86_REG_ES, 0x0900); uc.reg_write(UC_X86_REG_BX, 0x10)
        elif ah == 0x25:
            out['vec'][ax & 255] = dx
        elif ah == 0x4E:
            uc.reg_write(UC_X86_REG_EFLAGS, uc.reg_read(UC_X86_REG_EFLAGS) | 1)     # no library files
        elif ah in (0x31, 0x4C):
            out['exit'] = (ah, ax & 255 if ah == 0x4C else 0); uc.emu_stop()
    mu.hook_add(UC_HOOK_INTR, dos)
    probe = SEG * 16 + L['not_inst'] + 3                     # MOV AX,0100h (3 bytes), then AAD 10h
    assert bytes(mu.mem_read(probe, 2)) == b'\xd5\x10'
    if nec:
        def aad_nec(uc, addr, size, ud):                     # NEC ignores the AAD operand: AL = AH*10 + AL, AH = 0
            if addr == probe:
                uc.reg_write(UC_X86_REG_AX, 10); uc.reg_write(UC_X86_REG_IP, uc.reg_read(UC_X86_REG_IP) + 2)
        mu.hook_add(UC_HOOK_CODE, aad_nec, begin=probe, end=probe)
    for r in (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS): mu.reg_write(r, SEG)
    mu.reg_write(UC_X86_REG_SP, 0xFFFE)
    try: mu.emu_start(0x100, 0, count=200000)
    except UcError as e: out['err'] = str(e)
    out['v20'] = mu.mem_read(SEG * 16 + L['v20'], 1)[0]
    out['lpath'] = bytes(mu.mem_read(SEG * 16 + L['lpath'], 40)).split(b'\0')[0].decode('latin1')
    return out


ok = True
for tail, nec, want_v20, want_exit, want_path in [
        ('', False, 0, (0x31, 0x00), 'C:\\W8X\\'),
        ('', True, 1, (0x31, 0x00), 'C:\\W8X\\'),
        (' /8', True, 0, (0x31, 0x00), 'C:\\W8X\\'),
        (' /8 D:\\LIB', True, 0, (0x31, 0x00), 'D:\\LIB\\'),
        (' /8', False, 0, (0x31, 0x00), 'C:\\W8X\\'),
        (' D:\\LIB', True, 1, (0x31, 0x00), 'D:\\LIB\\'),
        (' /V', False, 1, (0x31, 0x00), 'C:\\W8X\\'),
        (' /v', False, 1, (0x31, 0x00), 'C:\\W8X\\'),
        (' /V D:\\LIB', False, 1, (0x31, 0x00), 'D:\\LIB\\'),
        (' D:\\LIB', False, 0, (0x31, 0x00), 'D:\\LIB\\'),
        (' /X', False, 0, (0x4C, 2), None)]:
    r = run(tail, nec)
    good = r['v20'] == want_v20 and r['exit'] == want_exit and (want_path is None or r['lpath'] == want_path)
    ok &= good
    print('%-4s nec=%d tail=%-12r v20=%d exit=%s lpath=%r err=%s' % ('ok' if good else 'FAIL', nec, tail, r['v20'], r['exit'], r['lpath'], r.get('err')))
print('OK' if ok else 'FAIL')
sys.exit(0 if ok else 1)
