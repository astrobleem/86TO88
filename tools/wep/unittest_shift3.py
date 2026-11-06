#!/usr/bin/env python3
"""Focused differential test of the WM88X3 shift handlers (types 1/2/3, word and byte forms).
Executes a native C0/C1 shift on a 386 core against the same site patched to INT F8h+vec and run through the real
handler code, over every register, every opcode extension and a count sweep that includes masked-zero counts
(0, 32, 64: the analyzer stores imm & 31, so these all arrive as an effective count of 0).
Checks registers, CF/PF/ZF/SF always, OF only for an effective count of 1.  CF is skipped for SHL/SHR when the
effective count >= operand size (undefined per the SDM) and reported separately.
usage: unittest_shift3.py        exit status 1 if any defined behaviour differs"""
import sys, struct, random, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))
import build_tsr3 as bt
from unicorn import *
from unicorn.x86_const import *

code, L = bt.build()
TSR_SEG, CODE_SEG, SS_SEG, DS_SEG = 0x1000, 0x3000, 0x5000, 0x6000
OFF = 0x100
REGS = dict(AX=UC_X86_REG_AX, BX=UC_X86_REG_BX, CX=UC_X86_REG_CX, DX=UC_X86_REG_DX,
            SI=UC_X86_REG_SI, DI=UC_X86_REG_DI, BP=UC_X86_REG_BP, SP=UC_X86_REG_SP)
VEC = 1
EXT = {1: 4, 2: 5, 3: 7}      # site type -> modrm reg field (shl, shr, sar)


def image(typ, reg, imm, ln):
    hdr = bytearray(66)
    hdr[0:4] = b'W8M1'
    struct.pack_into('<HBB', hdr, 4, 1, 0, 0)
    struct.pack_into('<HH', hdr, 8 + 4 * VEC, 0, 1)        # vector VEC: entries [0,1)
    hdr[40] = 4; hdr[41:45] = b'TEST'
    return bytes(hdr) + struct.pack('<HBBHBBHBB', OFF, typ, reg, imm, ln, 0, 0, 0, VEC)


def mkemu(seg, patched, img):
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x100000)
    if patched:
        mu.mem_write(TSR_SEG * 16 + 0x100, code[:L['arena'] - 0x100])
        mu.mem_write(TSR_SEG * 16 + L['arena'], img)
        mu.mem_write(TSR_SEG * 16 + L['slots'], struct.pack('<H', L['arena']))
        for i, st in enumerate(['stub0', 'stub1', 'stub2', 'stub3', 'stub4', 'stub5', 'stub6']):
            mu.mem_write((0xF8 + i) * 4, struct.pack('<HH', L[st], TSR_SEG))
    mu.mem_write(CODE_SEG * 16, seg)

    def intr(uc, intno, ud):
        sp = (uc.reg_read(UC_X86_REG_SP) - 6) & 0xFFFF
        fl = uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF
        uc.mem_write(uc.reg_read(UC_X86_REG_SS) * 16 + sp,
                     struct.pack('<HHH', uc.reg_read(UC_X86_REG_IP), uc.reg_read(UC_X86_REG_CS), fl))
        uc.reg_write(UC_X86_REG_SP, sp)
        voff, vseg = struct.unpack('<HH', bytes(uc.mem_read(intno * 4, 4)))
        uc.reg_write(UC_X86_REG_CS, vseg); uc.reg_write(UC_X86_REG_IP, voff)
        uc.reg_write(UC_X86_REG_EFLAGS, fl & ~0x300)
    mu.hook_add(UC_HOOK_INTR, intr)
    return mu


def run(mu, st, flags, until):
    for k, v in st.items(): mu.reg_write(REGS[k], v)
    mu.reg_write(UC_X86_REG_CS, CODE_SEG); mu.reg_write(UC_X86_REG_SS, SS_SEG)
    mu.reg_write(UC_X86_REG_DS, DS_SEG); mu.reg_write(UC_X86_REG_ES, DS_SEG)
    mu.reg_write(UC_X86_REG_EFLAGS, flags | 2)
    try: mu.emu_start(OFF, CODE_SEG * 16 + until, count=20000)
    except UcError: pass


def main():
    rnd = random.Random(7)
    bad = collections.Counter(); tot = collections.Counter(); undef = collections.Counter(); samples = {}
    COUNTS = [0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 24, 31, 32, 33, 63, 64, 65, 255]
    for typ in (1, 2, 3):
        for byte in (False, True):
            for r in range(8):
                if r == 4 and not byte: continue      # SP: the handler has no slot for it; analyze_ne reports such sites as unsup-sp-reg
                for raw in COUNTS:
                    eff = raw & 31
                    op = 0xC0 if byte else 0xC1
                    modrm = 0xC0 | EXT[typ] << 3 | r
                    nat = bytearray(0x10000)
                    nat[OFF:OFF + 3] = bytes([op, modrm, raw]); nat[OFF + 3] = 0xF4
                    pat = bytearray(nat); pat[OFF] = 0xCD; pat[OFF + 1] = 0xF8 + VEC
                    img = image(typ, r | (8 if byte else 0), eff, 3)
                    for trial in range(24):
                        sp = rnd.choice([0x7000, 0x7FFE, 0x9000])
                        st = {k: rnd.getrandbits(16) for k in REGS}
                        st['SP'] = sp; st['BP'] = sp + rnd.randrange(0, 100) * 2
                        flags = (rnd.getrandbits(16) & 0x0CD5) | 0x200
                        res = []
                        for patched, seg in ((False, bytes(nat)), (True, bytes(pat))):
                            mu = mkemu(seg, patched, img)
                            run(mu, st, flags, OFF + 3)
                            res.append(mu)
                        a, b = res
                        ra = {k: a.reg_read(v) for k, v in REGS.items()}
                        rb = {k: b.reg_read(v) for k, v in REGS.items()}
                        fa = a.reg_read(UC_X86_REG_EFLAGS); fb = b.reg_read(UC_X86_REG_EFLAGS)
                        size = 8 if byte else 16
                        mask = 0x0C4          # PF ZF SF
                        cf_defined = not (typ in (1, 2) and eff >= size)
                        if cf_defined: mask |= 1
                        if eff == 1: mask |= 0x800
                        key = ('shl shr sar'.split()[typ - 1], 'byte' if byte else 'word', 'zero' if eff == 0 else 'nz')
                        tot[key] += 1
                        if ra != rb or (fa & mask) != (fb & mask):
                            bad[key] += 1
                            samples.setdefault(key, (r, raw, hex(flags), hex(fa & mask), hex(fb & mask), ra == rb))
                        elif not cf_defined and (fa & 1) != (fb & 1):
                            undef[key] += 1
    print('cases', sum(tot.values()))
    for k in sorted(tot):
        print('%-26s tot=%4d bad=%4d cf-undefined-diff=%d' % (k, tot[k], bad[k], undef[k]), samples.get(k, ''))
    print('FAIL' if bad else 'OK')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
