import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from pcjs_media import *
raw,g=decode_pcjs(open(sys.argv[1],'rb').read())
d=FatDisk(raw)
if len(sys.argv)>2 and sys.argv[2]=='failure':
 d.write_file('WINDOWS/TEST88.COM',bytes.fromhex('b8014ccd21'))
else:
 d.write_file('AUTOEXEC.BAT',b'PATH C:\\;C:\\WINDOWS\r\nCD \\WINDOWS\r\nWIN /R WINMINE.EXE\r\n')
sys.stdout.buffer.write(encode_pcjs(d.to_bytes(),g))
