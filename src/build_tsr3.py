"""WM88 v3: library-driven bridge TSR.  Output: artifacts/WM88X3.COM
The TSR carries no game data.  Each patched module lives in the library as its own file
LIB\\BASE.W8x (x = first letter of the module extension, e.g. WINMINE.W8E, WEPUTIL.W8D).
When Windows opens a file, the TSR looks it up in the library, loads that module's table into a
small arena (exact name + size must match) and patches reads from that handle.  Files with no
library entry are never touched.  Tables are freed when the process that loaded them terminates.
Module image (.W8x): 'W8M1', nsites w, nconf b, pad b, vtab[8]{start w,cnt w} (8..39),
 module record x22 @40 {namelen b, name[12], dir b, size lo w, hi w, crc lo w, hi w},
 window @62 {lo_page w, hi_page w} (file offset>>8 of patched bytes), sites @66 x12:
 {segoff w, type b, reg b, imm w, len b, srcreg b, foff_lo w, foff_hi b, vec b}, then nconf x word: crc-lo ids of
 library modules that clash with this one (the TSR drops those when this module loads)
 types 0 push,1 shl,2 shr,3 sar,4 imul rr,5 cc-push,6 cc-leave,7 imul r,[bp+d],imm8,
 8 static byte patch (imm lo/hi = replacement bytes, len 1|2, segoff FFFFh, never trapped)
Vector keys (vec,segoff) are unique library-wide (same key only for identical semantics).
"""
import sys, pathlib, struct
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from asm88 import assemble
ROOT = pathlib.Path(__file__).resolve().parent.parent
def dbl(data):
    return "\n".join(" DB " + ",".join(str(b) for b in data[i:i+16]) for i in range(0, len(data), 16))
def dbs(s): return " DB " + ",".join(str(ord(c)) for c in s) + ",13,10,36"

