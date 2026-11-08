import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heapwalk import *
def segof(m,bl,t):
    for b in bl:
        if b['seg']<=t<b['seg']+max(b['size'],1):
            try: nm=modname(m,b['owner'])
            except Exception: nm='%04x'%b['owner']
            ms=module_segs(m,b['owner']) or []
            sn=[s['num'] for s in ms if s['handle'] in (b['handle'],b['seg'])]
            return '%04x: blk %04x+%x %s seg%s L%d'%(t,b['seg'],(t-b['seg'])*16,nm,sn,b['lock'])
    return '%04x: ?'%t
if __name__=='__main__':
    m=open(sys.argv[1],'rb').read(); bl=walk(m,find_heap(m))
    for a in sys.argv[2:]: print(segof(m,bl,int(a,16)))
