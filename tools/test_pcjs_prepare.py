"""Host-side fixture contracts. No claim of emulated guest execution."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import prepare_pcjs as p


class PreparationTests(unittest.TestCase):
    def test_all_runtime_assets_pinned(self):
        assets = json.loads((p.TEMPLATES/'assets.json').read_text())
        self.assertEqual(len(assets['pcjs_commit']), 40)
        self.assertEqual({a['name'] for a in assets['assets']},
                         {'pcx86.js','components.css','ATBIOS-REV3.json5','IBM-EGA.json5','PCJS-LICENSE.txt'})
        for a in assets['assets']:
            self.assertIn('/'+assets['pcjs_commit']+'/', a['url'])
            self.assertEqual(len(a['sha256']), 64)
            self.assertGreater(a['bytes'], 0)

    def test_refuses_mismatched_hash(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            p.checked(b'not the original', p.SPECIMEN_SHA, 'specimen')

    def test_refuses_changed_media_before_decoding(self):
        with self.assertRaisesRegex(ValueError, 'reference JSON'):
            p.compose(b'[]', b'anything')

    def test_does_not_write_in_repository(self):
        args=SimpleNamespace(out=str(p.ROOT/'private'), reference_media=True)
        with self.assertRaisesRegex(ValueError, 'OUTSIDE'):
            p.prepare(args)

    def test_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as out:
            args=SimpleNamespace(out=out, reference_media=True)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                p.prepare(args)

    def test_media_fetch_requires_explicit_option(self):
        with tempfile.TemporaryDirectory() as base:
            args=SimpleNamespace(out=str(Path(base)/'fresh'), reference_media=False, disk_json=None, winmine=None)
            with self.assertRaisesRegex(ValueError, 'explicitly choose'):
                p.prepare(args)

    def test_template_is_286_without_xslt(self):
        markup=(p.TEMPLATES/'machine.html').read_text()
        self.assertIn("model:'80286'", markup)
        self.assertNotIn("model:'8088'", markup)
        self.assertNotIn('ramExt', markup)
        self.assertIn("resume:'0'", markup)
        self.assertIn('disk.json', markup)
        self.assertIn('multiplier:1,', markup)
        self.assertNotIn('XSLTProcessor', markup)
        self.assertIn('<!-- PCJS_MACHINE -->', (p.TEMPLATES/'index.html').read_text())

    def test_guest_failures_do_not_launch_windows(self):
        startup = p.AUTOEXEC.decode('ascii')
        for command in ('WM88TSR.COM', 'TEST88.COM', 'RTEST2.COM'):
            self.assertIn(command+'\r\nIF ERRORLEVEL 1 GOTO FAILED\r\n', startup)
        self.assertNotIn('@ECHO', startup)  # PC DOS 3.20 predates @ suppression.
        failed = startup.split(':FAILED\r\n', 1)[1]
        self.assertNotIn('WIN /R', failed)
        self.assertIn('VALIDATION FAILED', failed)


if __name__ == '__main__':
    unittest.main()
