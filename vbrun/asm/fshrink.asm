; Trim a VB form/module local heap to its live size plus headroom once the object
; is built. Form heaps are locked for life (USER keeps their segment as hInstance in
; every control window, VB keeps far pointers), so they are created with a generous
; reserve; this gives each one's unused tail back to the global heap individually.
; LocalShrink compacts moveable local blocks (VB allocates LMEM_MOVEABLE and
; dereferences handles on use, as it must in protected mode too) and shrinks the
; segment in place, so nothing global moves.
;
; FORM (seg 76 form load, after the controls exist, before Form_Load): called near
;   in place of 'cmp word [0x396c],2 / jne / mov word [0x371e],1'; [bp-0x12] = heap.
; SYS  (seg 75 system-object container, after it is registered): called near in
;   place of 'mov ax,[bp-2]'; the new object's handle is [0x370c]:[0x370a].
bits 16
cpu 8086
org BASE
%ifdef FORM
entry:  cmp word [0x396c],2
        jne .a
        mov word [0x371e],1
.a:     push ds
        push si
        push di
        mov ax,[bp-0x12]
        call shrink
        pop di
        pop si
        pop ds
        ret
%else
entry:  push ds
        push si
        push di
        mov es,[0x370c]
        mov bx,[0x370a]
        mov ax,es
        or ax,bx
        jz .x
        mov bx,[es:bx]                  ; dereference the object handle
        mov ax,[es:bx+0x2f]             ; its local heap
        call shrink
.x:     pop di
        pop si
        pop ds
        mov ax,[bp-2]
        ret
%endif

; AX = heap segment. Clobbers ax,bx,cx,dx,es,si,di,ds.
shrink: or ax,ax
        jz .out
        mov ds,ax
        mov di,[6]
        or di,di
        jz .out
        cmp word [di+0x22],0x484c       ; 'LH' heap-info signature
        jne .out
        mov dx,[di+8]
        add dx,0xa
        sub dx,[di+6]                   ; span of the heap
        xor ax,ax                       ; free bytes: walk the free list
        mov si,[di+8]
        mov bx,[di+6]
        mov bx,[bx+8]
.fl:    cmp bx,si
        je .fd
        add ax,[bx+4]
        sub ax,0xa
        mov bx,[bx+8]
        jmp .fl
.fd:    mov cx,dx
        sub cx,ax                       ; live bytes (incl. arena headers)
        jb .out
        mov ax,cx
        shr ax,1                        ; headroom = max(live/2, MINHEAD)
        cmp ax,MINHEAD
        jae .h
        mov ax,MINHEAD
.h:     add ax,cx
        jc .out
        cmp ax,dx
        jae .out
        mov [di+0x20],ax                ; LocalInit set the minimum to the initial size
        push ds
        push ax
..@ls:  call 0:0xffff                   ; LocalShrink(hseg, cb)
.out:   ret
