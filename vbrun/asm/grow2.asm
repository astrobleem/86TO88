; seg 105 grow2: same arguments as the grow routine at 0x8A (flags, size, seg; retf 6).
; Tries the in-place grow first; if that cannot reach the requested size, lets the
; kernel move the block (real mode) and returns the new segment in DX (old one on
; failure or in-place success). VB's heaps are GMEM_FIXED in this build, so a moved
; block comes back as a new handle (= new segment) from GlobalReAlloc. Callers patched to store DX back into their context.
bits 16
cpu 8086
org BASE
grow2:  mov ax,ss
        inc bp
        push bp
        mov bp,sp
        push ds
        mov ds,ax
        push si
        push di
        push word [bp+0xa]
        push word [bp+8]
        push word [bp+6]
        push cs
        call GROW
        mov dx,[bp+0xa]
        cmp ax,[bp+8]
        jae .done
        push word [bp+0xa]
..@gh1: call 0:0xffff           ; GlobalHandle
        or ax,ax
        jz .fail
        mov si,ax
        push si
        xor ax,ax
        push ax
        push word [bp+8]
        mov ax,[bp+6]
        and ax,0xfff9
        or ax,2
        push ax
..@gra: call 0:0xffff           ; GlobalReAlloc
        or ax,ax
        jz .fail
        mov si,ax               ; use the returned handle: for a GMEM_FIXED block that the
                                ; kernel moved it is the new segment, the old one is freed
        push si
..@gh2: call 0:0xffff           ; GlobalHandle -> DX = segment
        mov di,dx
        push si
..@gs:  call 0:0xffff           ; GlobalSize
        or dx,dx
        jnz .cap
        cmp ax,0xffee
        jb .ok
.cap:   mov ax,0xffee
.ok:    mov dx,di
        jmp .done
.fail:  xor ax,ax
        mov dx,[bp+0xa]
.done:  pop di
        pop si
        dec bp
        dec bp
        mov sp,bp
        pop ds
        pop bp
        dec bp
        retf 6
