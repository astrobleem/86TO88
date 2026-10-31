import sys, pathlib
sys.path.insert(0,"/Users/macsd/winmine-hack/src")
from asm88 import assemble

ROOT=pathlib.Path("/Users/macsd/winmine-hack")
tbl=(ROOT/"artifacts/sites-table.bin").read_bytes()
pb=(ROOT/"artifacts/patchbytes.bin").read_bytes()
def db_lines(data):
    out=[]
    for i in range(0,len(data),16):
        out.append(" DB "+",".join(str(b) for b in data[i:i+16]))
    return "\n".join(out)

ASM = r"""
ORG 100h
start: JMP install
 DB 87,77,56,56
; ---------------- INT F8 handler ----------------
sig: DB 87,77,56,56
handler:
 PUSH BP
 MOV BP, SP
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 PUSH CS
 POP DS
 MOV AX, [BP+2]
 SUB AX, 2
 MOV CS:[site_off], AX
 XOR SI, SI
 MOV DI, __NF8M1__
bs_loop:
 CMP SI, DI
 JA notfound
 MOV AX, SI
 ADD AX, DI
 SHR AX, 1
 MOV BX, AX
 SHL BX, 1
 SHL BX, 1
 SHL BX, 1
 MOV DX, [BX+table]
 CMP DX, CS:[site_off]
 JE found
 JB bs_low
 MOV DI, AX
 SUB DI, 1
 JMP bs_loop
bs_low:
 MOV SI, AX
 ADD SI, 1
 JMP bs_loop
notfound:
 MOV AX, CS:[errcnt]
 ADD AX, 1
 MOV CS:[errcnt], AX
 JMP restore_iret
found:
 LEA SI, [BX+table]
 CALL record_trap
 MOV AL, [SI+2]
 CMP AL, 0
 JNE not_push
 JMP do_push
not_push:
 CMP AL, 4
 JNE not_imul
 JMP do_imul
not_imul:
 JMP do_shift
; ---- shift reg,imm / imul ----
do_shift:
 MOV AL, [SI+3]
 MOV CS:[tmp_reg], AL
 CALL slot_ptr
 MOV BX, CS:[tmp_slot]
 MOV AX, SS:[BX]
 MOV CX, [SI+4]
 AND CX, 31
 MOV DL, [SI+2]
 CMP DL, 1
 JE sh_shl
 CMP DL, 2
 JE sh_shr
 SAR AX, CL
 JMP sh_done
sh_shl: SHL AX, CL
 JMP sh_done
sh_shr: SHR AX, CL
sh_done:
 PUSHF
 POP DX
 MOV BX, CS:[tmp_slot]
 MOV SS:[BX], AX
 CALL merge_flags
 CALL set_newip
 JMP restore_iret
do_imul:
 MOV AL, [SI+7]
 MOV CS:[tmp_reg], AL
 CALL slot_ptr
 MOV BX, CS:[tmp_slot]
 MOV AX, SS:[BX]
 MOV BX, [SI+4]
 IMUL1 BX
 PUSHF
 POP DX
 PUSH AX
 MOV AL, [SI+3]
 MOV CS:[tmp_reg], AL
 CALL slot_ptr
 MOV BX, CS:[tmp_slot]
 POP AX
 MOV SS:[BX], AX
 ; flags from IMUL1 are already captured in DX (slot_ptr/MOV preserve DX value)
 CALL merge_flags
 CALL set_newip
 JMP restore_iret
; slot_ptr: CS:[tmp_reg] -> CS:[tmp_slot] (SS-relative ptr in BX on return leaves BX=slot)
slot_ptr:
 XOR BH, BH
 MOV BL, CS:[tmp_reg]
 MOV AL, CS:[BX+regslot]
 CBW
 ADD AX, BP
 MOV CS:[tmp_slot], AX
 MOV BX, AX
 RET
; merge_flags: DX=captured, merge CF/PF/ZF/SF/OF (08C5h) into frame flags [BP+6]
merge_flags:
 MOV AX, [BP+6]
 AND AX, 0F73Ah
 AND DX, 08C5h
 OR AX, DX
 MOV [BP+6], AX
 RET
set_newip:
 MOV AX, CS:[site_off]
 XOR BH, BH
 MOV BL, [SI+6]
 ADD AX, BX
 MOV [BP+2], AX
 RET
; ---- PUSH imm ----
do_push:
 MOV AX, [BP]
 MOV CS:[save_bp], AX
 MOV AX, [SI+4]
 MOV CS:[tmp_imm], AX
 MOV AX, CS:[site_off]
 XOR BH, BH
 MOV BL, [SI+6]
 ADD AX, BX
 MOV CS:[tmp_newip], AX
push_tail:
 MOV CX, [BP+4]
 MOV AX, [BP+6]
 MOV BX, CS:[tmp_imm]
 MOV [BP+6], BX
 MOV [BP+4], AX
 MOV [BP+2], CX
 MOV AX, CS:[tmp_newip]
 MOV [BP], AX
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 MOV BP, CS:[save_bp]
 IRET
restore_iret:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 IRET
; ---------------- INT 3 handler (relocation-resolved push sites) ----------------
; Sites here are `push imm16` whose imm field is a chained internal movable-entry
; relocation field. The buffer patch is a single 0CCh byte; the loader writes the
; resolved word at site+1. We read that word back from the code segment and push it.
int3h:
 PUSH BP
 MOV BP, SP
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 PUSH CS
 POP DS
 MOV AX, [BP+2]
 SUB AX, 1
 MOV CS:[site_off], AX
 XOR SI, SI
 MOV CX, __NCC__
cc_scan:
 MOV AX, CS:[site_off]
 CMP AX, CS:[SI+cctab]
 JE cc_found
 ADD SI, 2
 LOOP cc_scan
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 JMPL CS:[old3]
cc_found:
 CALL record3
 MOV AX, [BP]
 MOV CS:[save_bp], AX
 MOV AX, [BP+4]
 MOV ES, AX
 MOV BX, CS:[site_off]
 INC BX
 MOV AX, ES:[BX]
 MOV CS:[tmp_imm], AX
 MOV AX, CS:[site_off]
 ADD AX, 3
 MOV CS:[tmp_newip], AX
 JMP push_tail
; ---- debug instrumentation (resident) ----
record_trap:
 PUSH AX
 PUSH BX
 MOV AX, CS:[site_off]
 XOR BH, BH
 MOV BL, CS:[ringidx]
 ADD BL, BL
 LEA BX, [BX+ringbuf]
 MOV CS:[BX], AX
 MOV AL, CS:[ringidx]
 ADD AL, 1
 AND AL, 15
 MOV CS:[ringidx], AL
 ADD WORD CS:[trapcnt], 1
 JNB rt_nc
 ADD WORD CS:[trapcnt+2], 1
rt_nc:
 MOV AX, CS:[trapcnt]
 AND AX, 63
 JNZ rt_done
 CALL dump_log
rt_done:
 POP BX
 POP AX
 RET
record3:
 PUSH AX
 PUSH BX
 MOV AX, CS:[site_off]
 XOR BH, BH
 MOV BL, CS:[ring3idx]
 ADD BL, BL
 LEA BX, [BX+ring3]
 MOV CS:[BX], AX
 MOV AL, CS:[ring3idx]
 ADD AL, 1
 AND AL, 7
 MOV CS:[ring3idx], AL
 ADD WORD CS:[int3cnt], 1
 MOV AX, CS:[int3cnt]
 AND AX, 3
 JNZ r3_done
 CALL dump_log
r3_done:
 POP BX
 POP AX
 RET
dump_log:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH DS
 PUSH CS
 POP DS
 MOV DX, logname
 MOV CX, 0
 MOV AH, 3Ch
 INT 21h
 JB dl_done
 MOV BX, AX
 MOV DX, logdata
 MOV CX, 54
 MOV AH, 40h
 INT 21h
 MOV AH, 3Eh
 INT 21h
dl_done:
 POP DS
 POP DX
 POP CX
 POP BX
 POP AX
 RET
logname: DB 84,82,65,80,76,79,71,46,66,73,78,0
ringidx: DB 0
ring3idx: DB 0
logdata:
trapcnt: DW 0,0
int3cnt: DW 0
ringbuf: DW 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
ring3: DW 0,0,0,0,0,0,0,0
regslot: DB 254,250,248,252,0,0,246,244
site_off: DW 0
save_bp: DW 0
tmp_imm: DW 0
tmp_newip: DW 0
tmp_slot: DW 0
tmp_reg: DB 0
errcnt: DW 0
table:
__SITES__
cctab:
__CCTAB__
; ---------------- INT 21 hook ----------------
old21: DD 0
old3: DD 0
pend_open: DB 0
rd_pos: DW 0
rd_poshi: DW 0
rd_buf: DW 0
rd_bufseg: DW 0
rd_found: DB 0
handles:
__HANDLES__
hook21:
 CMP AH, 03Dh
 JNE hk_1
 JMP h_open
hk_1: CMP AH, 03Fh
 JNE hk_2
 JMP h_read
hk_2: CMP AH, 042h
 JNE hk_3
 JMP h_seek
hk_3: CMP AH, 03Eh
 JNE hk_4
 JMP h_close
hk_4: JMPL CS:[old21]
; ---- OPEN ----
h_open:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 MOV BYTE CS:[pend_open], 0
 MOV SI, DX
 XOR CX, CX
fo_len: MOV AL, [SI]
 CMP AL, 0
 JE fo_gotlen
 INC SI
 INC CX
 CMP CX, 128
 JB fo_len
 JMP fo_done
fo_gotlen:
 CMP CX, 11
 JB fo_done
 SUB SI, 11
 XOR BX, BX
fo_cmp: MOV AL, [SI+BX]
 CMP AL, 97
 JB fo_up1
 CMP AL, 122
 JA fo_up1
 SUB AL, 32
fo_up1: CMP AL, CS:[BX+targetname]
 JNE fo_done
 INC BX
 CMP BX, 11
 JB fo_cmp
 MOV BYTE CS:[pend_open], 1
fo_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 PUSHF
 CALLI CS:[old21]
 PUSH BP
 MOV BP, SP
 PUSH AX
 PUSHF
 POP AX
 MOV [BP+6], AX
 POP AX
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 CMP BYTE CS:[pend_open], 0
 JE open_done
 TEST WORD [BP+6], 1
 JNZ open_done
 MOV BX, AX
 CALL find_slot
 CMP BX, 0FFFFh
 JE open_done
 MOV CS:[BX+handles], AX
 MOV WORD CS:[BX+handles+2], 0
 MOV WORD CS:[BX+handles+4], 0
open_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 IRET
; find_slot: returns BX = free slot offset or FFFF (preserves others except BX)
find_slot:
 XOR BX, BX
fs_loop: CMP WORD CS:[BX+handles], 0FFFFh
 JE fs_ret
 ADD BX, 6
 CMP BX, 96
 JB fs_loop
 MOV BX, 0FFFFh
fs_ret: RET
; find_handle: BX=handle in; returns BX=slot offset or FFFF; preserves AX,CX,DX,SI,DI
find_handle:
 PUSH AX
 PUSH SI
 XOR SI, SI
fh_loop: MOV AX, CS:[SI+handles]
 CMP AX, BX
 JE fh_yes
 ADD SI, 6
 CMP SI, 96
 JB fh_loop
 POP SI
 POP AX
 MOV BX, 0FFFFh
 RET
fh_yes: MOV BX, SI
 POP SI
 POP AX
 RET
targetname: DB 87,73,78,77,73,78,69,46,69,88,69
; ---- READ ----
h_read:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 MOV BYTE CS:[rd_found], 0
 CALL find_handle
 CMP BX, 0FFFFh
 JE rd_pre_done
 MOV BYTE CS:[rd_found], 1
 MOV AX, CS:[BX+handles+2]
 MOV CS:[rd_pos], AX
 MOV AX, CS:[BX+handles+4]
 MOV CS:[rd_poshi], AX
 MOV CS:[rd_buf], DX
 MOV AX, DS
 MOV CS:[rd_bufseg], AX
rd_pre_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 CMP BYTE CS:[rd_found], 0
 JE rd_chain
 PUSHF
 CALLI CS:[old21]
 PUSH BP
 MOV BP, SP
 PUSH AX
 PUSHF
 POP AX
 MOV [BP+6], AX
 POP AX
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 TEST WORD [BP+6], 1
 JNZ read_done
 CMP AX, 0
 JE read_done
 ; update tracked pos
 PUSH AX
 MOV BX, WORD CS:[rd_buf]
 ; find handle again: guest BX still handle (saved on stack? BX currently flags) - use saved BX from stack frame [BP-4]
 MOV BX, [BP-4]
 CALL find_handle
 CMP BX, 0FFFFh
 JE rd_upd_done
 POP AX
 PUSH AX
 ADD CS:[BX+handles+2], AX
 JNB rd_upd_done
 ADD WORD CS:[BX+handles+4], 1
rd_upd_done:
 POP AX
 CMP CS:[rd_poshi], 0
 JNE read_done
 ; patch buffer
 MOV BX, CS:[rd_bufseg]
 MOV ES, BX
 MOV CX, __NPATCH__
 XOR SI, SI
 MOV DX, CS:[rd_pos]
rd_loop:
 MOV BX, CS:[SI+patchbytes]
 CMP BX, DX
 JB rd_next
 MOV DI, BX
 SUB DI, DX
 CMP DI, AX
 JAE rd_next
 ADD DI, CS:[rd_buf]
 MOV BL, CS:[SI+patchbytes+2]
 MOV ES:[DI], BL
rd_next:
 ADD SI, 4
 LOOP rd_loop
read_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 IRET
rd_chain: JMPL CS:[old21]
; ---- SEEK ----
h_seek:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 CALL find_handle
 MOV BYTE CS:[rd_found], 0
 CMP BX, 0FFFFh
 JE sk_pre_done
 MOV BYTE CS:[rd_found], 1
sk_pre_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 CMP BYTE CS:[rd_found], 0
 JE sk_chain
 PUSHF
 CALLI CS:[old21]
 PUSH BP
 MOV BP, SP
 PUSH AX
 PUSHF
 POP AX
 MOV [BP+6], AX
 POP AX
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 TEST WORD [BP+6], 1
 JNZ seek_done
 MOV BX, [BP-4]
 PUSH AX
 PUSH DX
 CALL find_handle
 CMP BX, 0FFFFh
 JE sk_upd_done
 POP DX
 POP AX
 MOV CS:[BX+handles+2], AX
 MOV CS:[BX+handles+4], DX
 JMP seek_done2
sk_upd_done:
 POP DX
 POP AX
seek_done2:
seek_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 IRET
sk_chain: JMPL CS:[old21]
; ---- CLOSE ----
h_close:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 CALL find_handle
 MOV BYTE CS:[rd_found], 0
 CMP BX, 0FFFFh
 JE cl_pre_done
 MOV BYTE CS:[rd_found], 1
 MOV WORD CS:[BX+handles], 0FFFFh
cl_pre_done:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 JMPL CS:[old21]
patchbytes:
__PATCH__
resident_end:
; ---------------- install (transient) ----------------
install:
 MOV AX, CS
 MOV DS, AX
 MOV DX, msg_title
 MOV AH, 9
 INT 21h
 ; already installed?
 MOV AH, 35h
 MOV AL, 0F8h
 INT 21h
 CMP BYTE ES:[BX-4], 87
 JNE not_inst
 CMP BYTE ES:[BX-3], 77
 JNE not_inst
 CMP BYTE ES:[BX-2], 56
 JNE not_inst
 CMP BYTE ES:[BX-1], 56
 JE already_p
not_inst:
 ; parse cmdline: PSP:80h
 MOV SI, 81h
 MOV DI, pathbuf
ic_copy: MOV AL, [SI]
 CMP AL, 13
 JE ic_done
 CMP AL, 32
 JE ic_skip
 MOV [DI], AL
 INC DI
ic_skip: INC SI
 CMP SI, 100h
 JB ic_copy
ic_done:
 CMP DI, pathbuf
 JA have_path
 MOV SI, defpath
ic_def: MOV AL, [SI]
 MOV [DI], AL
 INC SI
 INC DI
 CMP AL, 0
 JNE ic_def
 JMP path_ready
have_path: MOV BYTE [DI], 0
path_ready:
 ; open file
 MOV DX, pathbuf
 MOV AX, 3D00h
 INT 21h
 JB badfile
 MOV CS:[vf_handle], AX
 MOV BX, AX
 ; read header 440h bytes into vbuf
 MOV DX, vbuf
 MOV CX, 440h
 MOV AH, 3Fh
 INT 21h
 JB badfile
 CMP WORD [vbuf], 23117
 JNE badfile
 CMP WORD [vbuf+3Ch], 400h
 JNE badfile
 CMP WORD [vbuf+400h], 17742
 JNE badfile
 CMP BYTE [vbuf+43Eh], 10
 JNE badfile
 CMP BYTE [vbuf+43Fh], 3
 JNE badfile
 ; seek to 620h
 MOV BX, CS:[vf_handle]
 MOV AX, 4200h
 XOR CX, CX
 MOV DX, 620h
 INT 21h
 JB badfile
 MOV BX, CS:[vf_handle]
 MOV DX, vbuf
 MOV CX, 11216
 MOV AH, 3Fh
 INT 21h
 JB badfile
 CMP AX, 11216
 JNE badfile
 MOV BX, CS:[vf_handle]
 MOV AH, 3Eh
 INT 21h
 ; verify sites
 XOR SI, SI
 MOV CX, __NF8__
vf_loop:
 MOV BX, [SI+table]
 MOV AL, [BX+vbuf]
 MOV DL, [SI+table+2]
 CMP DL, 0
 JE vf_push
 CMP DL, 4
 JE vf_imul
 ; shift: C1, modrm, count
 CMP AL, 0C1h
 JNE badsite
 MOV AL, [SI+table+3]
 MOV AH, AL
 ; reg field from type: shl=4 shr=5 sar=7 -> use type map via tmp
 MOV DL, [SI+table+2]
 CMP DL, 1
 JE vf_op4
 CMP DL, 2
 JE vf_op5
 MOV DL, 7
 JMP vf_opdone
vf_op4: MOV DL, 4
 JMP vf_opdone
vf_op5: MOV DL, 5
vf_opdone:
 MOV AL, DL
 SHL AL, 1
 SHL AL, 1
 SHL AL, 1
 OR AL, AH
 OR AL, 0C0h
 MOV DL, AL
 MOV AL, [BX+vbuf+1]
 CMP AL, DL
 JNE badsite
 MOV AL, [BX+vbuf+2]
 MOV DL, [SI+table+4]
 CMP AL, DL
 JNE badsite
 JMP vf_next
vf_push:
 MOV DX, [SI+table+4]
 CMP BYTE [SI+table+6], 3
 JE vf_push16
 CMP AL, 106
 JNE badsite
 MOV AL, [BX+vbuf+1]
 CMP AL, DL
 JNE badsite
 JMP vf_next
vf_push16:
 CMP AL, 104
 JNE badsite
 MOV AL, [BX+vbuf+1]
 CMP AL, DL
 JNE badsite
 MOV AL, [BX+vbuf+2]
 CMP AL, DH
 JNE badsite
 JMP vf_next
vf_imul:
 CMP AL, 107
 JNE badsite
 MOV AL, [SI+table+3]
 SHL AL, 1
 SHL AL, 1
 SHL AL, 1
 OR AL, [SI+table+7]
 OR AL, 0C0h
 MOV DL, AL
 MOV AL, [BX+vbuf+1]
 CMP AL, DL
 JNE badsite
 MOV AL, [BX+vbuf+2]
 MOV DL, [SI+table+4]
 CMP AL, DL
 JNE badsite
vf_next:
 ADD SI, 8
 DEC CX
 JNZ vf_loop
 ; verify CC sites: original bytes must be 68 FF FF
__CCVERIFY__
 ; get/set vectors
 MOV AH, 35h
 MOV AL, 21h
 INT 21h
 MOV WORD CS:[old21], BX
 MOV AX, ES
 MOV WORD CS:[old21+2], AX
 MOV DX, hook21
 MOV AX, 2521h
 INT 21h
 MOV DX, handler
 MOV AX, 25F8h
 INT 21h
 MOV AH, 35h
 MOV AL, 3
 INT 21h
 MOV WORD CS:[old3], BX
 MOV AX, ES
 MOV WORD CS:[old3+2], AX
 MOV DX, int3h
 MOV AX, 2503h
 INT 21h
 CALL dump_log
 MOV DX, msg_ok
 MOV AH, 9
 INT 21h
 MOV DX, resident_end
 MOV CL, 4
 SHR DX, CL
 ADD DX, 17
 MOV AX, 3100h
 INT 21h
already_p:
 MOV DX, msg_already
 MOV AH, 9
 INT 21h
 MOV AX, 4C00h
 INT 21h
badfile:
 MOV DX, msg_bad
 MOV AH, 9
 INT 21h
 MOV AX, 4C02h
 INT 21h
badsite:
 MOV DX, msg_site
 MOV AH, 9
 INT 21h
 MOV AX, 4C03h
 INT 21h
msg_title: DB 87,77,56,56,32,45,32,111,114,105,103,105,110,97,108,32,87,73,78,77,73,78,69,32,56,48,56,56,32,98,114,105,100,103,101,13,10,36
msg_ok: DB 73,110,115,116,97,108,108,101,100,46,32,87,73,78,77,73,78,69,46,69,88,69,32,118,101,114,105,102,105,101,100,32,40,50,55,55,55,54,66,32,112,105,110,110,101,100,32,105,109,97,103,101,41,46,13,10,36
msg_already: DB 65,108,114,101,97,100,121,32,105,110,115,116,97,108,108,101,100,46,13,10,36
msg_bad: DB 69,82,82,79,82,58,32,116,97,114,103,101,116,32,110,111,116,32,102,111,117,110,100,32,111,114,32,78,69,32,104,101,97,100,101,114,32,109,105,115,109,97,116,99,104,46,13,10,36
msg_site: DB 69,82,82,79,82,58,32,99,111,100,101,32,115,105,116,101,32,109,105,115,109,97,116,99,104,32,45,32,110,111,116,32,116,104,101,32,112,105,110,110,101,100,32,50,55,55,55,54,66,32,111,114,105,103,105,110,97,108,46,13,10,36
defpath: DB 87,73,78,77,73,78,69,46,69,88,69,0
pathbuf: DB 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
vf_handle: DW 0
vbuf: DB 0
"""

