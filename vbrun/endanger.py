"""Static analysis: which VBRUN segments hold return addresses the real-mode
kernel cannot patch (because the far callee has no marked frame)."""
import struct, sys, collections, json

def load(fn):
    d = open(fn, 'rb').read()
    ne = struct.unpack_from('<I', d, 0x3c)[0]
    sto, = struct.unpack_from('<H', d, ne + 0x22)
    al, = struct.unpack_from('<H', d, ne + 0x32)
    n, = struct.unpack_from('<H', d, ne + 0x1c)
    segs = []
    for i in range(n):
        o, l, f, m = struct.unpack_from('<HHHH', d, ne + sto + 8 * i)
        base = o << al; ln = l or 0x10000
        code = bytearray(d[base:base + ln]) if o else bytearray()
        if m and m > ln: code += b'\0' * (m - ln)
        recs = []
        if o and f & 0x100:
            cnt, = struct.unpack_from('<H', d, base + ln)
            for k in range(cnt):
                recs.append(struct.unpack_from('<BBHHH', d, base + ln + 2 + 8 * k))
        segs.append(dict(flags=f, len=ln, code=code, recs=recs))
    return segs

def chain(code, off, additive):
    out = []
    if additive:
        return [off]
    p = off
    while p != 0xffff and p < len(code) - 1 and len(out) < 5000:
        out.append(p); p = struct.unpack_from('<H', code, p)[0]
    return out

def classify(code, off):
    """marked | unmarked | frameless | stdcb (exported-style with DS load)"""
    b = bytes(code[off:off + 12])
    i = 0
    # Windows callback/export prologues: mov ax,ds / push ds;pop ax / mov ax,ss / mov ax,imm ; nop
    for pre in (b'\x8c\xd8\x90', b'\x1e\x58\x90', b'\x8c\xd0\x90', b'\x90\x90\x90'):
        if b.startswith(pre): i = 3; break
    else:
        if b[:1] == b'\xb8': i = 3
    if b[i:i + 4] == b'\x45\x55\x8b\xec': return 'marked'
    if b[i:i + 3] == b'\x55\x8b\xec' or b[i:i + 1] == b'\xc8': return 'unmarked'
    if b[:3] == b'\x55\x8b\xec' or b[:1] == b'\xc8': return 'unmarked'
    return 'frameless'

def analyse(fn):
    segs = load(fn)
    calls = []      # (caller_seg, site, target_seg, target_off, kind)
    ptrs = []       # far pointers to code that are not call sites (callbacks/tables)
    for si, s in enumerate(segs):
        code = s['code']; data = s['flags'] & 1
        for t, fl, off, a, b in s['recs']:
            if fl & 3 != 0 or a == 0xff: continue        # imports / ordinal refs
            tgt = segs[a - 1]
            if tgt['flags'] & 1: continue                  # target is data
            add = bool(fl & 4)
            for p in chain(code, off, add):
                if t & 15 == 3:                            # far address seg:off
                    to = b if not add else struct.unpack_from('<H', code, p)[0]
                    op = code[p - 1] if p else 0
                    if not data and op in (0x9a, 0xea):
                        calls.append((si + 1, p, a, to, 'callf' if op == 0x9a else 'jmpf'))
                    else:
                        ptrs.append((si + 1, p, a, to))
                elif t & 15 == 2:                          # selector only
                    if p >= 3 and not data and code[p - 3] in (0x9a, 0xea):
                        to = struct.unpack_from('<H', code, p - 2)[0]
                        calls.append((si + 1, p, a, to, 'callf' if code[p - 3] == 0x9a else 'jmpf'))
                    elif p >= 2:
                        ptrs.append((si + 1, p, a, struct.unpack_from('<H', code, p - 2)[0]))
        # same-segment simulated far calls: push cs ; call near rel16
        if not data:
            for p in range(len(code) - 4):
                if code[p] == 0x0e and code[p + 1] == 0xe8:
                    rel, = struct.unpack_from('<h', code, p + 2)
                    to = (p + 4 + rel) & 0xffff
                    if to < s['len']:
                        calls.append((si + 1, p + 1, si + 1, to, 'pushcs'))
    return segs, calls, ptrs

if __name__ == '__main__':
    segs, calls, ptrs = analyse(sys.argv[1])
    cls = {}
    for c in calls:
        cls[(c[2], c[3])] = classify(segs[c[2] - 1]['code'], c[3])
    pcls = {}
    for p in ptrs:
        pcls[(p[2], p[3])] = classify(segs[p[2] - 1]['code'], p[3])
    cnt = collections.Counter(cls.values())
    print('far-call targets', len(cls), dict(cnt))
    print('far-pointer targets', len(pcls), dict(collections.Counter(pcls.values())))
    kinds = collections.Counter((c[4], cls[(c[2], c[3])]) for c in calls)
    print('call sites by kind', dict(kinds))
    endangered = collections.defaultdict(set)
    for c in calls:
        if cls[(c[2], c[3])] != 'marked' and c[4] != 'jmpf':
            endangered[c[0]].add((c[2], c[3]))
    code_segs = [i + 1 for i, s in enumerate(segs) if not s['flags'] & 1]
    print('code segments', len(code_segs), 'endangered callers', len(endangered))
    print(sorted(endangered))
    tot = sum(segs[s - 1]['len'] for s in endangered)
    print('endangered bytes', tot, 'of code bytes', sum(segs[s - 1]['len'] for s in code_segs))
    unm_ptr = sorted(set((p[2], p[3]) for p in ptrs if pcls[(p[2], p[3])] != 'marked'))
    print('non-marked far-pointer (callback/table) targets', len(unm_ptr), unm_ptr[:40])
    json.dump(dict(endangered={k: sorted(v) for k, v in endangered.items()},
                   unmarked_ptr_targets=unm_ptr,
                   calls=calls, ptrs=ptrs, cls={'%d:%d' % k: v for k, v in cls.items()},
                   pcls={'%d:%d' % k: v for k, v in pcls.items()}),
              open(sys.argv[2], 'w'))
