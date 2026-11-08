"""build_disk.py OUT.vhd DLLDIR [options] [SRC=DST ...]

Builds a MartyPC XT-IDE disk: the user's own installed Windows 3.0 image plus the
Entertainment Pack 2 VB apps, with converted DLLs taken from DLLDIR (anything not
in DLLDIR comes from the original set).

  --video cga|vga      display driver (default cga; vga uses VGA88.DRV from
                       windows-3-vga-8088)
  --shell APP.EXE      SYSTEM.INI shell= (default: leave Program Manager)
  --win-args ARGS      text after 'WIN /R' (e.g. C:\\GAME\\JIGSAWED.EXE)
  --no-autowin         don't start Windows from AUTOEXEC.BAT

Inputs (never committed; supply your own copies):
  VBW_WIN30_RAW     raw 615/4/17 hard-disk image with Windows 3.0 installed in C:\\WINDOWS
  VBW_ORIG          dir with original VBRUN100.DLL FIELD100.DLL WEPUTIL.DLL
                    JIGSAWED.EXE RODENT.EXE RATTLER.EXE
  VBW_W30DRV        dir with expanded CGA.DRV CGASYS.FON CGAFIX.FON CGAOEM.FON CGA.GR2
                    (and VGAOEM.FON VGAFIX.FON VGASYS.FON VGACOLOR.GR2 for --video vga)
  VBW_VGA88         path to VGA88.DRV (only for --video vga)
  VBW_VHD_TEMPLATE  MartyPC install/media/hdds/default_xtide.vhd (footer template)
"""
import sys, os, shutil, subprocess, argparse, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mkdisk import Img, set_ini
import vhd

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('dlldir')
ap.add_argument('--video', default='cga', choices=('cga', 'vga'))
ap.add_argument('--shell'); ap.add_argument('--win-args', default='')
ap.add_argument('--no-autowin', action='store_true')
ap.add_argument('extra', nargs='*')
a = ap.parse_args()
env = lambda k: os.environ.get(k) or sys.exit('set %s (see build_disk.py)' % k)
E = env('VBW_ORIG'); DRV = env('VBW_W30DRV')

raw = a.out + '.raw'
shutil.copy(env('VBW_WIN30_RAW'), raw)
im = Img(raw)
td = tempfile.mkdtemp()
log21 = os.path.join(td, 'LOG21.COM')
subprocess.check_call([sys.executable, os.path.join(HERE, 'build_log21.py'), log21], stdout=subprocess.DEVNULL)

files = []
for f in sorted(os.listdir(E)):
    if f.upper().endswith(('.DLL', '.EXE')):
        src = os.path.join(a.dlldir, f) if os.path.exists(os.path.join(a.dlldir, f)) else os.path.join(E, f)
        files.append((src, ('WINDOWS/SYSTEM/' if f.upper().endswith('.DLL') else 'GAME/') + f))
for x in a.extra:
    s, d = x.split('='); files.append((s, d))
files.append((log21, 'LOG21.COM'))

ini = im.get('WINDOWS/SYSTEM.INI')
if a.video == 'cga':
    kv = [('display.drv', 'CGA.DRV'), ('oemfonts.fon', 'cgaoem.fon'), ('fixedfon.fon', 'cgafix.fon'),
          ('fonts.fon', 'cgasys.fon'), ('286grabber', 'cga.gr2')]
    drv = ['CGA.DRV', 'CGASYS.FON', 'CGAFIX.FON', 'CGAOEM.FON', 'CGA.GR2']
else:
    kv = [('display.drv', 'VGA88.DRV'), ('oemfonts.fon', 'vgaoem.fon'), ('fixedfon.fon', 'vgafix.fon'),
          ('fonts.fon', 'vgasys.fon'), ('286grabber', 'vgacolor.gr2')]
    drv = ['VGAOEM.FON', 'VGAFIX.FON', 'VGASYS.FON', 'VGACOLOR.GR2']
    files.append((env('VBW_VGA88'), 'WINDOWS/SYSTEM/VGA88.DRV'))
files += [(os.path.join(DRV, f), 'WINDOWS/SYSTEM/' + f) for f in drv]
for k, v in kv: ini = set_ini(ini, 'boot', k, v)
if a.shell: ini = set_ini(ini, 'boot', 'shell', a.shell)

for src, dst in files:
    if os.path.dirname(dst): im.mkdir(os.path.dirname(dst))
    im.put(src, dst)
def put_text(name, data):
    p = os.path.join(td, 'x'); open(p, 'wb').write(data); im.put(p, name)
put_text('WINDOWS/SYSTEM.INI', ini)
put_text('CONFIG.SYS', b'files = 30\r\nbuffers = 30\r\n')
ae = 'PATH C:\\;C:\\WINDOWS;C:\\GAME\nSET TEMP=C:\\WINDOWS\\TEMP\nLOG21\n'
if not a.no_autowin: ae += ('WIN /R ' + a.win_args).rstrip() + '\n'
put_text('AUTOEXEC.BAT', ae.replace('\n', '\r\n').encode())
vhd.to_vhd(raw, a.out, 615, 4, 17)
os.remove(raw); shutil.rmtree(td)
print(a.out)
