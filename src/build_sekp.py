import sys, pathlib
sys.path.insert(0, "/Users/macsd/winmine-hack/src")
from asm88 import assemble
ASM = r"""
ORG 100h
start:
 MOV AX, CS
 MOV DS, AX
 MOV DX, fname
 MOV AX, 3D00h
 INT 21h
 JB fail
 MOV [handle], AX
 ; seek abs 43Eh
 MOV BX, AX
 MOV AX, 4200h
 XOR CX, CX
 MOV DX, 43Eh
 INT 21h
 JB fail
 ; read 2
 MOV BX, [handle]
 MOV DX, buf
 MOV CX, 2
 MOV AH, 3Fh
 INT 21h
 JB fail
 ; seek cur +2C0h
 MOV BX, [handle]
 MOV AX, 4201h
 XOR CX, CX
 MOV DX, 2C0h
 INT 21h
 JB fail
 CALL prhex16
 MOV DL, 32
 MOV AH, 2
 INT 21h
 ; read 4
 MOV BX, [handle]
 MOV DX, buf
 MOV CX, 4
 MOV AH, 3Fh
 INT 21h
 JB fail
 MOV BX, buf
 MOV AL, [BX]
 CALL prhex8
 MOV AL, [BX+1]
 CALL prhex8
 MOV AL, [BX+2]
 CALL prhex8
 MOV AL, [BX+3]
 CALL prhex8
 MOV DL, 13
 MOV AH, 2
 INT 21h
 MOV DL, 10
 MOV AH, 2
 INT 21h
 MOV AX, 4C00h
 INT 21h
fail:
 MOV DX, msg_fail
 MOV AH, 9
 INT 21h
 MOV AX, 4C01h
 INT 21h
prhex16: ; AX
 PUSH AX
 MOV AL, AH
 CALL prhex8
 POP AX
 CALL prhex8
 RET
prhex8: ; AL
 PUSH AX
 PUSH AX
 MOV CL, 4
 SHR AL, CL
 ADD AL, 48
 CMP AL, 57
 JBE ph1
 ADD AL, 7
ph1:
 MOV DL, AL
 MOV AH, 2
 INT 21h
 POP AX
 AND AL, 15
 ADD AL, 48
 CMP AL, 57
 JBE ph2
 ADD AL, 7
ph2:
 MOV DL, AL
 MOV AH, 2
 INT 21h
 POP AX
 RET
fname: DB 87,73,78,77,73,78,69,46,69,88,69,0
msg_fail: DB 83,69,69,75,70,65,73,76,13,10,36
handle: DW 0
buf: DB 0,0,0,0,0,0,0,0
"""
code, labels = assemble(ASM, org=0x100)
pathlib.Path("/Users/macsd/winmine-hack/artifacts/SEKP.COM").write_bytes(code)
print("SEKP.COM", len(code))
