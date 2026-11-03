"""Fetch only hash-locked official MIT PCjs source modules; no OS media/ROMs."""
import argparse,concurrent.futures,hashlib,json,pathlib,urllib.request
p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination');a=p.parse_args()
here=pathlib.Path(__file__).resolve().parent;root=pathlib.Path(a.destination).resolve()
if root.is_relative_to(here.parents[2]):raise SystemExit('Keep downloaded runtime outside the public repository.')
lock=json.loads((here/'runtime-lock.json').read_text())
def fetch(name):
 target=root/name;expected=lock['sha256'][name]
 if target.exists():
  data=target.read_bytes()
 else:
  url='https://raw.githubusercontent.com/jeffpar/pcjs/'+lock['commit']+'/'+name
  with urllib.request.urlopen(url,timeout=60) as r:data=r.read(8*1024*1024)
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('SHA-256 mismatch: '+name)
 target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists():target.write_bytes(data)
 return name
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:files=list(pool.map(fetch,lock['sha256']))
package=root/'package.json';expected='{"type":"module"}\n'
if package.exists() and package.read_text()!=expected:raise ValueError('Existing package.json differs; choose a dedicated runtime directory')
if not package.exists():package.write_text(expected)
print('Verified',len(files),'runtime files from',lock['commit'])
