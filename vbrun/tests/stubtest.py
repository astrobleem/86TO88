"""Regression tests for the converter's 16-bit stubs (asm/*.asm), run on Unicorn in real mode
with the KERNEL calls replaced by Python fakes. Run: python3 tests/stubtest.py [-v]

Covers:
  grow2    - in-place grow, moved GMEM_FIXED block (new handle from GlobalReAlloc), failure
  wrapcore - plain return, caller segment moved, caller segment discarded and reloaded,
             nested wrapped calls across segments, Throw followed by a call that reuses the
             same SS:SP, Throw out of a nested call, unknown caller (lock/unlock balance),
             a wrapped callee jumping into another W stub (dispatcher tables)
  growkeep - grow requests that fit the block keep it (no GlobalReAlloc), others realloc
  fshrink  - FORM and SYS hooks shrink the heap of the object just built, for consecutive
             objects, and leave the previous container alone
"""
import os, sys, struct, subprocess, tempfile, unittest
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn.x86_const import *

HERE = os.path.dirname(os.path.abspath(__file__))
ASM = os.environ.get('STUBTEST_ASM') or os.path.join(HERE, '..', 'asm')
KSEG = 0xF000                       # fake KERNEL entry points live here

def nasm(src, defs, text=False):
    with tempfile.TemporaryDirectory() as td:
        if text:
            p = os.path.join(td, 's.asm'); open(p, 'w').write(src); src = p
        cmd = ['nasm', '-f', 'bin', '--before', '[map symbols %s/m]' % td, src, '-o', td + '/b']
        cmd += ['-D%s=%s' % kv if kv[1] is not None else '-D%s' % kv[0] for kv in defs.items()]
        subprocess.check_call(cmd)
        sym = {}
        for l in open(td + '/m'):
            p = l.split()
            if len(p) == 3:
                try: sym[p[2]] = int(p[1], 16)
                except ValueError: pass
        return open(td + '/b', 'rb').read(), sym

class M:
    """Real-mode machine with fake far functions."""
    def __init__(self):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 0x100000)
        self.fakes = {}; self.calls = []; self.nk = 0
        self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=KSEG << 4, end=(KSEG << 4) + 0xFFFF)
    def w(self, seg, off, data): self.uc.mem_write((seg << 4) + off, bytes(data))
    def r(self, seg, off, n): return bytes(self.uc.mem_read((seg << 4) + off, n))
    def ww(self, seg, off, v): self.w(seg, off, struct.pack('<H', v & 0xFFFF))
    def rw(self, seg, off): return struct.unpack('<H', self.r(seg, off, 2))[0]
    def reg(self, r, v=None):
        if v is None: return self.uc.reg_read(r)
        self.uc.reg_write(r, v)
    def fake(self, name, nargs, fn):
        """far pascal function taking nargs words; fn(args list, first = last pushed) -> (ax, dx)"""
        off = self.nk * 8; self.nk += 1
        self.w(KSEG, off, b'\xca' + struct.pack('<H', 2 * nargs) if nargs else b'\xcb')
        self.fakes[(KSEG << 4) + off] = (name, nargs, fn)
        return off
    def _hook(self, uc, addr, size, ud):
        if addr not in self.fakes: return
        name, n, fn = self.fakes[addr]
        ss, sp = self.reg(UC_X86_REG_SS), self.reg(UC_X86_REG_SP)
        args = [self.rw(ss, sp + 4 + 2 * k) for k in range(n)]
        self.calls.append((name, args))
        ax, dx = fn(args)
        if ax is not None: self.reg(UC_X86_REG_AX, ax)
        if dx is not None: self.reg(UC_X86_REG_DX, dx)
    def link(self, seg, sym, base, name, off):
        """point the 'call 0:0xffff' at ..@name to fake KERNEL entry off"""
        a = sym['..@' + name] - 0 + 1
        self.w(seg, a, struct.pack('<HH', off, KSEG))
    def run(self, cs, ip, until_cs, until_ip, count=200000):
        self.reg(UC_X86_REG_CS, cs)
        self.uc.emu_start((cs << 4) + ip, (until_cs << 4) + until_ip, count=count)
        return (self.reg(UC_X86_REG_CS), self.reg(UC_X86_REG_IP))
    def stack(self, ss, sp):
        self.reg(UC_X86_REG_SS, ss); self.reg(UC_X86_REG_SP, sp)