ASM = r"""
ORG 100h
start: JMP install
 DB 87,77,56,56
sig: DB 87,77,56,56
stub0: MOVB CS:[vecidx], 0
 JMP handler
stub1: MOVB CS:[vecidx], 1
 JMP handler
stub2: MOVB CS:[vecidx], 2
 JMP handler
stub3: MOVB CS:[vecidx], 3
 JMP handler
stub4: MOVB CS:[vecidx], 4
 JMP handler
stub5: MOVB CS:[vecidx], 5
 JMP handler
stub6: MOVB CS:[vecidx], 6
 JMP handler
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
 MOV [site_off], AX
__DIAG__
 CALL lookup
 CMP BX, 0FFFFh
 JNE found
notfound:
__DIAGNF__
 MOV AX, [errcnt]
 ADD AX, 1
 MOV [errcnt], AX
 JMP restore_iret
found:
 MOV SI, BX
 MOV AL, [SI+2]
 CMP AL, 0
 JNE not_push
 JMP do_push
not_push:
 CMP AL, 4
 JNE not_imul
 JMP do_imul
not_imul:
 CMP AL, 7
 JNE not_imulm
 JMP do_imulm
not_imulm:
 CMP AL, 9
 JNE not_imulw
 JMP do_imulw
not_imulw:
 JMP do_shift
; lookup: vecidx + site_off -> BX = entry ptr or FFFF ; clobbers AX,CX,DX,SI,DI
lookup:
 MOV BYTE [lk_i], 0
lk_slot:
 MOV AL, [lk_i]
 CMP AL, 12
 JAE lk_all
 XOR AH, AH
 MOV BX, AX
 MOV AX, [BX+slots]
 ADD BYTE [lk_i], 2
 CMP AX, 0
 JE lk_slot
 MOV [cur_img], AX
 CALL lk_one
 CMP BX, 0FFFFh
 JE lk_slot
 RET
lk_all:
 MOV BX, 0FFFFh
 RET
lk_one:
 XOR BH, BH
 MOV BL, [vecidx]
 SHL BX, 1
 SHL BX, 1
 ADD BX, [cur_img]
 MOV SI, [BX+8]
 MOV AX, [BX+10]
 CMP AX, 0
 JE lk_none
 MOV DI, SI
 ADD DI, AX
 DEC DI
 MOV AX, SI
 CALL ent_addr
 MOV AX, [BX]
 CMP AX, [site_off]
 JA lk_none
 MOV AX, DI
 CALL ent_addr
 MOV AX, [BX]
 CMP AX, [site_off]
 JB lk_none
lk_loop:
 CMP SI, DI
 JA lk_none
 MOV AX, SI
 ADD AX, DI
 SHR AX, 1
 MOV CX, AX
 CALL ent_addr
 MOV AX, [BX]
 CMP AX, [site_off]
 JE lk_hit
 JB lk_low
 MOV DI, CX
 SUB DI, 1
 JMP lk_loop
lk_low:
 MOV SI, CX
 ADD SI, 1
 JMP lk_loop
lk_none:
 MOV BX, 0FFFFh
lk_hit:
 RET
; ent_addr: AX=index -> BX=entry pointer (x12) in image cur_img ; clobbers DX
ent_addr:
 MOV BX, AX
 SHL BX, 1
 SHL BX, 1
 MOV DX, BX
 SHL BX, 1
 ADD BX, DX
 ADD BX, [cur_img]
 ADD BX, 66
 RET
do_shift:
 MOV AL, [SI+3]
 CMP AL, 8
 JB sh_word
 JMP do_shiftb
sh_word:
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 MOV AX, SS:[BX]
 MOV CX, [SI+4]
 AND CX, 31
 JE sh_nop
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
 MOV BX, [tmp_slot]
 MOV SS:[BX], AX
 CALL merge_flags
 CALL set_newip
 JMP restore_iret
sh_nop:
 CALL set_newip
 JMP restore_iret
do_shiftb:
 AND AL, 7
 MOV [tmp_hi], AL
 AND AL, 3
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 CMP BYTE [tmp_hi], 4
 JB sb_lo
 INC BX
sb_lo:
 MOV AL, SS:[BX]
 MOV CX, [SI+4]
 AND CX, 31
 JE sh_nop
 MOV DL, [SI+2]
 CMP DL, 1
 JE sb_shl
 CMP DL, 2
 JE sb_shr
 SAR AL, CL
 JMP sb_done
sb_shl: SHL AL, CL
 JMP sb_done
sb_shr: SHR AL, CL
sb_done:
 PUSHF
 POP DX
 MOV SS:[BX], AL
 CALL merge_flags
 CALL set_newip
 JMP restore_iret
do_imul:
 MOV AL, [SI+7]
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 MOV AX, SS:[BX]
 MOV BX, [SI+4]
 JMP imul_tail
do_imulw:
 MOV BYTE [tmp_w], 1
 JMP imulm_body
do_imulm:
 MOV BYTE [tmp_w], 0
imulm_body:
 MOV AL, [SI+6]
 MOV CL, 4
 SHR AL, CL
 MOV [tmp_ea], AL
 XOR DX, DX
 CMP AL, 8
 JE ea_disp
 XOR BH, BH
 MOV BL, AL
 MOV AL, [BX+eab1]
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 MOV DX, SS:[BX]
 MOV BL, [tmp_ea]
 XOR BH, BH
 MOV AL, [BX+eab2]
 CMP AL, 0FFh
 JE ea_disp
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 ADD DX, SS:[BX]
ea_disp:
 ADD DX, [SI+4]
 MOV AX, [BP-14]
 MOV BL, [tmp_ea]
 CMP BL, 2
 JE ea_ss
 CMP BL, 3
 JE ea_ss
 CMP BL, 6
 JNE ea_seg
ea_ss:
 MOV AX, SS
ea_seg:
 MOV ES, AX
 MOV BX, DX
 MOV AX, ES:[BX]
 MOV DL, [tmp_w]
 CMP DL, 0
 JE im_b8
 PUSH AX
 MOV AX, [BP+4]
 MOV ES, AX
 MOV BL, [SI+6]
 AND BL, 15
 XOR BH, BH
 ADD BX, [site_off]
 SUB BX, 2
 MOV BX, ES:[BX]
 POP AX
 JMP imul_tail
im_b8:
 MOV BL, [SI+7]
 MOV BH, 0
 TEST BX, 80h
 JZ im_pos
 MOV BH, 0FFh
im_pos:
imul_tail:
 IMUL1 BX
 PUSHF
 POP DX
 PUSH AX
 MOV AL, [SI+3]
 MOV [tmp_reg], AL
 CALL slot_ptr
 MOV BX, [tmp_slot]
 POP AX
 MOV SS:[BX], AX
 CALL merge_flags
 CALL set_newip
 JMP restore_iret
slot_ptr:
 XOR BH, BH
 MOV BL, [tmp_reg]
 MOV AL, [BX+regslot]
 CBW
 ADD AX, BP
 MOV [tmp_slot], AX
 MOV BX, AX
 RET
merge_flags:
 MOV AX, [BP+6]
 AND AX, 0F73Ah
 AND DX, 08C5h
 OR AX, DX
 MOV [BP+6], AX
 RET
set_newip:
 MOV AX, [site_off]
 XOR BH, BH
 MOV BL, [SI+6]
 AND BL, 15
 ADD AX, BX
 MOV [BP+2], AX
 RET
do_push:
 MOV AX, [BP]
 MOV [save_bp], AX
 MOV AX, [SI+4]
 MOV [tmp_imm], AX
 MOV AX, [site_off]
 XOR BH, BH
 MOV BL, [SI+6]
 ADD AX, BX
 MOV [tmp_newip], AX
push_tail:
 MOV CX, [BP+4]
 MOV AX, [BP+6]
 MOV BX, [tmp_imm]
 MOV [BP+6], BX
 MOV [BP+4], AX
 MOV [BP+2], CX
 MOV AX, [tmp_newip]
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
; ---------------- INT 3: relocation-resolved push (5) and LEAVE (6) ----------------
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
 MOV BYTE [vecidx], 7
 MOV AX, [BP+2]
 SUB AX, 1
 MOV [site_off], AX
 CALL lookup
 CMP BX, 0FFFFh
 JE cc_chain
 MOV SI, BX
 MOV AX, [BP+4]
 MOV ES, AX
 MOV BX, [site_off]
 CMP BYTE ES:[BX], 0CCh
 JNE cc_chain
 MOV DI, 3
 CMP BYTE [SI+2], 5
 JE cc_ctx
 MOV DI, 1
cc_ctx:
 MOV AL, [SI+3]
 CMP ES:[BX+DI], AL
 JNE cc_chain
 MOV AL, [SI+7]
 CMP AL, 0
 JE cc_ok
 INC DI
 CMP ES:[BX+DI], AL
 JNE cc_chain
cc_ok:
 CMP BYTE [SI+2], 5
 JE cc_found
 JMP do_leave
cc_chain:
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
 MOV AX, [BP]
 MOV [save_bp], AX
 INC BX
 MOV AX, ES:[BX]
 MOV [tmp_imm], AX
 MOV AX, [site_off]
 ADD AX, 3
 MOV [tmp_newip], AX
 JMP push_tail
; LEAVE: SP=BPg; BP=pop.  Rebuild the IRET frame at BPg-4 and switch SP to it.
do_leave:
 MOV AX, [BP]
 MOV BX, AX
 MOV CX, SS:[BX]
 MOV [tmp_newbp], CX
 MOV DX, [site_off]
 INC DX
 MOV CX, [BP+4]
 MOV SI, [BP+6]
 SUB AX, 4
 MOV BX, AX
 MOV SS:[BX], DX
 MOV SS:[BX+2], CX
 MOV SS:[BX+4], SI
 MOV [tmp_sp], BX
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 POP BP
 MOV BP, CS:[tmp_newbp]
 MOV SP, CS:[tmp_sp]
 IRET
regslot: DB 254,250,248,252,0,0,246,244
eab1: DB 3,3,5,5,6,7,5,3
eab2: DB 6,7,6,7,255,255,255,255
tmp_ea: DB 0
tmp_w: DB 0
tmp_hi: DB 0
vecidx: DB 0
v20: DB 0
site_off: DW 0
save_bp: DW 0
tmp_imm: DW 0
tmp_newip: DW 0
tmp_newbp: DW 0
tmp_sp: DW 0
tmp_slot: DW 0
tmp_reg: DB 0
errcnt: DW 0
rd_ps: DW 0
nmod: DB 0
arena_top: DW 0
arena_end: DW 0
app_ds: DW 0
rd_img: DW 0
cur_img: DW 0
lk_i: DB 0
tl_h: DW 0
tl_cap: DW 0
tl_len: DW 0
tl_try: DB 0
tl_cf: DW 0
libend: DW 0
slots: DW 0,0,0,0,0,0
slotpsp: DW 0,0,0,0,0,0
lpath:
__LPATH__
lpath_max: DB 0
old21: DD 0
old3: DD 0
pend_mod: DB 0
pend_rec: DW 0
o_end: DW 0
o_len: DW 0
o_rec: DW 0
o_i: DB 0
rd_pos: DW 0
rd_poshi: DB 0
rd_modsh: DB 0
rd_buf: DW 0
rd_bufseg: DW 0
rd_n: DW 0
rd_found: DB 0
vf_ok: DB 0
cur_psp: DW 0
; handle records x12: {handle w (FFFF free), pos_lo w, pos_hi b, mod b, psp w}
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
hk_4: CMP AH, 04Ch
 JE h_term
 CMP AH, 0
 JE h_term
 JMPL CS:[old21]
h_term:
 PUSH AX
 PUSH BX
 PUSH CX
 PUSH DX
 PUSH SI
 PUSH DI
 PUSH DS
 PUSH ES
 CALL get_psp
 MOV CS:[cur_psp], AX
 XOR SI, SI
tm_loop:
 CMP WORD CS:[SI+handles], 0FFFFh
 JE tm_next
 MOV AX, CS:[SI+handles+6]
 CMP AX, CS:[cur_psp]
 JNE tm_next
 MOV WORD CS:[SI+handles], 0FFFFh
tm_next:
 ADD SI, 8
 CMP SI, 96
 JB tm_loop
 XOR SI, SI
tm_s:
 CMP WORD CS:[SI+slots], 0
 JE tm_sn
 MOV AX, CS:[SI+slotpsp]
 CMP AX, CS:[cur_psp]
 JNE tm_sn
 MOV WORD CS:[SI+slots], 0
tm_sn:
 ADD SI, 2
 CMP SI, 12
 JB tm_s
 XOR SI, SI
tm_a:
 CMP WORD CS:[SI+slots], 0
 JNE tm_keep
 ADD SI, 2
 CMP SI, 12
 JB tm_a
 MOV AX, arena
 MOV CS:[arena_top], AX
tm_keep:
 POP ES
 POP DS
 POP DI
 POP SI
 POP DX
 POP CX
 POP BX
 POP AX
 JMPL CS:[old21]
get_psp:
 PUSH BX
 MOV AH, 62h
 PUSHF
 CALLI CS:[old21]
 MOV AX, BX
 POP BX
 RET
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
 MOV BYTE CS:[pend_mod], 0
 MOV AX, DS
 MOV CS:[app_ds], AX
 MOV SI, DX
 XOR CX, CX
fo_len: MOV AL, [SI]
 CMP AL, 0
 JE fo_got
 INC SI
 INC CX
 CMP CX, 128
 JB fo_len
 JMP fo_done
fo_got:
 CMP CX, 5
 JB fo_done
 MOV CS:[o_end], SI
 MOV CS:[o_len], CX
 MOV BYTE CS:[o_i], 0
fo_slot:
 MOV AL, CS:[o_i]
 CMP AL, 12
 JAE fo_try
 XOR AH, AH
 MOV BX, AX
 MOV BX, CS:[BX+slots]
 CMP BX, 0
 JE fo_nexts
 ADD BX, 40
 CALL name_match
 CMP AL, 0
 JE fo_nexts
 MOV AL, CS:[o_i]
 SHR AL, 1
 INC AL
 MOV CS:[pend_mod], AL
 MOV CS:[pend_rec], BX
 JMP fo_done
fo_nexts:
 ADD BYTE CS:[o_i], 2
 JMP fo_slot
fo_try:
 CALL try_load
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
 CMP BYTE CS:[pend_mod], 0
 JE open_done
 TEST WORD [BP+6], 1
 JNZ open_done
 MOV CS:[o_end], AX
 CALL verify_size
 CMP BYTE CS:[vf_ok], 0
 JE open_done
 MOV AX, CS:[o_end]
 CALL find_slot
 CMP BX, 0FFFFh
 JE open_done
 MOV CS:[BX+handles], AX
 MOV WORD CS:[BX+handles+2], 0
 MOV BYTE CS:[BX+handles+4], 0
 MOV AL, CS:[pend_mod]
 DEC AL
 MOV CS:[BX+handles+5], AL
 CALL get_psp
 MOV CS:[BX+handles+6], AX
__DIAGO__
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
; name_match: BX = module record, DS = caller data, o_end/o_len = opened name -> AL=1 if the name ends with the record's name
name_match:
 XOR CX, CX
 MOV CL, CS:[BX]
 CMP CX, CS:[o_len]
 JA nm_no
 MOV SI, CS:[o_end]
 SUB SI, CX
 CMP CX, CS:[o_len]
 JE nm_cmp
 MOV AL, [SI-1]
 CMP AL, 92
 JE nm_cmp
 CMP AL, 58
 JNE nm_no
nm_cmp:
 LEA DI, [BX+1]
nm_c1: MOV AL, [SI]
 CMP AL, 97
 JB nm_up
 CMP AL, 122
 JA nm_up
 SUB AL, 32
nm_up: CMP AL, CS:[DI]
 JNE nm_no
 INC SI
 INC DI
 DEC CX
 JNZ nm_c1
 MOV AL, 1
 RET
nm_no:
 XOR AL, AL
 RET
; build_lpath: append BASE.W8x for the opened name (DS = caller data) to the library path. AL=1 ok
build_lpath:
 MOV SI, CS:[o_end]
 MOV CX, CS:[o_len]
bl_back:
 CMP CX, 0
 JE bl_start
 MOV AL, [SI-1]
 CMP AL, 92
 JE bl_start
 CMP AL, 58
 JE bl_start
 DEC SI
 DEC CX
 JMP bl_back
bl_start:
 MOV DI, CS:[libend]
 XOR BX, BX
bl_copy:
 CMP CX, 0
 JE bl_fail
 MOV AL, [SI]
 CMP AL, 46
 JE bl_dot
 CMP BX, 8
 JAE bl_fail
 CMP AL, 97
 JB bl_put
 CMP AL, 122
 JA bl_put
 SUB AL, 32
bl_put:
 MOV CS:[DI], AL
 INC DI
 INC SI
 DEC CX
 INC BX
 JMP bl_copy
bl_dot:
 CMP BX, 0
 JE bl_fail
 CMP CX, 2
 JB bl_fail
 MOV AL, [SI+1]
 CMP AL, 97
 JB bl_ext
 CMP AL, 122
 JA bl_ext
 SUB AL, 32
bl_ext:
 MOV BYTE CS:[DI], 46
 MOV BYTE CS:[DI+1], 87
 MOV BYTE CS:[DI+2], 56
 MOV CS:[DI+3], AL
 MOV BYTE CS:[DI+4], 0
 MOV AL, 1
 RET
bl_fail:
 XOR AL, AL
 RET
; evict_all: drop every loaded module (arena exhausted)
evict_all:
 XOR SI, SI
ev_s:
 MOV WORD CS:[SI+slots], 0
 ADD SI, 2
 CMP SI, 12
 JB ev_s
 MOV AX, arena
 MOV CS:[arena_top], AX
 XOR SI, SI
ev_h:
 CMP WORD CS:[SI+handles], 0FFFFh
 JE ev_n
 MOV BYTE CS:[SI+handles+5], 0FFh
ev_n:
 ADD SI, 8
 CMP SI, 96
 JB ev_h
 RET
; try_load: load the library file for the opened name; on success pend_mod/pend_rec are set (DS clobbered)
try_load:
 CALL build_lpath
 CMP AL, 0
 JNE tl_go
 RET
tl_go:
 MOV AX, CS
 MOV DS, AX
 MOV DX, lpath
 MOV AX, 3D00h
 PUSHF
 CALLI CS:[old21]
 JNC tl_opened
 RET
tl_opened:
 MOV [tl_h], AX
 MOV BYTE [tl_try], 0
tl_read:
 MOV CX, [arena_end]
 SUB CX, [arena_top]
 MOV [tl_cap], CX
 MOV DX, [arena_top]
 MOV BX, [tl_h]
 MOV AH, 3Fh
 PUSHF
 CALLI CS:[old21]
 JC tl_closeb
 CMP AX, [tl_cap]
 JB tl_got
 CMP BYTE [tl_try], 0
 JNE tl_closeb
 MOV BYTE [tl_try], 1
 CALL evict_all
 MOV BX, [tl_h]
 MOV AX, 4200h
 XOR CX, CX
 XOR DX, DX
 PUSHF
 CALLI CS:[old21]
 JMP tl_read
tl_closeb:
 MOV BX, [tl_h]
 MOV AH, 3Eh
 PUSHF
 CALLI CS:[old21]
 RET
tl_got:
 MOV [tl_len], AX
 MOV BX, [tl_h]
 MOV AH, 3Eh
 PUSHF
 CALLI CS:[old21]
 MOV DI, [arena_top]
 CMP WORD [tl_len], 66
 JB tl_bad
 CMP WORD [DI], 14423
 JNE tl_bad
 CMP WORD [DI+2], 12621
 JNE tl_bad
 MOV AX, [DI+4]
 SHL AX, 1
 SHL AX, 1
 MOV DX, AX
 SHL AX, 1
 ADD AX, DX
 ADD AX, 66
 MOV [tl_cf], AX
 XOR BX, BX
 MOV BL, [DI+6]
 ADD BX, BX
 ADD AX, BX
 CMP AX, [tl_len]
 JNE tl_bad
 MOV AX, [app_ds]
 MOV DS, AX
 MOV BX, CS:[arena_top]
 ADD BX, 40
 CALL name_match
 CMP AL, 0
 JE tl_bad
 MOV DI, CS:[arena_top]
 XOR CX, CX
 MOV CL, CS:[DI+6]
 CMP CX, 0
 JE tl_nc
 MOV DX, CS:[tl_cf]
 ADD DX, DI
tl_cl:
 MOV BX, DX
 MOV AX, CS:[BX]
 XOR SI, SI
tl_cs:
 MOV BX, CS:[SI+slots]
 CMP BX, 0
 JE tl_csn
 CMP AX, CS:[BX+58]
 JNE tl_csn
 MOV WORD CS:[SI+slots], 0
tl_csn:
 ADD SI, 2
 CMP SI, 12
 JB tl_cs
 ADD DX, 2
 DEC CX
 JNZ tl_cl
tl_nc:
 XOR SI, SI
tl_fs:
 CMP WORD CS:[SI+slots], 0
 JE tl_fx
 ADD SI, 2
 CMP SI, 12
 JB tl_fs
 RET
tl_fx:
 MOV AX, CS:[arena_top]
 MOV CS:[SI+slots], AX
 ADD AX, 40
 MOV CS:[pend_rec], AX
 MOV AX, CS:[tl_len]
 ADD CS:[arena_top], AX
 PUSH SI
 CALL get_psp
 POP SI
 MOV CS:[SI+slotpsp], AX
 MOV AX, SI
 SHR AX, 1
 INC AX
 MOV CS:[pend_mod], AL
tl_bad:
 RET
find_slot:
 XOR BX, BX
fs_loop: CMP WORD CS:[BX+handles], 0FFFFh
 JE fs_ret
 ADD BX, 8
 CMP BX, 96
 JB fs_loop
 MOV BX, 0FFFFh
fs_ret: RET
find_handle:
 PUSH AX
 PUSH SI
 CALL get_psp
 MOV CS:[cur_psp], AX
 XOR SI, SI
fh_loop: MOV AX, CS:[SI+handles]
 CMP AX, BX
 JNE fh_next
 MOV AX, CS:[SI+handles+6]
 CMP AX, CS:[cur_psp]
 JE fh_yes
fh_next: ADD SI, 8
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
; verify_size: handle in CS:[o_end]; module record CS:[pend_rec]. vf_ok=1 iff size matches. position left at 0.
verify_size:
 MOV BYTE CS:[vf_ok], 0
 MOV BX, CS:[o_end]
 MOV AX, 4202h
 XOR CX, CX
 XOR DX, DX
 PUSHF
 CALLI CS:[old21]
 MOV SI, AX
 MOV DI, DX
 PUSHF
 POP AX
 TEST AX, 1
 JNZ vs_s0
 MOV BX, CS:[pend_rec]
 CMP SI, CS:[BX+14]
 JNE vs_s0
 CMP DI, CS:[BX+16]
 JNE vs_s0
 MOV BYTE CS:[vf_ok], 1
vs_s0:
 MOV BX, CS:[o_end]
 MOV AX, 4200h
 XOR CX, CX
 XOR DX, DX
 PUSHF
 CALLI CS:[old21]
 RET
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
 MOV AL, CS:[BX+handles+4]
 MOV CS:[rd_poshi], AL
 MOV AL, CS:[BX+handles+5]
 SHL AL, 1
 MOV CS:[rd_modsh], AL
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
 MOV CS:[rd_n], AX
 MOV BX, [BP-4]
 CALL find_handle
 CMP BX, 0FFFFh
 JE rd_upd_done
 ADD CS:[BX+handles+2], AX
 JNB rd_upd_done
 INC BYTE CS:[BX+handles+4]
rd_upd_done:
 PUSH CS
 POP DS
 MOV AX, [rd_pos]
 MOV AL, AH
 MOV AH, [rd_poshi]
 MOV [rd_ps], AX
 MOV AX, [rd_pos]
 MOV DL, [rd_poshi]
 ADD AX, [rd_n]
 JNB rw_e1
 INC DL
rw_e1: SUB AX, 1
 JNB rw_e2
 DEC DL
rw_e2: MOV AL, AH
 MOV AH, DL
 MOV BL, [rd_modsh]
 CMP BL, 12
 JB rd_s_ok
 JMP read_done
rd_s_ok:
 XOR BH, BH
 MOV BX, [BX+slots]
 CMP BX, 0
 JNE rd_img_ok
 JMP read_done
rd_img_ok:
 MOV [rd_img], BX
 ADD BX, 62
 CMP AX, [BX]
 JB read_done
 MOV DX, [rd_ps]
 CMP DX, [BX+2]
 JA read_done
 MOV AX, [rd_bufseg]
 MOV ES, AX
 MOV SI, [rd_img]
 MOV CX, [SI+4]
 ADD SI, 66
rd_loop:
 CMP CX, 0
 JE read_done
 CMP BYTE [v20], 0
 JE rd_go
 CMP BYTE [SI+2], 8
 JNE rd_next
rd_go:
 MOV AX, [SI+8]
 MOV DL, [SI+10]
 MOV BH, 0
 CALL try_patch
 MOV BL, [SI+2]
 CMP BL, 5
 JE rd_next
 CMP BL, 6
 JE rd_next
 CMP BL, 8
 JNE rd_2nd
 CMP BYTE [SI+6], 1
 JE rd_next
rd_2nd:
 MOV AX, [SI+8]
 MOV DL, [SI+10]
 INC AX
 JNZ rd_nc
 INC DL
rd_nc:
 MOV BH, 1
 CALL try_patch
rd_next:
 ADD SI, 12
 DEC CX
 JMP rd_loop
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
; try_patch: AX/DL = file offset (lo/hi) of the byte, BH = 0 first byte / 1 vector byte, SI = entry
try_patch:
 SUB AX, [rd_pos]
 JNB tp_nb
 DEC DL
tp_nb:
 SUB DL, [rd_poshi]
 CMP DL, 0
 JNE tp_out
 CMP AX, [rd_n]
 JAE tp_out
 MOV DI, AX
 ADD DI, [rd_buf]
 CMP BH, 0
 JNE tp_vec
 MOV BL, [SI+2]
 MOV AL, 0CCh
 CMP BL, 5
 JE tp_wr
 CMP BL, 6
 JE tp_wr
 CMP BL, 8
 JNE tp_cd
 MOV AL, [SI+4]
 JMP tp_wr
tp_cd: MOV AL, 0CDh
 JMP tp_wr
tp_vec:
 CMP BYTE [SI+2], 8
 JNE tp_vec2
 MOV AL, [SI+5]
 JMP tp_wr
tp_vec2: MOV AL, [SI+11]
 AND AL, 7
 ADD AL, 0F8h
tp_wr:
 MOV ES:[DI], AL
__DIAGP__
tp_out:
 RET
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
 MOV CS:[BX+handles+4], DL
 JMP seek_done
sk_upd_done:
 POP DX
 POP AX
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
arena:
; =============== install (transient; shares its space with the arena) ===============
install:
 MOV AX, CS
 MOV DS, AX
 MOV DX, msg_title
 MOV AH, 9
 INT 21h
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
 MOV AX, 0100h
 DB 0D5h, 010h
 CMP AL, 10
 JNE ic_nov
 MOV BYTE [v20], 1
ic_nov: MOV SI, 81h
 MOV DI, lpath
ic_sk0: CMP BYTE [SI], 32
 JNE ic_opt
 INC SI
 JMP ic_sk0
ic_opt: CMP BYTE [SI], 47
 JNE ic_c1
 MOV AL, [SI+1]
 AND AL, 0DFh
 CMP AL, 86
 JE ic_v
 CMP AL, 56
 JNE ic_bad
 MOV BYTE [v20], 0
 ADD SI, 2
 JMP ic_sk0
ic_v: MOV BYTE [v20], 1
 ADD SI, 2
 JMP ic_sk0
ic_bad: JMP usage
ic_c1: MOV AL, [SI]
 CMP AL, 13
 JE ic_e1
 CMP AL, 32
 JE ic_e1
 MOV [DI], AL
 INC DI
 INC SI
 CMP DI, lpath_max
 JB ic_c1
 JMP usage
ic_e1: CMP DI, lpath
 JNE ic_have
 MOV SI, defdir
ic_dd: MOV AL, [SI]
 MOV [DI], AL
 INC SI
 INC DI
 CMP AL, 0
 JNE ic_dd
 DEC DI
ic_have:
 CMP BYTE [DI-1], 92
 JNE ic_nb
 DEC DI
ic_nb: MOV BYTE [DI], 92
 INC DI
 MOV [libend], DI
 MOV SI, wild
ic_w: MOV AL, [SI]
 MOV [DI], AL
 INC SI
 INC DI
 CMP AL, 0
 JNE ic_w
 MOV DX, lpath
 XOR CX, CX
 MOV AH, 4Eh
 INT 21h
 MOV WORD [maxsz], 0
ic_ff: JC ic_ffd
 MOV AX, [9Ah]
 CMP AX, [maxsz]
 JBE ic_nx
 MOV [maxsz], AX
ic_nx: MOV AH, 4Fh
 INT 21h
 JMP ic_ff
ic_ffd:
 MOV AX, [maxsz]
 ADD AX, AX
 CMP AX, 2048
 JAE ic_a1
 MOV AX, 2048
ic_a1: CMP AX, 32768
 JBE ic_a2
 MOV AX, 32768
ic_a2: ADD AX, arena
 MOV [arena_end], AX
 MOV AX, arena
 MOV [arena_top], AX
 MOV BX, [libend]
 MOV BYTE [BX], 0
 MOV AH, 35h
 MOV AL, 21h
 INT 21h
 MOV WORD CS:[old21], BX
 MOV AX, ES
 MOV WORD CS:[old21+2], AX
 MOV AH, 35h
 MOV AL, 3
 INT 21h
 MOV WORD CS:[old3], BX
 MOV AX, ES
 MOV WORD CS:[old3+2], AX
 MOV DX, stub0
 MOV AX, 25F8h
 INT 21h
__HOOKVEC__
 MOV DX, int3h
 MOV AX, 2503h
 INT 21h
 MOV DX, hook21
 MOV AX, 2521h
 INT 21h
 MOV DX, msg_ok
 MOV AH, 9
 INT 21h
 MOV DX, [arena_end]
 ADD DX, 15
 MOV CL, 4
 SHR DX, CL
 ADD DX, 16
 MOV AX, 3100h
 INT 21h
already_p:
 MOV DX, msg_already
 MOV AH, 9
 INT 21h
 MOV AX, 4C00h
 INT 21h
usage:
 MOV DX, msg_usage
 JMP die1
die1:
 MOV AH, 9
 INT 21h
 MOV AX, 4C02h
 INT 21h
msg_title:
__MSG_TITLE__
msg_ok:
__MSG_OK__
msg_already:
__MSG_ALREADY__
msg_usage:
__MSG_USAGE__
defdir: DB 67,58,92,87,56,88,0
wild: DB 42,46,87,56,63,0
maxsz: DW 0
"""
# transient scratch labels placed after the file end (no bytes in the .COM)

