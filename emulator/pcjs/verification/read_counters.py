"""Read reference-window counters by exact original-bitmap bright-pixel match.

No OCR guessing, invented digits, or guest changes. The pinned WINMINE resource
is read from the PRIVATE prepared disk; no Microsoft bitmap is redistributed.
Requires Pillow. Coordinates are for the unchanged 640x350 reference window.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from pcjs_media import decode_pcjs,FatDisk
SPEC='633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b'

def templates(specimen):
    if hashlib.sha256(specimen).hexdigest()!=SPEC:raise ValueError('Unrecognized WINMINE specimen')
    ne=struct.unpack_from('<I',specimen,0x3c)[0]
    if specimen[ne:ne+2]!=b'NE':raise ValueError('Missing NE header')
    p=ne+struct.unpack_from('<H',specimen,ne+0x24)[0];shift=struct.unpack_from('<H',specimen,p)[0];p+=2
    dib=None
    while True:
        typ,count=struct.unpack_from('<HH',specimen,p);p+=8
        if not typ:break
        for _ in range(count):
            off,size,flags,nid,handle,usage=struct.unpack_from('<6H',specimen,p);p+=12
            if typ==0x8002 and nid==0x81a4:dib=specimen[off<<shift:(off+size)<<shift]
    if dib is None:raise ValueError('Missing original digit bitmap')
    header,width,height,planes,bits=struct.unpack_from('<IiiHH',dib)
    if (header,width,height,planes,bits)!=(40,13,276,1,4):raise ValueError('Unexpected digit bitmap geometry')
    palette=[tuple(reversed(dib[40+4*i:43+4*i])) for i in range(16)]
    rows=[]
    for y in range(height):
        start=104+(height-1-y)*8
        rows.append([palette[(dib[start+x//2]>>(4 if x%2==0 else 0))&15]==(255,0,0) for x in range(width)])
    masks=[sum(rows[i*23:(i+1)*23],[]) for i in range(12)]
    return list(zip(['-',' ']+list('9876543210'),masks))

def read_frame(path,patterns):
    im=Image.open(path).convert('RGB')
    if im.size!=(640,350):raise ValueError('Expected native 640x350 EGA capture')
    results=[]
    for x in (96,109,122,173,186,199):
        patch=im.crop((x,95,x+13,118)).tobytes();pixels=[patch[i:i+3]==b'\xff\x00\x00' for i in range(0,len(patch),3)]
        ranked=sorted((sum(a!=b for a,b in zip(pixels,mask)),symbol) for symbol,mask in patterns)
        if ranked[0][0] or ranked[0][1]==' ' or ranked[0][0]==ranked[1][0]:raise ValueError(f'No unique exact numeric glyph match in {path} at x={x}: {ranked[:2]}')
        results.append(ranked[0][1])
    return {'file':str(path),'mine_counter':''.join(results[:3]),'timer':''.join(results[3:]),'mismatching_bright_pixels':0,'method':'exact original WINMINE digit resource bright-red masks; fixed reference window coordinates'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('private_fixture');p.add_argument('captures',nargs='+');args=p.parse_args()
    raw,_=decode_pcjs((Path(args.private_fixture)/'disk.json').read_bytes());patterns=templates(FatDisk(raw).read_file('WINDOWS/WINMINE.EXE'))
    print(json.dumps([read_frame(path,patterns) for path in args.captures],indent=2))
