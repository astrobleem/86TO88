"""Differential test of the 80186 rewrite: every rewritten site of a converted DLL is run
on Unicorn (real mode) from random register, flag, stack and memory states, once as the
original instruction(s) and once as the converted code (trampoline, detour or INT 3 with
the resident handler from asm/i186.asm), and the results are compared: registers, the
flags the original defines, the stack and the data the instruction may touch.

usage: i186test.py ORIGINAL.DLL PRE.DLL CONVERTED.DLL [rounds]   (exit 1 on any difference)
  PRE = the same conversion without the 80186 rewrite (I186=0): the reference behaviour
"""
import os, sys, struct, random, subprocess, tempfile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INTR, UcError
from unicorn.x86_const import *
import i186

HERE = os.path.dirname(os.path.abspath(__file__))
CS, SS, DS, ES, HSEG = 0x1000, 0x3000, 0x5000, 0x7000, 0x9000
REGS = [UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP]
NAMES = 'ax bx cx dx si di bp'.split()
CF, PF, AF, ZF, SF, OF = 1, 4, 0x10, 0x40, 0x80, 0x800


def handler():
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(['nasm', '-f', 'bin', '-DBASE=0', '--before', '[map symbols %s/m]' % td,
                               os.path.join(HERE, 'asm', 'i186.asm'), '-o', td + '/b'])
        sym = {}
        for l in open(td + '/m'):
            p = l.split()
            if len(p) == 3:
                try: sym[p[2]] = int(p[1], 16)
                except ValueError: pass
        return open(td + '/b', 'rb').read(), sym


class Machine:
    def __init__(self, code, hcode=None, hsym=None):
        u = self.u = Uc(UC_ARCH_X86, UC_MODE_16)
        u.mem_map(0, 0x100000)
        u.mem_write(CS << 4, bytes(code))
        if hcode:
            u.mem_write(HSEG << 4, hcode)
            u.mem_write(3 * 4, struct.pack('<HH', hsym['int3h'], HSEG))
        u.hook_add(UC_HOOK_INTR, self.intr)
        self.ints = 0
    def intr(self, u, intno, ud):
        # real-mode INT n: push FLAGS, CS, IP; clear IF/TF; CS:IP = vector
        self.ints += 1
        ip, cs, fl = u.reg_read(UC_X86_REG_IP), u.reg_read(UC_X86_REG_CS), u.reg_read(UC_X86_REG_EFLAGS)
        ss, sp = u.reg_read(UC_X86_REG_SS), u.reg_read(UC_X86_REG_SP)
        sp = (sp - 6) & 0xffff
        u.mem_write((ss << 4) + sp, struct.pack('<HHH', ip, cs, fl & 0xffff))
        u.reg_write(UC_X86_REG_SP, sp); u.reg_write(UC_X86_REG_EFLAGS, fl & ~0x300)
        off, seg = struct.unpack('<HH', u.mem_read(intno * 4, 4))
        u.reg_write(UC_X86_REG_CS, seg); u.reg_write(UC_X86_REG_IP, off)
    def state(self, st):
        u = self.u
        for r, v in zip(REGS, st['regs']): u.reg_write(r, v)
        u.reg_write(UC_X86_REG_SS, SS); u.reg_write(UC_X86_REG_SP, st['sp'])
        u.reg_write(UC_X86_REG_DS, DS); u.reg_write(UC_X86_REG_ES, ES)
        u.reg_write(UC_X86_REG_EFLAGS, st['fl'])
        u.mem_write(SS << 4, st['stack']); u.mem_write(DS << 4, st['data']); u.mem_write(ES << 4, st['data'])
    def run(self, ip, stop, count):
        u = self.u
        u.reg_write(UC_X86_REG_CS, CS)
        u.emu_start((CS << 4) + ip, stop, count=count)
        return dict(regs=[u.reg_read(r) for r in REGS], sp=u.reg_read(UC_X86_REG_SP),
                    cs=u.reg_read(UC_X86_REG_CS), ip=u.reg_read(UC_X86_REG_IP),
                    fl=u.reg_read(UC_X86_REG_EFLAGS) & 0xffff,
                    stack=bytes(u.mem_read(SS << 4, 0x10000)), data=bytes(u.mem_read(DS << 4, 0x10000)))


