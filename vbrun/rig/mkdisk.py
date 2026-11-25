"""mtools helpers for the partitioned Windows 3.0 test image (partition at byte offset 8704)."""
import subprocess, sys, os, shutil, tempfile, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vhd
OFF = 8704
os.environ['MTOOLS_SKIP_CHECK'] = '1'
def mt(*a, inp=None):
    return subprocess.run(['mtools'] + list(a), input=inp, capture_output=True, check=True)
class Img:
    def __init__(self, path): self.p = path + '@@%d' % OFF
    def run(self, cmd, *a, **k):
        r = subprocess.run([cmd, '-i', self.p] + list(a), capture_output=True, **k)
        if r.returncode: raise RuntimeError((cmd, a, r.stderr.decode()))
        return r.stdout
    def put(self, src, dst): self.run('mcopy', '-o', '-n', src, '::' + dst)
    def mkdir(self, d):
        subprocess.run(['mmd', '-i', self.p, '::' + d], capture_output=True)
    def get(self, p): return self.run('mtype', '-t' if False else '', '::' + p) if False else subprocess.run(['mcopy','-i',self.p,'::'+p,'-'],capture_output=True).stdout
def set_ini(data, section, key, value):
    text = data.decode('latin1')
    lines = text.split('\r\n'); out = []; insec = False; done = False; seen = False
    for ln in lines:
        m = re.match(r'^\[(.*)\]\s*$', ln)
        if m:
            if insec and not done: out.append('%s=%s' % (key, value)); done = True
            insec = m.group(1).lower() == section.lower(); seen = seen or insec
        elif insec and re.match(r'^\s*%s\s*=' % re.escape(key), ln, re.I):
            ln = '%s=%s' % (key, value); done = True
        out.append(ln)
    if insec and not done: out.insert(len(out) - 1 if out and out[-1] == '' else len(out), '%s=%s' % (key, value)); done = True
    if not seen: out += ['[%s]' % section, '%s=%s' % (key, value)]
    return '\r\n'.join(out).encode('latin1')
