; Real-mode call wrapper core (placed at the end of a FIXED segment).
; W stub:  call center / dd target / dw X     (X = caller's segment number, 0 = unknown)
; The caller's return address is replaced by cexit and remembered here. For a known
; caller segment X nothing is locked: on return the segment is (re)loaded through
; GetCodeHandle on a thunk of X and the return goes to its current address. For an
; unknown caller (callback through a pointer table) its code segment is locked for
; the duration of the call instead.
bits 16
cpu 8086
org BASE
%ifdef STATS
RS equ 10                       ; record also keeps the caller's CS at call time
%else
RS equ 8
%endif
wtop:   dw wstk
wstk:   times RS*NSLOT db 0     ; SS, SPe, IP, X (<0x100: segment number) or locked raw CS [, CS]
wend:
xthunk: times 4*NSEG db 0       ; far pointer to an entry of each segment (fixups)
%ifdef STATS
        db 'WSTATS'
st_call: dw 0           ; wrapped calls
st_raw:  dw 0           ; of which unknown caller (locked)
st_same: dw 0           ; returns where the caller's segment was where it was left
st_moved: dw 0          ; returns where it was moved or discarded and reloaded
st_throw: dw 0          ; records abandoned by a non-local exit
st_fallb: dw 0          ; returns matched by the newest-record fallback
st_maxd: dw 0           ; deepest nesting of live records
st_full: dw 0           ; calls not hooked because the record stack was full
%endif

center:                 ; [d][IPx][CSx][args]
        push bp
        push bp
        mov bp,sp       ; [bp+4]=d [bp+6]=IPx [bp+8]=CSx
        pushf
        push ax
        push bx
        push cx
        push dx
        push si
        push es
        mov bx,[bp+4]
        mov si,[cs:wtop]
%ifdef STATS
        inc word [cs:st_call]
        cmp si,wend
        jb .room
        inc word [cs:st_full]
        jmp .go
.room:
        mov ax,[bp+8]
        mov [cs:si+8],ax
%endif
        cmp si,wend
        jae .go
        mov ax,ss
        mov [cs:si],ax
        lea ax,[bp+6]
        mov [cs:si+2],ax
        mov ax,[bp+6]
        mov [cs:si+4],ax
        mov ax,[cs:bx+4]
        or ax,ax
        jnz .known
        mov ax,[bp+8]   ; unknown caller: remember raw CS and lock it
        mov [cs:si+6],ax
        add si,RS
        mov [cs:wtop],si
%ifdef STATS
        inc word [cs:st_raw]
        call depth
%endif
        push word [bp+8]
..@lockcall: call 0:0xffff      ; KERNEL.LockSegment
        jmp .hook
.known: mov [cs:si+6],ax
        add si,RS
        mov [cs:wtop],si
%ifdef STATS
        call depth
%endif
.hook:  mov bx,[bp+4]
        mov word [bp+6],cexit
        mov [bp+8],cs
.go:    mov ax,[cs:bx]
        mov [bp+2],ax
        mov ax,[cs:bx+2]
        mov [bp+4],ax
        pop es
        pop si
        pop dx
        pop cx
        pop bx
        pop ax
        popf
        pop bp
        retf

cexit:                  ; callee returned here; its args are already popped (SP = S)
        sub sp,2
        push bp
        push bp
        mov bp,sp       ; S = bp+6 ; [bp+2],[bp+4] = return target slots
        pushf
        push ax
        push bx
        push cx
        push dx
        push si
        push di
        push es
        lea di,[bp+6]
        mov dx,ss
        xor bx,bx
        xor cx,cx
        mov si,wstk
.p1:    cmp si,[cs:wtop]
        jae .p1d
        cmp [cs:si],dx
        jne .n1
        mov ax,[cs:si+2]
        cmp ax,di
        jae .n1
        cmp ax,cx
        jb .n1
        mov cx,ax
        mov bx,si
.n1:    add si,RS
        jmp .p1
.p1d:   or bx,bx
        jnz .have
        mov si,[cs:wtop]        ; callee re-pushed its return address lower: newest record
.fb:    cmp si,wstk
        jbe .lost
        sub si,RS
        cmp [cs:si],dx
        jne .fb
        mov cx,[cs:si+2]
        mov bx,si
%ifdef STATS
        inc word [cs:st_fallb]
%endif
.have:  mov si,[cs:wtop]
.p2:    cmp si,wstk
        jbe .p2d
        sub si,RS
        cmp [cs:si],dx
        jne .p2
        cmp [cs:si+2],cx
        jae .p2
%ifdef STATS
        inc word [cs:st_throw]
%endif
        call release            ; abandoned by Throw
        call remove
        jmp .p2
.p2d:   mov si,wstk
.p3:    cmp si,[cs:wtop]
        jae .lost
        cmp [cs:si],dx
        jne .n3
        cmp [cs:si+2],cx
        je .found
.n3:    add si,RS
        jmp .p3
.found: mov ax,[cs:si+4]
        mov [bp+2],ax
        mov ax,[cs:si+6]
        cmp ax,0x100
        jae .raw
        push si
        mov bx,ax
        shl bx,1
        shl bx,1
        push word [cs:xthunk+bx-4+2]
        push word [cs:xthunk+bx-4]
..@gch: call 0:0xffff           ; KERNEL.GetCodeHandle -> AX = handle (segment loaded)
        push ax
..@gh:  call 0:0xffff           ; KERNEL.GlobalHandle -> DX = segment
        pop si
        mov [bp+4],dx
%ifdef STATS
        cmp dx,[cs:si+8]
        jne .mv
        inc word [cs:st_same]
        jmp .rm
.mv:    inc word [cs:st_moved]
%endif
        jmp .rm
.raw:   mov [bp+4],ax
        push si
        push ax
..@unl2: call 0:0xffff          ; KERNEL.UnlockSegment
        pop si
.rm:    call remove
        pop es
        pop di
        pop si
        pop dx
        pop cx
        pop bx
        pop ax
        popf
        pop bp
        retf
.lost:  int 3
        jmp .lost

release:                ; record at cs:si abandoned: unlock if it was a locked raw CS
        push ax
        push bx
        push cx
        push dx
        push si
        push di
        push es
        mov ax,[cs:si+6]
        cmp ax,0x100
        jb .x
        push ax
..@unl1: call 0:0xffff          ; KERNEL.UnlockSegment
.x:     pop es
        pop di
        pop si
        pop dx
        pop cx
        pop bx
        pop ax
        ret

%ifdef STATS
depth:  push ax
        mov ax,[cs:wtop]
        sub ax,wstk
        cmp ax,[cs:st_maxd]
        jbe .d
        mov [cs:st_maxd],ax     ; in bytes (records * RS)
.d:     pop ax
        ret
%endif

remove:                 ; delete slot at cs:si
        push cx
        push di
        push si
        push ds
        push es
        push ax
        mov ax,cs
        mov ds,ax
        mov es,ax
        mov di,si
        add si,RS
        mov cx,[wtop]
        sub cx,si
        shr cx,1
        cld
        rep movsw
        sub word [wtop],RS
        pop ax
        pop es
        pop ds
        pop si
        pop di
        pop cx
        ret