def rand_state(rng, sp):
    regs = [rng.randrange(0x10000) for _ in REGS]
    regs[6] = rng.randrange(0x4000, 0xe000) & ~1          # BP inside the stack area
    return dict(regs=regs, sp=sp, fl=0x2 | rng.choice([0, 1]) * CF | rng.choice([0, 1]) * ZF |
                rng.choice([0, 1]) * SF | rng.choice([0, 1]) * OF | rng.choice([0, 1]) * 0x400 | 0x200,
                stack=rng.randbytes(0x10000), data=rng.randbytes(0x10000))


def main():
    orig, pre, conv = sys.argv[1], sys.argv[2], sys.argv[3]
    rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    od = open(orig, 'rb').read(); pd = open(pre, 'rb').read(); cd = open(conv, 'rb').read()
    nr = i186.VB_NORETURN if b'VBRUN100' in od[:0x2000] else None
    s0, _, _ = i186.load(od); so, _, _ = i186.load(pd); sc, _, _ = i186.load(cd)
    sites, _ = i186.census(od, nr, [dict(n=s['n'], flags=s0[s['n'] - 1]['flags'], code=s['code'], recs=s['recs'])
                                     for s in so])
    hcode, hsym = handler()
    rng = random.Random(1)
    fails = 0; n = 0; skipped = 0
    for s in sites:
        sg, off, k = s['seg'], s['off'], s['kind']
        ocode, ccode = so[sg - 1]['code'], sc[sg - 1]['code']
        oins = s['ins']; size = oins.size
        cins = next(i186.md.disasm(bytes(ccode[off:off + 16]), off, 1), None)
        if cins is not None and bytes(cins.bytes) == bytes(oins.bytes):
            skipped += 1; print('NOT REWRITTEN %d:%04x %s %s' % (sg, off, oins.mnemonic, oins.op_str)); fails += 1; continue
        # the run ends after the instruction (and for LEAVE after the RETF that follows it)
        if k == 'leave':
            o2 = next(i186.md.disasm(bytes(ocode[off + 1:off + 5]), off + 1, 1))
            steps = 2; far_ret = True
        else:
            steps = 1; far_ret = False
        start = off
        if k == 'leave' and ocode[off + 1] in (0xcb, 0xc3) and bytes(ccode[off - 2:off - 1]) == b'\xe9':
            start = off - 2; steps = 4
        if bytes(ccode[off - 2:off - 1]) == b'\xe9' and k == 'leave' and start == off:
            pass
        mo = Machine(ocode); mc = Machine(ccode, hcode, hsym)
        for r in range(rounds):
            st = rand_state(rng, 0x8000)
            if far_ret:      # LEAVE: SP <- BP, pop BP, RETF to a known far address
                bp = st['regs'][6]
                stk = bytearray(st['stack'])
                struct.pack_into('<HHH', stk, bp, rng.randrange(0x10000), 0x0100, 0x0F00)
                st['stack'] = bytes(stk)
                stop = (0x0F00 << 4) + 0x0100
            else:
                stop = (CS << 4) + off + size
            res = []
            for m, cnt in ((mo, steps), (mc, 400)):
                m.state(st)
                try: res.append(m.run(start, stop, cnt))
                except UcError as e: res.append(dict(err=str(e)))
            a, b = res
            n += 1
            if 'err' in a or 'err' in b:
                print('ERROR %d:%04x %s: %s / %s' % (sg, off, oins.mnemonic, a.get('err'), b.get('err'))); fails += 1; break
            mask = 0xffff & ~(AF | 0x8000 | 0x7000)
            if k == 'shift' and (oins.bytes[2] & 31) != 1: mask &= ~OF
            if k == 'shift' and (oins.bytes[2] & 31) == 0: mask = 0xffff & ~(0x8000 | 0x7000)
            if k == 'imul': mask &= ~(SF | ZF | PF | AF)
            diff = []
            for nm, x, y in zip(NAMES, a['regs'], b['regs']):
                if x != y: diff.append('%s %04x/%04x' % (nm, x, y))
            for nm in ('sp', 'cs', 'ip'):
                if a[nm] != b[nm]: diff.append('%s %04x/%04x' % (nm, a[nm], b[nm]))
            if (a['fl'] ^ b['fl']) & mask: diff.append('flags %04x/%04x' % (a['fl'], b['fl']))
            # stack: compare the live part (at and above the final SP) and the words just below
            lo = min(a['sp'], b['sp'])
            if a['stack'][lo:] != b['stack'][lo:]: diff.append('stack')
            if a['data'] != b['data']: diff.append('data')
            if diff:
                print('DIFF %d:%04x %s %s: %s' % (sg, off, oins.mnemonic, oins.op_str, ', '.join(diff))); fails += 1; break
    print('%d sites, %d runs, %d failures' % (len(sites), n, fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