# --------------------------------------------------------------------------- grow2
GSEG, GBASE, GROW = 0x6000, 0x200, 0x8a
class Grow2(unittest.TestCase):
    def setup(self, inplace_size, move_to):
        m = M(); code, sym = nasm(os.path.join(ASM, 'grow2.asm'), {'BASE': GBASE, 'GROW': GROW})
        m.w(GSEG, GBASE, code)
        m.w(GSEG, GROW, b'\xca\x06\x00')                    # retf 6, AX set by hook below
        st = {'blocks': {0x5237: 0x300}, 'gra': []}
        def grow_hook(uc, a, s, u):
            m.reg(UC_X86_REG_AX, inplace_size)
        m.uc.hook_add(UC_HOOK_CODE, grow_hook, begin=(GSEG << 4) + GROW, end=(GSEG << 4) + GROW)
        def gh(a):                                          # fixed block: handle == segment
            h = a[0]
            return (h, h) if h in st['blocks'] else (0, 0)
        def gra(a):
            flags, lo, hi, h = a
            st['gra'].append((h, lo, flags))
            if move_to is None: return (0, None)
            del st['blocks'][h]; st['blocks'][move_to] = lo
            return (move_to, None)                          # new handle = new segment
        def gs(a):
            n = st['blocks'].get(a[0], 0); return (n & 0xFFFF, n >> 16)
        for nm, n, f in (('gh1', 1, gh), ('gh2', 1, gh), ('gra', 4, gra), ('gs', 1, gs)):
            m.link(GSEG, sym, GBASE, nm, m.fake(nm, n, f))
        # caller: push seg,size,flags (pascal) ; call far grow2 ; (stop)
        m.w(0x3000, 0, b'\x68' + struct.pack('<H', 0x5237) + b'\x68' + struct.pack('<H', 0x3b0) +
            b'\x68' + struct.pack('<H', 0x40) + b'\x9a' + struct.pack('<HH', GBASE, GSEG) + b'\x90')
        m.stack(0x1000, 0xF000); m.reg(UC_X86_REG_BP, 0xF100)
        m.run(0x3000, 0, 0x3000, 14)
        return m, st
    def test_inplace(self):
        m, st = self.setup(0x3b0, None)
        self.assertEqual(m.reg(UC_X86_REG_DX), 0x5237); self.assertEqual(m.reg(UC_X86_REG_AX), 0x3b0)
        self.assertEqual(st['gra'], [])
    def test_moved_fixed_block_uses_returned_handle(self):
        m, st = self.setup(0x300, 0x5371)
        self.assertEqual(st['gra'], [(0x5237, 0x3b0, 0x42)])
        self.assertEqual(m.reg(UC_X86_REG_DX), 0x5371, 'new segment must come from the handle GlobalReAlloc returned')
        self.assertEqual(m.reg(UC_X86_REG_AX), 0x3b0)
        self.assertEqual(m.reg(UC_X86_REG_SP), 0xF000, 'retf 6 balance')
    def test_realloc_fails(self):
        m, st = self.setup(0x300, None)
        self.assertEqual(m.reg(UC_X86_REG_AX), 0); self.assertEqual(m.reg(UC_X86_REG_DX), 0x5237)

