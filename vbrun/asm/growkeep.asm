; seg 105 grow routine (0x8A): replaces its GlobalReAlloc call. VB's heaps are GMEM_FIXED
; in this build and are created with headroom; a GlobalReAlloc to a size that already fits
; would make the kernel cut the block back and free that headroom (VB also shrinks heaps
; explicitly), after which the next grow has to find free space right behind a fixed
; block. Keep the block as it is whenever the requested size fits; otherwise do the
; GlobalReAlloc as before. Called near with GlobalReAlloc's arguments already pushed.
bits 16
cpu 8086
org BASE
keep:   push bp
        mov bp,sp               ; [bp+2] near ret, [bp+4] flags, [bp+6] size lo, [bp+8] size hi, [bp+10] handle
        push word [bp+10]
..@gs:  call 0:0xffff           ; GlobalSize(handle) -> DX:AX
        cmp word [bp+8],0
        jne .do
        or dx,dx
        jnz .keep
        cmp ax,[bp+6]
        jb .do
.keep:  mov ax,[bp+10]          ; what GlobalReAlloc returns on success
        pop bp
        ret 8
.do:    pop bp
        pop ax                  ; turn the near call into a far one for GlobalReAlloc
        push cs
        push ax
..@gra: jmp 0:0xffff            ; GlobalReAlloc(handle, size, flags)
