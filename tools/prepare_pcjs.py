#!/usr/bin/env python3
"""Prepare a private, self-hosted PCjs judge fixture. Python 3.9+, stdlib only.

No Microsoft disk is part of this repository. --reference-media explicitly
retrieves public archival reference media; availability is not a copyright
license. Alternatively supply the pinned JSON and your own exact WINMINE.EXE.
"""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request

from pcjs_media import decode_pcjs, encode_pcjs, FatDisk

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'emulator' / 'pcjs'
PIN = 'd2a82f69c9cbfe028020ff7d1cf3679638c5cf9d'
BASE = f'https://raw.githubusercontent.com/Foxlum/pcjs-wiki/{PIN}/disks/pcx86/fixed/20mb/'
MEDIA = {
    'windows30': ('PCDOS320-WIN300-EGA.json', 'ee96645f9e9bb629c2250f11c06b72c86b31f24b164c32efef28d89ffb90a4e2'),
    'windows31': ('PCDOS330-WIN310-VGA.json', 'abcf3297ae3adde213d96363448c88a709febc817692aa17a677d7b0d4fe0112'),
}
SPECIMEN_SHA = '633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b'
TSR_SHA = 'c04950d38ca03a209a898e16029260211e0b538c65ee3a99f3ac90e285c469f7'
SHIM_SHA = '2d7532ae8ac73b957b5fb423449168c7b8f976b150155a42ac37d4b0139ddd1b'
AUTOEXEC = '''ECHO OFF
PATH C:\\;C:\\WINDOWS
SET TEMP=C:\\WINDOWS\\TEMP
CD \\WINDOWS
ECHO 86TO88 judge fixture - 80286, Windows 3.0 real mode
ECHO The 286 browser demo is NOT an 8088 hardware proof.
WM88TSR.COM
IF ERRORLEVEL 1 GOTO FAILED
TEST88.COM
IF ERRORLEVEL 1 GOTO FAILED
RTEST2.COM
IF ERRORLEVEL 1 GOTO FAILED
ECHO Starting Windows 3.0 with WIN /R WINMINE.EXE
WIN /R WINMINE.EXE
GOTO END
:FAILED
ECHO VALIDATION FAILED - Windows was NOT launched.
ECHO Keep the error above for diagnosis. Do not report this run as passing.
:END
'''.replace('\n', '\r\n').encode('ascii')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(data, digest, label):
    if sha(data) != digest:
        raise ValueError(f'{label}: SHA-256 mismatch; refusing changed input')
    return data


