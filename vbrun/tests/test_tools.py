"""Tests for the rig tooling: log pairing (rig/xwlog.py) and disk staging (rig/run.sh).
Run: python3 tests/test_tools.py"""
import os, sys, subprocess, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); RIG = os.path.join(HERE, '..', 'rig')
sys.path.insert(0, RIG)
import xwlog

def xw(name, frm, args, sp, i, id=None, ss='3FC1'):
    return 'XW %s from %s args(sp+4..) %s DS:3FC1 SS:%s SP:%s BP:0000%s i%d' % (
        name, frm, ' '.join(args + ['0000'] * (6 - len(args))), ss, sp, '' if id is None else ' id:%d' % id, i)
def xr(name, ax, i, id=None, dx='0000'):
    return 'XR %s -> AX:%s DX:%s CX:0000 ES:0000%s i%d' % (name, ax, dx, '' if id is None else ' id:%d' % id, i)

class Pairing(unittest.TestCase):
    def test_nested_with_ids(self):
        # GRA (segment load) runs a nested GA (relocation buffer) that fails, then GRA succeeds;
        # a later GA whose result arrives after an unrelated nested call
        log = [xw('GRA', '0FA7:50C8', ['0000', '0400', '0000', '00DE'], '7000', 1, 0),
               xw('GA', '0FA7:4F8E', ['02E0', '0000', '0022'], '6F00', 2, 1),
               xr('GA', '0000', 3, 1),
               xr('GRA', '00DE', 4, 0),
               xw('GA', '9805:004D', ['0100', '0000', '0041'], '7100', 5, 2),
               xw('GRA', '9805:00F1', ['0040', '0300', '0000', '5237'], '7050', 6, 3),
               xr('GRA', '5237', 7, 3),
               xr('GA', '6000', 8, 2)]
        calls, _ = xwlog.parse(log)
        got = {(c.name, c.frm): c.ret[0] for c in calls}
        self.assertEqual(got[('GA', '0FA7:4F8E')], 0)
        self.assertEqual(got[('GRA', '0FA7:50C8')], 0xDE)
        self.assertEqual(got[('GA', '9805:004D')], 0x6000)
        self.assertEqual(got[('GRA', '9805:00F1')], 0x5237)
        self.assertEqual([c.frm for c in calls if c.ret[0] == 0], ['0FA7:4F8E'])

    def test_abandoned_call_does_not_steal_later_return(self):
        # first GA never returns (stack unwound); the second GA's return must not be given to it
        log = [xw('GA', '1111:0001', ['0010'], '7000', 1, 0),
               xw('GA', '2222:0002', ['0020'], '7000', 2, 1),
               xr('GA', '4321', 3, 1)]
        calls, _ = xwlog.parse(log)
        self.assertIsNone(calls[0].ret); self.assertEqual(calls[1].ret[0], 0x4321)

    def test_recursive_same_name(self):
        log = [xw('GRA', '0FA7:50C8', ['0000', '1272', '0000', '0072'], '7000', 1, 0),
               xw('GRA', '0FA7:50C8', ['0000', '1272', '0000', '0072'], '6E00', 2, 1),
               xr('GRA', '0000', 3, 1), xr('GRA', '0072', 4, 0)]
        calls, _ = xwlog.parse(log)
        self.assertEqual([c.ret[0] for c in calls], [0x72, 0])

    def test_legacy_lifo(self):
        log = [xw('GRA', '0FA7:50C8', ['0'*4], '7000', 1), xw('GA', '0FA7:4F8E', ['02E0'], '6F00', 2),
               xr('GA', '0000', 3), xr('GRA', '00DE', 4)]
        calls, _ = xwlog.parse(log)
        self.assertEqual([(c.name, c.ret[0]) for c in calls], [('GRA', 0xDE), ('GA', 0)])

class ShrinkCheck(unittest.TestCase):
    def ga(self, i, es, id): return [xw('GA', '9FE9:0089', ['30AA', '0000', '0042'], '7000', i, id), xr('GA', '050E', i + 1, id).replace('ES:0000', 'ES:%04X' % es)]
    def ls(self, i, h, id): return [xw('LS', '9081:08C8', ['0BDC', '%04X' % h], '7000', i, id), xr('LS', '0BDE', i + 1, id)]
    def test_consecutive_forms_each_own_heap(self):
        log = self.ga(10, 0x6810, 1) + self.ls(20, 0x6811, 2) + self.ga(30, 0x68DA, 3) + self.ga(40, 0x6E5E, 4) + self.ls(50, 0x6E5F, 5)
        self.assertEqual([v for _, v in xwlog.check_shrinks(xwlog.parse(log)[0])], ['ok', 'ok'])
    def test_previous_heap_flagged(self):
        log = self.ga(10, 0x6810, 1) + self.ga(30, 0x68DA, 3) + self.ls(50, 0x6811, 5)
        self.assertEqual([v for _, v in xwlog.check_shrinks(xwlog.parse(log)[0])], ['WRONG HEAP'])
    def test_twice_flagged(self):
        log = self.ga(10, 0x6810, 1) + self.ls(20, 0x6811, 2) + self.ls(30, 0x6811, 3)
        self.assertEqual([v for _, v in xwlog.check_shrinks(xwlog.parse(log)[0])], ['ok', 'TWICE'])
    def test_register_field_tolerated(self):
        l = xw('GA', '9FE9:0089', ['30AA'], '7000', 5, 7).replace(' id:7', ' R:0001,0002,0003,0004,0005,0006,0007 id:7')
        self.assertEqual(xwlog.parse([l])[0][0].id, '7')

