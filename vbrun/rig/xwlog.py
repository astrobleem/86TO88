"""Parse MartyPC trace logs (trace-hooks.patch): pair each watched call (XW) with its return
(XR) and summarise. Pairing uses the sequence id both lines carry ('id:N'); the emulator
matches a return to the innermost pending call on the same SS. Logs from before ids existed
are paired per name, innermost first (LIFO), which is only right if no call is abandoned.

  python3 xwlog.py LOG            summary (allocation failures, reloads, LocalShrink, ...)
  python3 xwlog.py LOG --pairs    every call with its result
"""
import sys, re, collections

XW = re.compile(r'^XW (\S+) from (\w{4}):(\w{4}) args\(sp\+4\.\.\) ((?:\w{4} ?){6}) DS:(\w+) SS:(\w+) SP:(\w+) BP:(\w+)(?: R:[\w,]+)?(?: id:(\d+))? i(\d+)')
XR = re.compile(r'^XR (\S+) -> AX:(\w+) DX:(\w+) CX:(\w+) ES:(\w+)(?: id:(\d+))? i(\d+)')

class Call:
    __slots__ = ('name', 'frm', 'args', 'ss', 'sp', 'id', 't', 'ret', 'rt', 'es')
    def __repr__(self):
        r = 'AX:%04X DX:%04X' % self.ret if self.ret else 'no return'
        return '%s from %s args %s -> %s @i%d' % (self.name, self.frm, ' '.join('%04X' % a for a in self.args), r, self.t)

def parse(lines):
    calls = []; byid = {}; stacks = collections.defaultdict(list); other = []
    for l in lines:
        m = XW.match(l)
        if m:
            c = Call(); c.name = m.group(1); c.frm = m.group(2) + ':' + m.group(3)
            c.args = [int(x, 16) for x in m.group(4).split()]; c.ss = int(m.group(6), 16); c.sp = int(m.group(7), 16)
            c.id = m.group(9); c.t = int(m.group(10)); c.ret = None; c.rt = None
            calls.append(c)
            if c.id is not None: byid[c.id] = c
            else: stacks[c.name].append(c)
            continue
        m = XR.match(l)
        if m:
            name, rid = m.group(1), m.group(6)
            c = byid.pop(rid, None) if rid is not None else (stacks[name].pop() if stacks[name] else None)
            if c is None or c.name != name:
                other.append(('unmatched return', l.strip())); continue
            c.ret = (int(m.group(2), 16), int(m.group(3), 16)); c.rt = int(m.group(7)); c.es = int(m.group(5), 16)
            continue
        if l.startswith(('PC ', 'DUMPED', 'RING-TRIGGERED')): other.append((l.split()[0], l.strip()))
    return calls, other

FAIL_NAMES = ('GA', 'GRA', 'LA', 'LRA')

def check_shrinks(calls, heap_size=0x30AA):
    """Each LocalShrink (LS, hseg at args[1]) must target the local heap created most
    recently before it (GlobalAlloc of heap_size; the data segment is the returned arena
    ES + 1), and no heap may be shrunk twice. Returns [(ls_call, verdict)] with verdict
    'ok', 'WRONG HEAP', 'TWICE' or 'unknown' (creation's return not seen)."""
    out = []; seen = set(); last = None
    for c in sorted(calls, key=lambda c: c.t):
        if c.name == 'GA' and c.args[0] == heap_size and c.args[1] == 0:
            last = c
        elif c.name == 'LS':
            h = c.args[1]
            if h in seen: v = 'TWICE'
            elif last is None or last.ret is None: v = 'unknown'
            else: v = 'ok' if last.es + 1 == h else 'WRONG HEAP'
            seen.add(h); out.append((c, v))
    return out
def summary(path):
    lines = open(path, 'rb').read().decode('latin1').splitlines()
    calls, other = parse(lines)
    fails = [c for c in calls if c.name in FAIL_NAMES and c.ret and c.ret[0] == 0]
    churn = collections.Counter(c.t // 10000000 for c in calls if c.name == 'GRA' and c.frm.endswith(':50C8'))
    out = ['alloc failures: %d' % len(fails)] + ['  %r' % c for c in fails[:12]]
    out.append('segment reloads per 10M: %s' % dict(sorted(churn.items())))
    out.append('LocalShrink (heap, target, new size, check): %s' % [('%04X' % c.args[1], '%04X' % c.args[0], c.ret and '%04X' % c.ret[0], v) for c, v in check_shrinks(calls)])
    out.append('MessageBox: %s' % [c.frm + ' i%d' % c.t for c in calls if c.name == 'MB'])
    out.append('pending at end: %d' % sum(1 for c in calls if c.ret is None))
    pcs = [o[1] for o in other if o[0] == 'PC'][-8:]
    out.append('last samples: ' + ' | '.join(' '.join(p.split()[1:2] + [x for x in p.split() if x.startswith(('SS:', 'SP:'))] + p.split()[-1:]) for p in pcs))
    return '\n'.join(out)

if __name__ == '__main__':
    if '--pairs' in sys.argv:
        for c in parse(open(sys.argv[1], 'rb').read().decode('latin1').splitlines())[0]: print(c)
    else:
        print(summary(sys.argv[1]))