def download(url, digest, limit=32*1024*1024):
    request = urllib.request.Request(url, headers={'User-Agent': '86TO88-PCjs-private-judge/1'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Download exceeds size limit: '+url)
    return checked(data, digest, url)


def read_media(key, path):
    filename, digest = MEDIA[key]
    return checked(Path(path).read_bytes(), digest, filename) if path else download(BASE+filename, digest)


def compose(source, specimen):
    checked(source, MEDIA['windows30'][1], 'Windows 3.0 reference JSON')
    checked(specimen, SPECIMEN_SHA, 'WINMINE.EXE')
    if len(specimen) != 27776:
        raise ValueError('Unexpected WINMINE.EXE length')
    raw, geometry = decode_pcjs(source)
    if tuple(geometry[k] for k in ('cylinders', 'heads', 'sectors_per_track')) != (615,4,17):
        raise ValueError('Expected 615/4/17 reference disk geometry')
    disk = FatDisk(raw)
    before = {name: sha(disk.read_file(name)) for name in disk.list_files()}
    changes = {
        'WINDOWS/WM88TSR.COM': checked((ROOT/'deliverable/WM88TSR.COM').read_bytes(), TSR_SHA, 'WM88TSR.COM'),
        'WINDOWS/SYSTEM/SHELL.DLL': checked((ROOT/'deliverable/SHELL.DLL').read_bytes(), SHIM_SHA, 'SHELL.DLL'),
        'WINDOWS/WINMINE.EXE': specimen,
        # Git may check this text file out with CRLF on Windows. Preserve the
        # canonical LF bytes used by the validated disk on every host.
        'WINDOWS/WM88.BAT': (ROOT/'deliverable/WM88.BAT').read_bytes().replace(b'\r\n', b'\n'),
        'WINDOWS/TEST88.COM': (ROOT/'tests/TEST88.COM').read_bytes(),
        'WINDOWS/RTEST2.COM': (ROOT/'tests/RTEST2.COM').read_bytes(),
        # EGA.SYS preserves EGA state for Windows 3.0 real mode. HIMEM and
        # SMARTDRV are deliberately not loaded: this fixture is 640 KiB only.
        'CONFIG.SYS': b'FILES=30\r\nBUFFERS=10\r\nDEVICE=C:\\WINDOWS\\EGA.SYS\r\n',
        'AUTOEXEC.BAT': AUTOEXEC,
    }
    for name, data in changes.items():
        disk.write_file(name, data)
    result = disk.to_bytes()
    reread = FatDisk(result)
    for name, data in changes.items():
        if reread.read_file(name) != data:
            raise ValueError('Written file verification failed: '+name)
    unchanged = [name for name in before if name not in changes]
    if any(sha(reread.read_file(name)) != before[name] for name in unchanged):
        raise ValueError('An unrelated guest file changed')
    encoded = encode_pcjs(result, geometry)
    if decode_pcjs(encoded)[0] != result:
        raise ValueError('PCjs encoding round-trip failed')
    return encoded, {
        'geometry': geometry,
        'source_json_sha256': sha(source),
        'source_raw_sha256': sha(raw),
        'disk_sha256': sha(encoded),
        'specimen_sha256': sha(specimen),
        'unchanged_original_files': len(unchanged),
        'changed_or_added': {name: sha(data) for name,data in changes.items()},
    }


def prepare(args):
    out = Path(args.out).resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError('Private output must be OUTSIDE this public repository')
    if out.exists():
        raise ValueError('Output already exists; choose a new directory (no overwrites or backups)')
    if not args.reference_media and not (args.disk_json and args.winmine):
        raise ValueError('Supply --disk-json and --winmine, or explicitly choose --reference-media')
    source = read_media('windows30', args.disk_json)
    if args.winmine:
        specimen = Path(args.winmine).read_bytes()
    else:
        data = read_media('windows31', args.win31_json)
        raw, _ = decode_pcjs(data)
        specimen = FatDisk(raw).read_file('WINDOWS/WINMINE.EXE')
    disk, report = compose(source, specimen)
    assets = json.loads((TEMPLATES/'assets.json').read_text())
    runtime = {}
    for asset in assets['assets']:
        print('Fetching pinned runtime asset:', asset['name'], flush=True)
        runtime[asset['name']] = download(asset['url'], asset['sha256'], 2*1024*1024)
    # Write only after every input/download passed validation. Original inputs
    # are read-only; neither input media nor archive copies are retained here.
    out.mkdir(parents=True, exist_ok=False)
    (out/'vendor').mkdir()
    (out/'disk.json').write_bytes(disk)
    for name, data in runtime.items():
        (out/'vendor'/name).write_bytes(data)
    for name in ('index.html', 'judge.css'):
        content = (TEMPLATES/name).read_text()
        if name == 'index.html':
            content = content.replace('<!-- PCJS_MACHINE -->', (TEMPLATES/'machine.html').read_text())
        (out/name).write_text(content)
    # PCjs' documented resource cache supports a private all-in-one file.
    # This needs no localhost server and makes no ROM/disk network requests.
    # PCjs consults resources.parms for optional machine settings. Even when
    # none are supplied it must be valid JSON, or browser startup shows alerts.
    resources = {'parms': '{}', 'disk.json': disk.decode('utf-8')}
    resources.update({'vendor/'+name: data.decode('utf-8') for name,data in runtime.items() if name.endswith('.json5')})
    preload = json.dumps(resources, ensure_ascii=True).replace('<', '\\u003c')
    offline = (out/'index.html').read_text()
    offline = offline.replace('<link rel="stylesheet" href="vendor/components.css">', '<style>'+runtime['components.css'].decode('utf-8')+'</style>')
    offline = offline.replace('<link rel="stylesheet" href="judge.css">', '<style>'+(TEMPLATES/'judge.css').read_text()+'</style>')
    offline = offline.replace('<script src="vendor/pcx86.js"></script>', '<script>window.resources='+preload+';</script><script>'+runtime['pcx86.js'].decode('utf-8').replace('</script', '<\\/script')+'</script>')
    (out/'judge.html').write_text(offline)
    report.update({
        'status': 'HOST PREPARATION PASS; guest not executed by this script',
        'guest_executed': False,
        'cpu_model': 80286,
        'clock_multiplier': 1,
        'windows_startup_command': 'WIN /R WINMINE.EXE',
        'pcjs_commit': assets['pcjs_commit'],
        'runtime_assets': assets['assets'],
        'reference_sources': {k: {'url':BASE+v[0], 'sha256':v[1]} for k,v in MEDIA.items()},
        'third_party_notice': 'Archival availability is not redistribution permission. Keep generated disks private.',
    })
    (out/'PREPARED.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'KEEP-PRIVATE.txt').write_text('Contains DOS/Windows and ROM media. Do not commit, upload, or publish this folder.\nServe locally on 127.0.0.1 only. Browser Reset restarts the session; reload restores the prepared disk.\n')
    print(f'Prepared private fixture: {out}')
    print('Recommended launch (Windows: use py -3 or python instead of python3):')
    print(f'python3 -m http.server 8080 --bind 127.0.0.1 --directory "{out}"')
    print('Leave the server running and open http://127.0.0.1:8080/judge.html')
    print(f'Optional unverified file:// alternative: {out/"judge.html"}')
    print('Fullscreen and browser-control extensions are not required. Keep generated media private.')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, help='New private output directory outside the repo')
    p.add_argument('--reference-media', action='store_true', help='Explicitly fetch public archival DOS/Windows reference media locally (not a redistribution license)')
    p.add_argument('--disk-json', help='Offline pinned PCDOS320-WIN300-EGA.json')
    p.add_argument('--winmine', help='Your exact unmodified Windows 3.1 WINMINE.EXE')
    p.add_argument('--win31-json', help='Offline pinned Windows 3.1 source JSON instead of its download')
    args = p.parse_args()
    try:
        prepare(args)
    except (ValueError, OSError, KeyError) as exc:
        p.exit(1, f'Preparation stopped: {exc}\n')
