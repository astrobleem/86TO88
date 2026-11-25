; macros.inc -- calling conventions and relocations for the 8086 COMMDLG (see mkne.py)
%assign RN 0

; API MODULE, ORDINAL: far call to an imported ordinal (arguments already pushed, Pascal order)
%macro API 2
  %assign RN RN+1
  db 9Ah
  ..@__I_%1_%2_%[RN]: dw 0FFFFh, 0
%endmacro

; MOVDS reg: load the data segment's selector (relocated by the loader)
%macro MOVDSSEL 0
  %assign RN RN+1
  db 0B8h
  ..@__D_%[RN]: dw 0FFFFh
%endmacro

; FARPROC name: exported FAR PASCAL entry; real-mode frame (odd BP marks a far frame for
; KERNEL's stack walk), DS = our data segment, SI/DI saved. Arguments at [bp+6] upwards.
; The entry starts with the standard 'push ds / pop ax / nop', which KERNEL rewrites to
; 'mov ax, DGROUP' for exported entries flagged as using the shared data segment. (A
; relocated 'mov ax, imm16' does not work: real-mode KERNEL patches that form too, before
; the relocations run, and breaks their fixup chain.)
%macro FARPROC 1
%1:
  push ds
  pop ax
  nop
  inc bp
  push bp
  mov bp, sp
  push ds
  mov ds, ax
  push si
  push di
%endmacro

; FARRET n: leave a FARPROC frame, popping n bytes of arguments
%macro FARRET 1
  lea sp, [bp-6]
  pop di
  pop si
  pop ds
  pop bp
  dec bp
  retf %1
%endmacro

%macro PUSHD 1          ; push a far pointer to a label in our data segment (uses AX)
  push ds
  mov ax, %1
  push ax
%endmacro

%macro PUSHI 1          ; push a 16-bit constant (uses AX; no PUSH imm on the 8086)
  mov ax, %1
  push ax
%endmacro

; ---- dialog templates (Windows 3.0 DLGTEMPLATE, no font)
%macro DLG 6            ; style, count, x, y, cx, cy  (caption follows with DLGCAP)
  dd %1
  db %2
  dw %3, %4, %5, %6
  db 0, 0               ; no menu, default class
%endmacro
%macro DLGCAP 1
  db %1, 0
%endmacro
; ITEM class, id, style, x, y, cx, cy, 'text'
%macro ITEM 8
  dw %5, %6, %7, %8, %2
  dd %3
  db %1
  db %4, 0
  db 0
%endmacro

; window styles and classes
WS_CHILD      equ 40000000h
WS_VISIBLE    equ 10000000h
WS_POPUP      equ 80000000h
WS_CAPTION    equ 00C00000h
WS_SYSMENU    equ 00080000h
WS_BORDER     equ 00800000h
WS_VSCROLL    equ 00200000h
WS_TABSTOP    equ 00010000h
WS_GROUP      equ 00020000h
DS_MODALFRAME equ 80h
DLGSTYLE      equ WS_POPUP | WS_CAPTION | WS_SYSMENU | DS_MODALFRAME | WS_VISIBLE
CHILD         equ WS_CHILD | WS_VISIBLE
C_BUTTON      equ 80h
C_EDIT        equ 81h
C_STATIC      equ 82h
C_LISTBOX     equ 83h
C_COMBO       equ 85h
BS_PUSHBUTTON equ 0
BS_DEFPUSH    equ 1
BS_AUTOCHECK  equ 3
BS_OWNERDRAW  equ 0Bh
ES_AUTOHSCROLL equ 80h
LBS_NOTIFY    equ 1
LBS_SORT      equ 2
CBS_DROPDOWN  equ 2
CBS_DROPDOWNLIST equ 3
CBS_SORT      equ 100h
SS_LEFT       equ 0
SS_NOPREFIX   equ 80h

; messages and notifications
WM_INITDIALOG equ 110h
WM_COMMAND    equ 111h
WM_DRAWITEM   equ 2Bh
EM_SETSEL     equ 401h
CB_ADDSTRING  equ 403h
CB_GETCURSEL  equ 407h
CB_GETLBTEXT  equ 408h
CB_SELECTSTRING equ 40Dh
CB_SETCURSEL  equ 40Eh
CB_GETCOUNT   equ 406h
LBN_SELCHANGE equ 1
LBN_DBLCLK    equ 2
CBN_SELCHANGE equ 1
IDOK          equ 1
IDCANCEL      equ 2
MB_OK         equ 0
MB_YESNO      equ 4
MB_ICONEXCL   equ 30h
IDYES         equ 6

; control ids (the ones Windows 3.1 COMMDLG uses, so hooks find them)
chx1 equ 410h
chx2 equ 411h
stc1 equ 440h
stc2 equ 441h
lst1 equ 460h
lst2 equ 461h
cmb1 equ 470h
cmb2 equ 471h
cmb3 equ 472h
edt1 equ 480h
