"""80186 -> 8088 rewrite (i186.py, asm/i186.asm): each rewritten form against the original
instruction on Unicorn, from random states, plus the INT 3 handler's corner cases.
Run: python3 -m pytest tests/test_i186.py"""
import os, sys, struct, random, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import collections, i186, i186test
from i186test import Machine, rand_state, handler, CS, SS, REGS
from unicorn.x86_const import *

HCODE, HSYM = handler()


def site(code, off, targets=()):
    ins = next(i186.md.disasm(bytes(code[off:off + 16]), off, 1))
    prev = None
    for p in range(max(off - 6, 0), off):
        i = next(i186.md.disasm(bytes(code[p:off]), p, 1), None)
        if i is not None and p + i.size == off and i.mnemonic in i186.SIMPLE: prev = p; break
    return dict(seg=1, off=off, kind=i186.kind(ins), ins=ins, targets=set(targets), ft=False, prev=prev)


def convert(code, offs, recs=()):
    blobs = [(bytearray(code), [struct.pack('<BBHHH', *r) for r in recs])]
    stats = collections.Counter()
    probs = i186.rewrite(None, blobs, [site(code, o) for o in offs], stats)
    return blobs[0][0], [struct.unpack('<BBHHH', r) for r in blobs[0][1]], probs, stats


