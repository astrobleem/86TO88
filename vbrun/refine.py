import sys, json, collections
sys.path.insert(0, '.')
from endanger import analyse, classify
from reach import explore
segs, calls, ptrs = analyse(sys.argv[1])
cache = {}
def danger(a, off):
    k = (a, off)
    if k not in cache:
        ev, _ = explore(segs[a - 1]['code'], off)
        cache[k] = ev
    return cache[k]
cls = {}; ev = {}
for c in calls:
    k = (c[2], c[3]); cls[k] = classify(segs[c[2] - 1]['code'], c[3]); ev[k] = danger(*k)
end = collections.defaultdict(set); why = collections.Counter()
for c in calls:
    k = (c[2], c[3])
    if cls[k] == 'marked' or c[4] == 'jmpf': continue
    e = ev[k]
    if e & {'far', 'int3f', 'indirect', 'limit', 'baddecode'}:
        end[c[0]].add(k); why[tuple(sorted(e))] += 1
print('unmarked/frameless far callees', sum(1 for k in cls if cls[k] != 'marked'),
      'of which can move memory while active', len({k for v in end.values() for k in v}))
print('reasons', dict(why))
print('endangered caller segments', len(end), sorted(end))
codesz = {i + 1: s['len'] for i, s in enumerate(segs) if not s['flags'] & 1}
print('endangered bytes', sum(codesz[s] for s in end), 'of', sum(codesz.values()))
# callback / table targets that hand control to an unmarked/frameless function which can move memory
cb = sorted({(p[2], p[3]) for p in ptrs if classify(segs[p[2] - 1]['code'], p[3]) != 'marked'
             and danger(p[2], p[3]) & {'far', 'int3f', 'indirect'}})
print('dangerous non-marked far-pointer targets', len(cb), cb)
json.dump({str(k): sorted(v) for k, v in end.items()}, open(sys.argv[2], 'w'))
