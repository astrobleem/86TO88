import sys, pathlib
sys.path.insert(0,"/Users/macsd/winmine-hack/src")
from asm88 import assemble
ASM=r"""
ORG 100h
start:
 MOV AX, CS
 MOV DS, AX
 ; open WINMINE.EXE
 MOV DX, fname
 MOV AX, 3D00h
 INT 21h
 JB fail_open
 MOV [handle], AX
 ; seek 43Eh read 2
 MOV BX, [handle]
 MOV AX, 4200h
 XOR CX, CX
 MOV DX, 43Eh
 INT 21h
 JB fail_s1
 MOV BX, [handle]
 MOV DX, buf
 MOV CX, 2
 MOV AH, 3Fh
 INT 21h
 JB fail_r1
 CMP BYTE [buf], 0
 JNE fail_ver
 CMP BYTE [buf+1], 3
 JNE fail_ver
 ; seek 620h read 256
 MOV BX, [handle]
 MOV AX, 4200h
 XOR CX, CX
 MOV DX, 620h
 INT 21h
 JB fail_s1
 MOV BX, [handle]
 MOV DX, buf
 MOV CX, 256
 MOV AH, 3Fh
 INT 21h
 JB fail_r2
 ; site 40h: CD F8 90
 CMP BYTE [buf+40h], 0CDh
 JNE fail_site
 CMP BYTE [buf+41h], 0F8h
 JNE fail_site
 CMP BYTE [buf+42h], 90h
 JNE fail_site
 ; site 43h: CD F8 (push 0, 2 bytes)
 CMP BYTE [buf+43h], 0CDh
 JNE fail_site
 CMP BYTE [buf+44h], 0F8h
 JNE fail_site
 MOV DX, msg_pass
 MOV AH, 9
 INT 21h
 MOV AX, 4C00h
 INT 21h
fail_open: MOV DX, msg_open
 JMP prfail
fail_ver: MOV DX, msg_ver
 JMP prfail
fail_site: MOV DX, msg_site
 JMP prfail
fail_s1: MOV DX, msg_s1
 JMP prfail
fail_r1: MOV DX, msg_r1
 JMP prfail
fail_s2: MOV DX, msg_s2
 JMP prfail
fail_r2: MOV DX, msg_r2
 JMP prfail
fail: MOV DX, msg_fail
prfail:
 MOV AH, 9
 INT 21h
 MOV AX, 4C01h
 INT 21h
fname: DB 87,77,46,69,88,69,0
msg_pass: DB 82,69,65,68,80,65,83,83,13,10,36
msg_open: DB 82,69,65,68,70,65,73,76,32,79,80,69,78,13,10,36
msg_ver: DB 82,69,65,68,70,65,73,76,32,86,69,82,13,10,36
msg_site: DB 82,69,65,68,70,65,73,76,32,83,73,84,69,13,10,36
msg_s1: DB 70,49,13,10,36
msg_r1: DB 70,50,13,10,36
msg_s2: DB 70,51,13,10,36
msg_r2: DB 70,52,13,10,36
msg_fail: DB 82,69,65,68,70,65,73,76,13,10,36
handle: DW 0
buf: DB 0
"""
code,labels=assemble(ASM, org=0x100)
pathlib.Path("/Users/macsd/winmine-hack/artifacts/RT2.COM").write_bytes(code)
print("READTEST.COM", len(code))
