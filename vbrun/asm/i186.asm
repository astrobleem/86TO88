; i186.asm -- resident part of the 80186 -> 8088 rewrite (i186.py), placed in a FIXED
; segment of VBRUN100.DLL.  PUSH imm8 sites (6A ib) are rewritten to INT 3 followed by
; the immediate byte; int3h pushes the sign-extended byte for the caller and resumes after
; it.  An INT 3 that is not one of those (the CD 03 form, or no CC before the return
; address) goes to the previous handler.  The DLL entry point is routed through init,
; which installs int3h, and WEP (ordinal 1) through wep, which takes it out again if the
; vector still points here.
bits 16
cpu 8086
org BASE

int3h:  push ax                 ; [bp+2]=ax [bp+4]=IP [bp+6]=CS [bp+8]=FL ; O = SP before INT
        push bp
        mov bp,sp
        push ds
        push si
        lds si,[bp+4]           ; DS:SI = the byte after the INT 3
        cmp byte [si-1],0xcc
        jne .chain
        mov al,[si]             ; (not LODSB: the caller's DF is still in effect)
        inc si
        cbw
        xchg ax,[bp+8]          ; [O-2] = value      ax = FL
        xchg ax,[bp+6]          ; [O-4] = FL         ax = CS
        xchg ax,[bp+4]          ; [O-6] = CS
        mov ax,si
        xchg ax,[bp+2]          ; [O-8] = IP past ib ax = caller's AX
        pop si
        pop ds
        pop bp
        iret                    ; SP = O-2, [SP] = value
.chain: pop si
        pop ds
        pop bp
        pop ax
        jmp far [cs:old3]

old3:   dd 0

init:   push ax                 ; DLL entry: DI = hInstance, DS, CX, ES:SI as KERNEL set them
        push bx
        push dx
        push ds
        push es
        mov ax,0x3503
        int 0x21
        mov [cs:old3],bx
        mov [cs:old3+2],es
        push cs
        pop ds
        mov dx,int3h
        mov ax,0x2503
        int 0x21
        pop es
        pop ds
        pop dx
        pop bx
        pop ax
..@entry: jmp 0:0xffff          ; original entry point

wep:    push ax
        push bx
        push dx
        push ds
        push es
        mov ax,0x3503
        int 0x21
        cmp bx,int3h
        jne .x
        mov ax,es
        mov bx,cs
        cmp ax,bx
        jne .x
        lds dx,[cs:old3]
        mov ax,0x2503
        int 0x21
.x:     pop es
        pop ds
        pop dx
        pop bx
        pop ax
..@wep: jmp 0:0xffff            ; original WEP
