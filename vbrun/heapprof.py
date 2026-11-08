import sys
L=[l for l in open(sys.argv[1],errors='ignore') if l.startswith('XW ') or l.startswith('XR ')]
pend={}; allocs={}; order=[]
for l in L:
    p=l.split()
    if len(p)<4: continue
    if p[0]=='XW':
        if len(p)<11: continue
        pend[p[1]]=(p[3],p[5:11])
    else:
        nm=p[1]; ax=p[3][3:]
        if nm not in pend: continue
        caller,a=pend.pop(nm)
        if nm=='GA' and caller.endswith(':004D'):
            allocs[ax]=['alloc %s'%a[0]]; order.append(ax)
        elif nm=='GRA' and caller.endswith(':00F1'):
            h=a[3]; allocs.setdefault(h,['?']).append('grow%s%s'%(a[1],'' if ax!='0000' else '!FAIL'))
            if h not in order: order.append(h)
        elif nm=='GF' and a[0] in allocs: allocs[a[0]].append('free')
for h in order: print(h,' '.join(allocs[h]))
