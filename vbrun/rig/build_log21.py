# build_log21.py OUT.COM : INT 21h open/read/seek logger TSR (writes to port 0xE9)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src'))
from asm88 import assemble
ASM = r"""
ORG 100h
 JMP install
old21: DD 0
pc: PUSH DX
 MOV DX, 0E9h
 OUT DX, AL
 POP DX
 RET
phex: PUSH AX
 SHR AL, 1
 SHR AL, 1
 SHR AL, 1
 SHR AL, 1
 CALL pnib
 POP AX
 AND AL, 0Fh
pnib: CMP AL, 10
 JB pn1
 ADD AL, 7
pn1: ADD AL, 48
 JMP pc
pz: MOV SI, DX
pz1: LODSB
 OR AL, AL
 JE pz2
 CALL pc
 JMP pz1
pz2: MOV AL, 10
 JMP pc
tag: CALL pc
 MOV AL, 32
 JMP pc
h21: PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DS
 CMP AH, 3Dh
 JNE n1
 MOV AL, 'O'
 CALL tag
 CALL pz
 JMP fin
n1: CMP AH, 4Bh
 JNE n2
 MOV AL, 'X'
 CALL tag
 CALL pz
 JMP fin
n2: CMP AH, 4Ch
 JNE n3
 MOV AL, 'T'
 CALL tag
 POP DS
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 PUSH AX
 CALL phex
 MOV AL, 10
 CALL pc
 POP AX
 JMPL CS:[old21]
n3: CMP AH, 9
 JNE n4
 MOV AL, 'S'
 CALL tag
 MOV SI, DX
ps1: LODSB
 CMP AL, '$'
 JE ps2
 CALL pc
 JMP ps1
ps2: MOV AL, 10
 CALL pc
 JMP fin
n4: CMP AH, 40h
 JNE n5
 CMP BX, 2
 JA tfin
 CMP BX, 1
 JB tfin
 CMP CX, 200
 JA tfin
 JCXZ tfin
 MOV AL, 'W'
 CALL tag
 MOV SI, DX
pw1: LODSB
 CALL pc
 LOOP pw1
 MOV AL, 10
 CALL pc
tfin: JMP fin
n5: CMP AH, 3Fh
 JNE n6
 MOV AL, 'R'
 CALL tag
 MOV AL, BL
 CALL phex
 MOV AL, 32
 CALL pc
 MOV AL, CH
 CALL phex
 MOV AL, CL
 CALL phex
 MOV AL, 10
 CALL pc
 JMP fin
n6: CMP AH, 42h
 JNE n7
 MOV AL, 'P'
 CALL tag
 MOV AL, BL
 CALL phex
 MOV AL, 32
 CALL pc
 MOV AL, CH
 CALL phex
 MOV AL, CL
 CALL phex
 MOV AL, DH
 CALL phex
 MOV AL, DL
 CALL phex
 MOV AL, 10
 CALL pc
n7: CMP AH, 3Eh
 JNE n8
 MOV AL, 'C'
 CALL tag
 MOV AL, BL
 CALL phex
 MOV AL, 10
 CALL pc
n8: JMP fin
fin: POP DS
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
post: JMPL CS:[old21]
post2: CMP AH, 3Fh
 JE chk
 CMP AH, 3Dh
 JE chk
 CMP AH, 48h
 JE chk
 CMP AH, 4Ah
 JE chk
 CMP AH, 4Bh
 JE chk
 CMP AH, 42h
 JE chk
 JMPL CS:[old21]
sah: DB 0
chk: MOV CS:[sah], AH
 PUSHF
 CALLI CS:[old21]
 PUSHF
 JNC nolog
 PUSH AX
 PUSH BX
 MOV AL, 'E'
 CALL tag
 MOV AL, CS:[sah]
 CALL phex
 MOV AL, 32
 CALL pc
 POP BX
 POP AX
 PUSH AX
 MOV AL, AH
 CALL phex
 POP AX
 CALL phex
 MOV AL, 10
 CALL pc
nolog: POPF
 RETF 2
install: MOV AX, 3521h
 INT 21h
 MOV [old21], BX
 MOV AX, ES
 MOV [old21+2], AX
 MOV DX, h21
 MOV AX, 2521h
 INT 21h
 MOV DX, install
 INT 27h
"""
code,_=assemble(ASM,org=0x100)
open(sys.argv[1],'wb').write(code); print(len(code))
