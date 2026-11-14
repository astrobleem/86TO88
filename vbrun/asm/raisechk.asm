; raisechk.asm -- DIAGNOSTIC ONLY (conv.py RAISECHK=1). Appended to fixed segment 4; the
; error dispatcher's stack reset at 4:17AA ("mov sp,ax / mov byte [2E2C],0") calls here.
; Prints on port 0xE9:  RZ err=<[2518]> sp=<SP before> new=<AX> bp=<BP> top=<6 words at SP>
; and then performs the two displaced instructions.
cpu 8086
org BASE
rchk:   pop word [cs:rip]       ; near return (into 4:17AF)
        push ax
        push bx
        push cx
        push dx
        push si
        mov si,sp
        add si,10               ; SP as it was at 4:17AA
        mov dx,s_rz
        call puts
        mov ax,[0x2518]
        call hex
        mov dx,s_sp
        call puts
        mov ax,si
        call hex
        mov dx,s_new
        call puts
        mov bx,sp
        mov ax,[ss:bx+8]        ; saved AX = new SP
        call hex
        mov dx,s_bp
        call puts
        mov ax,bp
        call hex
        mov dx,s_top
        call puts
        mov cx,6
.w:     mov ax,[ss:si]
        call hex
        mov al,' '
        out 0xe9,al
        inc si
        inc si
        loop .w
        mov al,13
        out 0xe9,al
        mov al,10
        out 0xe9,al
        pop si
        pop dx
        pop cx
        pop bx
        pop ax
        mov sp,ax
        mov byte [0x2e2c],0
        jmp word [cs:rip]
rip:    dw 0

puts:   push si
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
hex:    push ax
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
s_rz:   db 'RZ err=',0
s_sp:   db ' sp=',0
s_new:  db ' new=',0
s_bp:   db ' bp=',0
s_top:  db ' top=',0
