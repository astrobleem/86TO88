"""Render PCjs EGA mode 10h snapshots, not browser screenshots.

Four plane bytes are packed in each PCjs adwMemory dword. Register 13h=40
means 80 bytes/scanline; display start zero. Reject other display layouts.
"""
import json,pathlib,sys
from PIL import Image
for name in sys.argv[1:]:
 p=pathlib.Path(name);j=json.loads(p.read_text());c=j['crtc']
 assert j.get('videoMode',16)==16,'Only EGA mode 10h graphics is supported'
 assert c[12]==0 and c[13]==0 and c[19]==40,'Unsupported display layout'
 im=Image.new('RGB',(640,350));px=im.load()
 for y in range(350):
  for x in range(640):
   v=j['memory'][y*80+x//8] or 0;bit=7-x%8
   index=sum(((v>>(k*8+bit))&1)<<k for k in range(4))
   color=j['atc'][index]
   px[x,y]=tuple(170*((color>>b)&1)+85*((color>>(b+3))&1) for b in (2,1,0))
 im.save(p.with_suffix('.png'))
 print(p.with_suffix('.png'))