class Staging(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(); self.mp = os.path.join(self.td, 'marty')
        os.makedirs(os.path.join(self.mp, 'install', 'media', 'hdds')); os.makedirs(os.path.join(self.mp, 'target', 'release'))
        open(os.path.join(self.mp, 'install', 'martypc.toml'), 'w').write('filename = "default_xtide.vhd"\n')
        b = os.path.join(self.mp, 'target', 'release', 'martypc')
        open(b, 'w').write('#!/bin/sh\necho "$@" > "%s/ran"\n' % self.td); os.chmod(b, 0o755)
        self.disk = os.path.join(self.td, 'sub', 'a.vhd'); os.makedirs(os.path.dirname(self.disk))
        open(self.disk, 'wb').write(b'NEWDISK' * 100)
        self.stage = os.path.join(self.mp, 'install', 'media', 'hdds', 'cur.vhd')
        open(self.stage, 'wb').write(b'STALE')
    def run_sh(self, arg, cwd):
        env = dict(os.environ, MARTYPC_DIR=self.mp, MARTY_LOG=os.path.join(self.td, 'log'), DISPLAY=':99')
        return subprocess.run(['bash', os.path.join(RIG, 'run.sh'), arg], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=30)
    def test_relative_path_from_other_dir(self):
        r = self.run_sh('sub/a.vhd', self.td)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(open(self.stage, 'rb').read(), open(self.disk, 'rb').read())
    def test_missing_disk_fails_and_does_not_boot(self):
        r = self.run_sh('sub/missing.vhd', self.td)
        self.assertNotEqual(r.returncode, 0)
        import time; time.sleep(0.5)
        self.assertFalse(os.path.exists(os.path.join(self.td, 'ran')))
        self.assertEqual(open(self.stage, 'rb').read(), b'STALE')   # untouched, and not booted
    def test_staging_failure_fails_and_leaves_no_stale_disk(self):
        os.rename(os.path.join(self.mp, 'install', 'media', 'hdds'), os.path.join(self.td, 'gone'))
        r = self.run_sh(self.disk, self.td)
        self.assertNotEqual(r.returncode, 0); self.assertIn('staging', r.stderr)
        import time; time.sleep(0.5)
        self.assertFalse(os.path.exists(os.path.join(self.td, 'ran')))

def mini_ne(segs, gang=None):
    """Minimal NE image: segs = [(file_offset, length, flags)], sector shift 4,
    optional fast-load area gang=(start, length) in bytes."""
    import struct
    ne = 0x40; sto = 0x40; et = sto + 8 * len(segs)
    d = bytearray(0x400)
    d[0:2] = b'MZ'; struct.pack_into('<I', d, 0x3c, ne)
    d[ne:ne + 2] = b'NE'
    struct.pack_into('<HH', d, ne + 4, et, 1)            # entry table: one terminating 0
    struct.pack_into('<H', d, ne + 0x1c, len(segs)); struct.pack_into('<H', d, ne + 0x22, sto)
    struct.pack_into('<H', d, ne + 0x32, 4)
    if gang:
        d[ne + 0x37] = 0x08; struct.pack_into('<HH', d, ne + 0x38, gang[0] >> 4, gang[1] >> 4)
    for i, (o, l, f) in enumerate(segs):
        struct.pack_into('<HHHH', d, ne + sto + 8 * i, o >> 4, l, f, l)
    return bytes(d)

class FastLoad(unittest.TestCase):
    """nevalid.py: segments loaded with the module must sit inside the fast-load area."""
    def run_valid(self, img):
        with tempfile.NamedTemporaryFile(suffix='.dll', delete=False) as f: f.write(img)
        try:
            return subprocess.run([sys.executable, os.path.join(HERE, '..', 'nevalid.py'), f.name],
                                  capture_output=True, text=True).stdout
        finally: os.unlink(f.name)
    def test_fixed_segment_outside_area_flagged(self):
        # seg1 preload inside the area, seg2 movable, seg3 FIXED far outside (the VBRUN seg 4 case)
        out = self.run_valid(mini_ne([(0x100, 0x40, 0x50), (0x200, 0x40, 0x10), (0x300, 0x40, 0x00)], gang=(0x100, 0x40)))
        self.assertIn('seg 3 loaded with the module but outside the fast-load area', out)
    def test_no_area_ok(self):
        out = self.run_valid(mini_ne([(0x100, 0x40, 0x50), (0x200, 0x40, 0x10), (0x300, 0x40, 0x00)]))
        self.assertTrue(out.strip().endswith('OK []'), out)
    def test_movable_outside_area_ok(self):
        out = self.run_valid(mini_ne([(0x100, 0x40, 0x50), (0x200, 0x40, 0x10)], gang=(0x100, 0x40)))
        self.assertTrue(out.strip().endswith('OK []'), out)

if __name__ == '__main__':
    unittest.main()
