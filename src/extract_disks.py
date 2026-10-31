import sys, pathlib, hashlib, json
sys.path.insert(0, "/tmp/unpack-tester/mygithubpage-gh-pages/tools")
# pcjs_disk is read-only parser from tester repo; run isolated
import importlib.util
spec = importlib.util.spec_from_file_location("pcjs_disk", "/tmp/unpack-tester/mygithubpage-gh-pages/tools/pcjs_disk.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

for label, src, outdir in [
    ("win31", "/Users/macsd/winmine-hack/work/PCDOS330-WIN310-VGA.json", "/Users/macsd/winmine-hack/upstream/extract31"),
    ("win30", "/Users/macsd/winmine-hack/work/PCDOS320-WIN300-EGA.json", "/Users/macsd/winmine-hack/upstream/extract30"),
]:
    data = pathlib.Path(src).read_bytes()
    print(label, "json sha256", hashlib.sha256(data).hexdigest(), len(data))
    raw, geo = m.decode_pcjs(data)
    print(label, geo, "raw sha256", hashlib.sha256(raw).hexdigest())
    vol = m.FatVolume(raw)
    print(label, vol.summary())
    out = pathlib.Path(outdir)
    for path, content in sorted(vol.files.items()):
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    print(label, "files:", sorted(vol.files.keys())[:20], "... total", len(vol.files))