# --------------------------------------------------------------------------- growkeep
class GrowKeep(unittest.TestCase):
    def run_keep(self, blocksize, req):
        m = M(); code, sym = nasm(os.path.join(ASM, 'growkeep.asm'), {'BASE': 0x200})
        m.w(GSEG, 0x200, code)
        gra = []
        m.link(GSEG, sym, 0x200, 'gs', m.fake('gs', 1, lambda a: (blocksize & 0xFFFF, blocksize >> 16)))
        m.link(GSEG, sym, 0x200, 'gra', m.fake('gra', 4, lambda a: (gra.append(a) or 0x5555, None)))
        # in seg 105: push h, 0, size, flags ; call near keep ; nop nop ; (stop)
        m.w(GSEG, 0x100, b'\x68\x47\x18\x6a\x00\x68' + struct.pack('<H', req) + b'\x6a\x40' +
            b'\xe8' + struct.pack('<h', 0x200 - 0x10d) + b'\x90\x90\x90')
        m.stack(0x1000, 0xF000)
        m.run(GSEG, 0x100, GSEG, 0x110)
        self.assertEqual(m.reg(UC_X86_REG_SP), 0xF000)
        return m.reg(UC_X86_REG_AX), gra
    def test_fits_keeps_block(self):
        self.assertEqual(self.run_keep(0x1000, 0x2be), (0x1847, []))
    def test_shrink_request_keeps_block(self):
        self.assertEqual(self.run_keep(0x1000, 0xbc), (0x1847, []))
    def test_larger_calls_globalrealloc(self):
        self.assertEqual(self.run_keep(0x100, 0x2be), (0x5555, [[0x40, 0x2be, 0, 0x1847]]))