import struct as _struct
ccb=(ROOT/"artifacts/cc-sites.bin").read_bytes()
cc_offs=[_struct.unpack_from("<H",ccb,i)[0] for i in range(0,len(ccb),2)]
ccv=[]
for _off in cc_offs:
    ccv += [f" MOV BX, {_off}",
            " CMP BYTE [BX+vbuf], 104",
            " JNE badsite",
            " INC BX",
            " CMP BYTE [BX+vbuf], 255",
            " JNE badsite",
            " INC BX",
            " CMP BYTE [BX+vbuf], 255",
            " JNE badsite"]
ASM = ASM.replace("__SITES__", db_lines(tbl))
ASM = ASM.replace("__CCTAB__", db_lines(ccb))
ASM = ASM.replace("__NF8M1__", str(len(tbl)//8 - 1))
ASM = ASM.replace("__NF8__", str(len(tbl)//8))
ASM = ASM.replace("__NCC__", str(len(cc_offs)))
ASM = ASM.replace("__CCVERIFY__", "\n".join(ccv))
ASM = ASM.replace("__PATCH__", db_lines(pb))
ASM = ASM.replace("__NPATCH__", str(len(pb)//4))
handles_db = "\n".join(" DB "+",".join(str(b) for b in b"\xff\xff\x00\x00\x00\x00") for _ in range(16))
ASM = ASM.replace("__HANDLES__", handles_db)

code, labels = assemble(ASM, org=0x100)
out = ROOT/"artifacts/WM88DBG.COM"
out.write_bytes(code)
import json as _json
(ROOT/"artifacts/tsr-labels-dbg.json").write_text(_json.dumps({k: labels[k] for k in ("errcnt","handles","handler","hook21","resident_end","old21","rd_found","int3h","old3","cctab")}))
print("WM88DBG.COM", len(code), "resident_end", hex(labels['resident_end']), "handler", hex(labels['handler']), "hook", hex(labels['hook21']), "table", hex(labels['table']), "errcnt", hex(labels['errcnt']), "handles", hex(labels['handles']))
# Verify no forbidden 186 opcodes in our own code (except inside data tables)
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
bad=[]
# disassemble only up to table
for ins in md.disasm(code[:labels['table']-0x100], 0x100):
    raw=bytes(ins.bytes)
    if raw[0] in (0x68,0x6A,0x6B,0xC0,0xC1): bad.append((hex(ins.address),ins.mnemonic,ins.op_str))
print("186 opcodes in TSR code region:", bad)
