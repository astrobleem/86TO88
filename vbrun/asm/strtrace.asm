; strtrace.asm -- DIAGNOSTIC ONLY (conv.py STRTRACE=1). Appended to seg 106; the near calls
; at 106:06EE (minimum + 0x200 slack) and 106:06F6 (bare minimum) to the grow helper at
; 106:073D are redirected here.  Each call prints one line on port 0xE9:
;   STR<n> req=<BX> seg=<DS> pre=<size before> ret=<helper AX> cf=<CF> post=<GlobalSize after>
; With -DSPIN=n (STRTRACE_SPIN=n) it spins n*64K loop iterations after a refused grow so a
; watcher can take a MARTY_DUMP_NOW dump first; this changes timing, default 0.
cpu 8086
org BASE
HELPER equ 0x073d

t1:     push ax
        mov al,'1'
        jmp short go
t2:     push ax
        mov al,'2'
go:     ; stack: ax(orig)
        push bp
        mov bp,sp
        push cx
        push dx
        push bx
        mov cl,al
        mov al,'S'
        out 0xe9,al
        mov al,'T'
        out 0xe9,al
        mov al,'R'
        out 0xe9,al
        mov al,cl
        out 0xe9,al
        mov dx,s_req
        call puts
        mov ax,bx
        call hex
        mov dx,s_seg
        call puts
        push bx
        mov bx,[bp]             ; caller's BP: the helper grows the segment at [bp+6]
        mov ax,[ss:bx+6]
        pop bx
        call hex
        mov dx,s_pre
        call puts
        call gsize
        call hex
        pop bx
        pop dx
        pop cx
        pop bp
        pop ax
        call HELPER             ; AX, CF as the helper returns them; DS = string segment
        pushf
        push bp
        mov bp,sp
        push ax
        push bx
        push cx
        push dx
        mov cx,[bp+2]           ; saved flags
        mov dx,s_ret
        call puts
        call hex                ; AX = helper result
        mov dx,s_cf
        call puts
        mov al,'0'
        test cl,1
        jz .c0
        inc al
.c0:    out 0xe9,al
        mov dx,s_post
        call puts
        mov ax,ds               ; helper left DS = the string segment
        call gsize
        call hex
        mov al,13
        out 0xe9,al
        mov al,10
        out 0xe9,al
%ifndef SPIN
%define SPIN 0
%endif
%if SPIN
        test cl,1
        jz .out
        mov bx,SPIN               ; let a watcher take a dump of the refusing heap
.spin:  mov cx,0xffff
.sp2:   loop .sp2
        dec bx
        jnz .spin
%endif
.out:   pop dx
        pop cx
        pop bx
        pop ax
        pop bp
        popf
        ret

; AX = GlobalSize(GlobalHandle(AX)) (low word)
gsize:  push bx
        push cx
        push dx
        push es
        push ax
..@gh:  call 0:0xffff           ; GlobalHandle(seg) -> AX handle
        push ax
..@gs:  call 0:0xffff           ; GlobalSize(handle) -> DX:AX
        pop es
        pop dx
        pop cx
        pop bx
        ret

puts:   push si                 ; DX -> zero-terminated string in CS
        push ax
        mov si,dx
.l:     mov al,[cs:si]
        or al,al
        jz .d
        out 0xe9,al
        inc si
        jmp .l
.d:     pop ax
        pop si
        ret

hex:    push ax                 ; print AX as 4 hex digits
        push cx
        push dx
        mov dx,ax
        mov cx,4
.h:     push cx
        mov cl,4
        rol dx,cl
        pop cx
        mov al,dl
        and al,15
        add al,'0'
        cmp al,'9'
        jbe .p
        add al,7
.p:     out 0xe9,al
        loop .h
        pop dx
        pop cx
        pop ax
        ret

s_req:  db ' req=',0
s_seg:  db ' seg=',0
s_pre:  db ' pre=',0
s_ret:  db ' ret=',0
s_cf:   db ' cf=',0
s_post: db ' post=',0