# --------------------------------------------------------------------------- wrapcore
WSEG, WBASE = 0x2000, 0x100
CSEG, CSEG2, ESEG, ESEG2 = 0x3000, 0x5000, 0x4000, 0x4800   # caller, caller moved, callees
class Wrap(unittest.TestCase):
    def setUp(self):
        m = self.m = M()
        code, self.sym = nasm(os.path.join(ASM, 'wrapcore.asm'), {'BASE': WBASE, 'NSLOT': 8, 'NSEG': 4})
        m.w(WSEG, WBASE, code)
        self.where = {1: CSEG, 2: ESEG}                     # segment number -> current segment
        self.locks = {}
        def gch(a):                                         # GetCodeHandle(lpfn): seg number by thunk
            return (a[1], None)                             # thunk segment field = handle id
        def gh(a): return (a[0], self.where[a[0]])
        def lock(a): self.locks[a[0]] = self.locks.get(a[0], 0) + 1; return (a[0], None)
        def unl(a): self.locks[a[0]] = self.locks.get(a[0], 0) - 1; return (a[0], None)
        for nm, n, f in (('gch', 2, gch), ('gh', 1, gh), ('lockcall', 1, lock), ('unl1', 1, unl), ('unl2', 1, unl)):
            m.link(WSEG, self.sym, WBASE, nm, m.fake(nm, n, f))
        xt = self.sym['xthunk']
        for X in (1, 2): m.w(WSEG, xt + 4 * (X - 1), struct.pack('<HH', 0, X))
        self.stubs = {}; self.nxt = WBASE + len(code)
    def stub(self, tseg, toff, X):
        a = self.nxt; c = self.sym['center']
        self.m.w(WSEG, a, b'\xe8' + struct.pack('<h', c - (a + 3)) + struct.pack('<HHH', toff, tseg, X))
        self.nxt += 9; return a
    def caller(self, seg, code): self.m.w(seg, 0, code)
    def wtop(self): return self.m.rw(WSEG, self.sym['wtop']) - self.sym['wstk']
    @staticmethod
    def callw(off, arg=None):
        return (b'\x68' + struct.pack('<H', arg) if arg is not None else b'') + b'\x9a' + struct.pack('<HH', off, WSEG)

    def test_plain_return(self):
        w = self.stub(ESEG, 0, 1)
        self.m.w(ESEG, 0, b'\xca\x02\x00')                 # retf 2
        self.caller(CSEG, self.callw(w, 0x1234) + b'\x90\x90')
        self.m.stack(0x1000, 0xF000)
        self.assertEqual(self.m.run(CSEG, 0, CSEG, 8), (CSEG, 8))
        self.assertEqual(self.m.reg(UC_X86_REG_SP), 0xF000); self.assertEqual(self.wtop(), 0)

    def test_caller_moved(self):
        w = self.stub(ESEG, 0, 1)
        self.m.w(ESEG, 0, b'\xca\x02\x00')
        code = self.callw(w, 1) + b'\x90\x90'
        self.caller(CSEG, code); self.caller(CSEG2, code)
        self.where[1] = CSEG2                               # moved while the callee ran
        self.m.stack(0x1000, 0xF000)
        self.assertEqual(self.m.run(CSEG, 0, CSEG2, 8), (CSEG2, 8))
        self.assertEqual(self.wtop(), 0)

    def test_caller_discarded_and_reloaded(self):
        """deliberate discard: the callee wipes the caller's code; GetCodeHandle reloads it elsewhere"""
        w = self.stub(ESEG, 0, 1)
        code = self.callw(w, 1) + b'\x90\x90'
        self.caller(CSEG, code)
        m = self.m
        m.w(ESEG, 0, b'\xca\x02\x00')
        def discard(uc, a, s, u):                           # at callee entry: discard segment 1
            m.w(CSEG, 0, b'\xcc' * 16); self.where[1] = None
        m.uc.hook_add(UC_HOOK_CODE, discard, begin=ESEG << 4, end=ESEG << 4)
        reloads = []
        def gh(a):
            if a[0] == 1 and self.where[1] is None:         # "segment not present": load it again
                m.w(CSEG2, 0, code); self.where[1] = CSEG2; reloads.append(1)
            return (a[0], self.where[a[0]])
        m.fakes[[k for k, v in m.fakes.items() if v[0] == 'gh'][0]] = ('gh', 1, gh)
        m.stack(0x1000, 0xF000)
        self.assertEqual(m.run(CSEG, 0, CSEG2, 8), (CSEG2, 8)); self.assertEqual(reloads, [1])

    def test_nested(self):
        """caller(seg1) -> W -> callee(seg2) -> W -> inner; both segments move during inner"""
        w_inner = self.stub(ESEG2, 0, 2); w_outer = self.stub(ESEG, 0, 1)
        m = self.m
        m.w(ESEG2, 0, b'\xcb')                                                     # inner: retf
        outer = self.callw(w_inner) + b'\xca\x02\x00'                               # outer: call inner; retf 2
        m.w(ESEG, 0, outer); m.w(0x4400, 0, outer)
        code = self.callw(w_outer, 7) + b'\x90\x90'
        self.caller(CSEG, code); self.caller(CSEG2, code)
        depth = []
        def mv(uc, a, s, u):
            depth.append(self.wtop() // 8)
            self.where[1] = CSEG2; self.where[2] = 0x4400                             # both moved
        m.uc.hook_add(UC_HOOK_CODE, mv, begin=ESEG2 << 4, end=ESEG2 << 4)
        m.stack(0x1000, 0xF000)
        self.assertEqual(m.run(CSEG, 0, CSEG2, 8), (CSEG2, 8))
        self.assertEqual(depth, [2]); self.assertEqual(self.wtop(), 0)
        self.assertEqual(m.reg(UC_X86_REG_SP), 0xF000)

    def throw_then_reuse(self, nested):
        """call A is abandoned by a Throw back to the caller's frame; the caller then calls B
        from the same SS:SP. B's return must go to B's return address, and A's record must go."""
        m = self.m
        wa = self.stub(ESEG, 0, 1); wb = self.stub(ESEG, 0x10, 1)
        if nested:                                          # A calls further in before throwing
            wi = self.stub(ESEG2, 0, 2); m.w(ESEG, 0, self.callw(wi))
            throw_at = (ESEG2, 0)
        else:
            throw_at = (ESEG, 0)
        m.w(ESEG2, 0, b'\xcb'); m.w(ESEG, 0x10, b'\xca\x02\x00')
        # caller: [0] call A (returns to 8, should never happen) ; [0x10] call B ; [0x18] landing
        code = bytearray(b'\x90' * 0x20)
        a = self.callw(wa, 0xAAAA); code[0:len(a)] = a; code[8] = 0xf4                  # hlt = wrong return
        b = self.callw(wb, 0xBBBB); code[0x10:0x10 + len(b)] = b
        self.caller(CSEG, bytes(code))
        m.stack(0x1000, 0xF000)
        m.run(CSEG, 0, *throw_at)                           # enter A (and the inner call)
        self.assertEqual(self.wtop() // 8, 2 if nested else 1)
        m.stack(0x1000, 0xF000)                             # Throw: back to the caller's frame
        cs, ip = m.run(CSEG, 0x10, CSEG, 0x18)
        self.assertEqual((cs, ip), (CSEG, 0x18), "B's return went to %04x:%04x" % (cs, ip))
        self.assertEqual(m.reg(UC_X86_REG_SP), 0xF000)
        self.assertEqual(self.wtop(), 0, 'abandoned records must be dropped')
    def test_throw_then_same_sp_call(self): self.throw_then_reuse(False)
    def test_throw_from_nested_then_same_sp_call(self): self.throw_then_reuse(True)

    def test_jump_chain_into_second_wrapper(self):
        """callee A (wrapped) tail-jumps through a pointer table into another W stub (unknown
        caller): no second record, B's retf returns straight to A's caller"""
        m = self.m
        wb = self.stub(ESEG2, 0, 0); wa = self.stub(ESEG, 0, 1)
        m.w(ESEG, 0, b'\xea' + struct.pack('<HH', wb, WSEG))     # A: jmp far W_B
        m.w(ESEG2, 0, b'\xca\x02\x00')                           # B: retf 2
        seen = []
        m.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s_, u: seen.append(self.wtop() // 8),
                      begin=ESEG2 << 4, end=ESEG2 << 4)
        self.caller(CSEG, self.callw(wa, 5) + b'\x90\x90')
        m.stack(0x1000, 0xF000)
        self.assertEqual(m.run(CSEG, 0, CSEG, 8), (CSEG, 8))
        self.assertEqual(seen, [1]); self.assertEqual(self.wtop(), 0)
        self.assertEqual(self.locks, {}, 'no lock for a chained entry')
        self.assertEqual(m.reg(UC_X86_REG_SP), 0xF000)

    def test_unknown_caller_lock_balance(self):
        w = self.stub(ESEG, 0, 0)
        self.m.w(ESEG, 0, b'\xca\x02\x00')
        self.caller(CSEG, self.callw(w, 1) + b'\x90\x90')
        self.m.stack(0x1000, 0xF000)
        self.assertEqual(self.m.run(CSEG, 0, CSEG, 8), (CSEG, 8))
        self.assertEqual(self.locks, {CSEG: 0}); self.assertEqual(self.wtop(), 0)

    def test_unknown_caller_throw_unlocks(self):
        m = self.m
        wa = self.stub(ESEG, 0, 0); wb = self.stub(ESEG, 0x10, 0)
        m.w(ESEG, 0x10, b'\xca\x02\x00')
        code = bytearray(b'\x90' * 0x20)
        a = self.callw(wa, 1); code[0:len(a)] = a; code[8] = 0xf4
        b = self.callw(wb, 2); code[0x10:0x10 + len(b)] = b
        self.caller(CSEG, bytes(code)); m.stack(0x1000, 0xF000)
        m.run(CSEG, 0, ESEG, 0); m.stack(0x1000, 0xF000)
        self.assertEqual(m.run(CSEG, 0x10, CSEG, 0x18), (CSEG, 0x18))
        self.assertEqual(self.locks, {CSEG: 0}, 'abandoned locked record must be unlocked')

# --------------------------------------------------------------------------- fshrink
DG, FBASE = 0x1000, 0x500
def make_heap(m, seg, live_end, size):
    """local heap in seg: first arena 0x10, one used block to live_end, one free block, sentinel"""
    di = 0x10; first = 0x40; last = size - 0x10
    m.ww(seg, 6, di)
    m.ww(seg, di + 0x22, 0x484c); m.ww(seg, di + 6, first); m.ww(seg, di + 8, last); m.ww(seg, di + 0x20, size)
    m.ww(seg, first + 8, live_end)                         # first arena -> first free block
    m.ww(seg, live_end + 4, last - live_end); m.ww(seg, live_end + 8, last)
    span = last + 0xa - first; free = (last - live_end) - 0xa
    live = span - free
    return live + max(live // 2, 0x800)

class FShrink(unittest.TestCase):
    def machine(self, var):
        m = M(); code, sym = nasm(os.path.join(ASM, 'fshrink.asm'), {'BASE': FBASE, 'MINHEAD': '0x800', var: None})
        m.w(0x2800, FBASE, code)
        self.ls = []
        m.link(0x2800, sym, FBASE, 'ls', m.fake('ls', 2, lambda a: (self.ls.append((a[1], a[0])) or a[0], None)))
        m.w(0x2800, 0x10, b'\xe8' + struct.pack('<h', FBASE - 0x13) + b'\x90')    # near call entry ; nop
        return m
    def obj(self, m, hseg, slot):
        """object handle at DG:slot -> pointer -> struct with heap segment at +0x2f"""
        m.ww(DG, slot, slot + 0x100); m.ww(DG, slot + 0x100 + 0x2f, hseg)
        return slot
    def test_sys_consecutive_containers(self):
        m = self.machine('SYS')
        prev_heap, heaps = 0x7000, (0x7400, 0x7800)
        make_heap(m, prev_heap, 0x200, 0x3000)
        want = [make_heap(m, h, 0x300 + 0x100 * i, 0x3000) for i, h in enumerate(heaps)]
        prev = self.obj(m, prev_heap, 0x40)
        for i, h in enumerate(heaps):
            new = self.obj(m, h, 0x60 + 0x10 * i)
            m.ww(DG, 0x36f4, new); m.ww(DG, 0x36f6, DG)    # what 75:03A8 stores
            m.ww(DG, 0x370a, prev); m.ww(DG, 0x370c, DG)    # previous container (restored next)
            m.reg(UC_X86_REG_DS, DG); m.stack(0x1100, 0xF000); m.reg(UC_X86_REG_BP, 0xF010)
            m.ww(0x1100, 0xF010 - 2, 0xBEEF)
            m.run(0x2800, 0x10, 0x2800, 0x13)
            self.assertEqual(m.reg(UC_X86_REG_AX), 0xBEEF, 'displaced mov ax,[bp-2]')
            self.assertEqual(m.reg(UC_X86_REG_DS), DG)
        self.assertEqual(self.ls, list(zip(heaps, want)))
        self.assertNotIn(prev_heap, [h for h, _ in self.ls])
    def test_form_consecutive_forms(self):
        m = self.machine('FORM')
        heaps = (0x7400, 0x7800); want = [make_heap(m, h, 0x1800 + 0x400 * i, 0x3000) for i, h in enumerate(heaps)]
        for h in heaps:
            m.reg(UC_X86_REG_DS, DG); m.stack(0x1100, 0xF000); m.reg(UC_X86_REG_BP, 0xF020)
            m.ww(0x1100, 0xF020 - 0x12, h); m.ww(DG, 0x396c, 2); m.ww(DG, 0x371e, 0)
            m.run(0x2800, 0x10, 0x2800, 0x13)
            self.assertEqual(m.rw(DG, 0x371e), 1, 'displaced cmp/mov')
        self.assertEqual(self.ls, list(zip(heaps, want)))
        for h, cb in self.ls: self.assertEqual(m.rw(h, 0x10 + 0x20), cb, 'heap minimum lowered first')
    def test_no_shrink_when_full(self):
        m = self.machine('FORM')
        make_heap(m, 0x7400, 0x2800, 0x3000)
        m.reg(UC_X86_REG_DS, DG); m.stack(0x1100, 0xF000); m.reg(UC_X86_REG_BP, 0xF020)
        m.ww(0x1100, 0xF020 - 0x12, 0x7400); m.ww(DG, 0x396c, 0)
        m.run(0x2800, 0x10, 0x2800, 0x13)
        self.assertEqual(self.ls, [])

if __name__ == '__main__':
    unittest.main()