def build():
    import os
    a = ASM
    if os.environ.get("WM88_DIAG"):
        a = a.replace("__DIAG__", " MOV AX, 0B800h\n MOV ES, AX\n INC WORD ES:[0]\n MOV AX, [site_off]\n MOV ES:[2], AX\n MOV AX, [BP+4]\n MOV ES:[4], AX")
        a = a.replace("__DIAGO__", " PUSH ES\n PUSH AX\n MOV AX, 0B800h\n MOV ES, AX\n INC WORD ES:[12]\n POP AX\n POP ES")
        a = a.replace("__DIAGP__", " PUSH ES\n PUSH AX\n MOV AX, 0B800h\n MOV ES, AX\n INC WORD ES:[8]\n MOV AX, [rd_pos]\n MOV ES:[10], AX\n POP AX\n POP ES")
        a = a.replace("__DIAGNF__", " MOV AX, 0B800h\n MOV ES, AX\n INC WORD ES:[6]")
    else:
        a = a.replace("__DIAG__", "").replace("__DIAGNF__", "").replace("__DIAGP__", "").replace("__DIAGO__", "")
    a = a.replace("__HANDLES__", "\n".join(" DB 255,255,0,0,0,0,0,0" for _ in range(12)))
    a = a.replace("__LPATH__", " DB " + ",".join(["0"] * 64))
    hv = []
    for i in range(1, 7):
        hv += [f" MOV DX, stub{i}", f" MOV AX, {0x2500 | (0xF8 + i)}", " INT 21h"]
    a = a.replace("__HOOKVEC__", "\n".join(hv))
    msgs = {"TITLE": "WM88X3 - Win3.0 8088 bridge (library driven)", "OK": "Installed. Library modules load on demand.", "ALREADY": "Already installed.",
            "USAGE": "usage: WM88X3 [/V|/8] [library dir, default C:\\W8X]  (NEC V20/V30 auto-detected and left native; /8 forces 8088 rewriting, /V forces native)"}
    for k, v in msgs.items(): a = a.replace(f"__MSG_{k}__", dbs(v))
    code, labels = assemble(a + "\n", org=0x100)
    # scratch labels: assemble() needs them defined; append zero-length via extra pass
    return code, labels

if __name__ == "__main__":
    import os
    # scratch vars live after code: emit them as real (zeroed) bytes only for the tiny set; crcbuf is 512
    ASM = ASM  # noqa
    extra = ""
    ASM = ASM + extra
    code, labels = build()
    out = ROOT / ("artifacts/WM88X3_D.COM" if os.environ.get("WM88_DIAG") else "artifacts/WM88X3.COM")
    out.write_bytes(code)
    print("WM88X3.COM", len(code), "arena", hex(labels["arena"]), "resident bytes", labels["arena"] - 0x100)