class Forms(unittest.TestCase):
    def same(self, code, off, size, steps=1, rounds=40, flags_mask=0xffff & ~0x10 & ~0xf000, stop=None, prep=None):
        conv, recs, probs, stats = convert(code, [off])
        self.assertEqual(probs, [])
        rng = random.Random(off * 7 + len(code))
        mo, mc = Machine(code), Machine(conv, HCODE, HSYM)
        for r in range(rounds):
            st = rand_state(rng, 0x8000)
            if prep: prep(st, rng)
            res = []
            for m, cnt in ((mo, steps), (mc, 400)):
                m.state(st); res.append(m.run(off, stop or (CS << 4) + off + size, cnt))
            a, b = res
            self.assertEqual(a['regs'], b['regs'], code[off:off + size].hex())
            self.assertEqual((a['sp'], a['cs'], a['ip']), (b['sp'], b['cs'], b['ip']))
            self.assertEqual(a['fl'] & flags_mask, b['fl'] & flags_mask, code[off:off + size].hex())
            lo = min(a['sp'], b['sp'])
            self.assertEqual(a['stack'][lo:], b['stack'][lo:]); self.assertEqual(a['data'], b['data'])
        return conv, stats

    def test_push_imm16(self):
        for v in (0, 1, 0x7fff, 0x8000, 0xffff, 0x1234):
            code = b'\x90' + b'\x68' + struct.pack('<H', v) + b'\x90'
            conv, st = self.same(code, 1, 3)
            self.assertEqual(conv[1], 0xe8); self.assertEqual(st['i186_push16'], 1)

    def test_push_imm16_shared_per_value(self):
        code = b'\x68\x34\x12\x68\x34\x12\x68\x35\x12'
        conv, recs, probs, st = convert(code, [0, 3, 6])
        t = [o + 3 + struct.unpack_from('<h', conv, o + 1)[0] for o in (0, 3, 6)]
        self.assertEqual(t[0], t[1]); self.assertNotEqual(t[0], t[2])

    def test_push_imm16_relocated(self):
        """push offset/seg with a fixup on the immediate: the fixup moves into the trampoline"""
        code = bytearray(b'\x90\x68\xff\xff\x90\x68\xff\xff\x90')     # two sites in one chain
        struct.pack_into('<H', code, 2, 6)                             # chain 2 -> 6 -> end
        conv, recs, probs, st = convert(bytes(code), [1, 5], recs=[(5, 0, 2, 3, 0x40)])
        self.assertEqual(probs, [])
        sites = sorted(p for r in recs for p in i186.chain(conv, r[2], bool(r[1] & 4)))
        self.assertEqual(len(sites), 2)
        for p in sites: self.assertGreaterEqual(p, len(code))         # both inside trampolines
        for o in (1, 5): self.assertEqual(conv[o], 0xe8)
        self.assertEqual(st['i186_push16_reloc'], 2)

    def test_push_imm8(self):
        for v in (0, 1, 0x7f, 0x80, 0xff, 0x05):
            conv, st = self.same(b'\x90\x6a' + bytes([v]) + b'\x90', 1, 2)
            self.assertEqual(conv[1:3], b'\xcc' + bytes([v]))

    def test_push_imm8_with_direction_flag_set(self):
        def std(st, rng): st['fl'] |= 0x400
        self.same(b'\x6a\x80\x90', 0, 2, prep=std)

    def test_shifts(self):
        for op in (0xc0, 0xc1):
            for r in (4, 5, 7):                          # shl, shr, sar
                for reg in (0, 1, 3, 6, 7):
                    for n in (0, 1, 2, 4, 8, 15, 16, 17, 31, 33):
                        if op == 0xc1 and reg == 4: continue
                        b = bytes([op, 0xc0 | r << 3 | reg, n])
                        mask = 0xffff & ~0x10 & ~0xf000
                        if n & 31 != 1: mask &= ~0x800
                        self.same(b + b'\x90', 0, 3, rounds=6, flags_mask=mask)

    def test_enter(self):
        for n in (2, 8, 0x4c, 0x80, 0x82, 0x400):
            self.same(b'\xc8' + struct.pack('<H', n) + b'\x00\x90', 0, 4)

    def test_leave_retf(self):
        def frame(st, rng):
            stk = bytearray(st['stack']); bp = st['regs'][6]
            struct.pack_into('<HHH', stk, bp, rng.randrange(0x10000), 0x0100, 0x0F00); st['stack'] = bytes(stk)
        for tail in (b'\xca\x04\x00', b'\xca\x0c\x00'):
            conv, st = self.same(b'\xc9' + tail, 0, 4, steps=2, stop=(0x0F00 << 4) + 0x100, prep=frame)
            self.assertEqual(conv[0], 0xe9)

    def test_pop_pop_leave_retf(self):
        def frame(st, rng):
            stk = bytearray(st['stack']); bp = st['regs'][6]
            struct.pack_into('<HHH', stk, bp, rng.randrange(0x10000), 0x0100, 0x0F00); st['stack'] = bytes(stk)
        code = b'\x5e\x5f\xc9\xcb'
        conv, recs, probs, stats = convert(code, [2]); self.assertEqual(probs, [])
        self.assertEqual(conv[1], 0xe9)
        rng = random.Random(3); mo, mc = Machine(code), Machine(conv, HCODE, HSYM)
        for r in range(20):
            st = rand_state(rng, 0x8000); frame(st, rng)
            a = (mo.state(st), mo.run(0, (0x0F00 << 4) + 0x100, 4))[1]
            b = (mc.state(st), mc.run(0, (0x0F00 << 4) + 0x100, 40))[1]
            self.assertEqual((a['regs'], a['sp'], a['cs'], a['ip']), (b['regs'], b['sp'], b['cs'], b['ip']))

    def test_mov_leave_retf(self):
        """mov ax,imm / leave / retf (7:15A8): the MOV moves into the detour"""
        def frame(st, rng):
            stk = bytearray(st['stack']); bp = st['regs'][6]
            struct.pack_into('<HHH', stk, bp, rng.randrange(0x10000), 0x0100, 0x0F00); st['stack'] = bytes(stk)
        code = b'\x90\xb8\x2c\x2d\xc9\xcb'
        conv, recs, probs, stats = convert(code, [4]); self.assertEqual(probs, [])
        self.assertEqual(conv[1], 0xe9)
        rng = random.Random(4); mo, mc = Machine(code), Machine(conv, HCODE, HSYM)
        for r in range(20):
            st = rand_state(rng, 0x8000); frame(st, rng)
            a = (mo.state(st), mo.run(1, (0x0F00 << 4) + 0x100, 3))[1]
            b = (mc.state(st), mc.run(1, (0x0F00 << 4) + 0x100, 40))[1]
            self.assertEqual((a['regs'], a['sp'], a['cs'], a['ip']), (b['regs'], b['sp'], b['cs'], b['ip']))

    def test_leave_retf_target_inside_is_refused(self):
        code = b'\xc9\xca\x04\x00'
        blobs = [(bytearray(code), [])]
        s = site(code, 0, targets={1})
        probs = i186.rewrite(None, blobs, [s], collections.Counter())
        self.assertEqual(len(probs), 1)

    def test_imul(self):
        forms = [b'\x6b\x4e\xd2\x0a', b'\x6b\x1e\x0a\x23\x27', b'\x6b\x06\x0a\x23\x27', b'\x6b\x3e\x0a\x23\x27',
                 b'\x6b\x16\x0a\x23\x85', b'\x69\x06\x0a\x23\x34\x12', b'\x6b\xc0\x21', b'\x6b\xc2\xf0',
                 b'\x6b\xd0\x07', b'\x6b\xda\x07', b'\x6b\xc9\x7f', b'\x26\x6b\x46\x02\x05', b'\x69\xc3\x00\x80']
        for f in forms:
            self.same(f + b'\x90', 0, len(f), flags_mask=0x801)          # CF, OF defined

    def test_relocation_inside_non_push_site_is_refused(self):
        code = b'\xc1\xe0\x04\x90'
        blobs = [(bytearray(code), [struct.pack('<BBHHH', 5, 0, 2, 3, 0)])]
        probs = i186.rewrite(None, blobs, [site(code, 0)], collections.Counter())
        self.assertTrue(probs)


class MergeChains(unittest.TestCase):
    def test_same_target_records_share_one_chain(self):
        code = bytearray(b'\x9a\xff\xff\x00\x00' * 4 + b'\x68\xff\xff')
        recs = [struct.pack('<BBHHH', 3, 0, 5 * k + 1, 0xff, 7) for k in range(4)]      # far ptr, same target
        recs += [struct.pack('<BBHHH', 5, 0, 21, 3, 0x40)]                               # offset, other target
        recs += [struct.pack('<BBHHH', 3, 4, 1, 0xff, 7)]                                # additive: kept apart
        out = [struct.unpack('<BBHHH', r) for r in i186.merge_chains(code, recs)]
        self.assertEqual(len(out), 3)
        far = [r for r in out if r[0] == 3 and not r[1] & 4][0]
        self.assertEqual(sorted(i186.chain(code, far[2], False)), [1, 6, 11, 16])
        self.assertEqual(struct.unpack_from('<H', code, 16)[0], 0xffff)


class Int3(unittest.TestCase):
    def test_foreign_int3_goes_to_previous_handler(self):
        """CD 03 (no CC before the return address) is not a rewritten site: chain"""
        code = b'\xcd\x03\x90\x90'
        m = Machine(code, HCODE, HSYM)
        # previous handler: a stub at 0800:0000 that sets AX=0xBEEF and IRETs
        m.u.mem_write(0x8000, b'\xb8\xef\xbe\xcf')
        m.u.mem_write((0x9000 << 4) + HSYM['old3'], struct.pack('<HH', 0, 0x0800))
        st = rand_state(random.Random(5), 0x8000); m.state(st)
        r = m.run(0, (CS << 4) + 2, 100)
        self.assertEqual(r['regs'][0], 0xbeef); self.assertEqual(r['sp'], 0x8000)

    def test_interrupt_flag_restored(self):
        code = b'\x6a\x05\x90'
        conv, recs, probs, st = convert(code, [0])
        m = Machine(conv, HCODE, HSYM)
        for fl in (0x202, 0x002):
            s = rand_state(random.Random(fl), 0x8000); s['fl'] = fl; m.state(s)
            r = m.run(0, (CS << 4) + 2, 100)
            self.assertEqual(r['fl'] & 0x200, fl & 0x200)


if __name__ == '__main__':
    unittest.main()
