; Real-mode call wrapper core (placed at the end of a FIXED segment).
; W stub:  call center / dd target / dw X     (X = caller's segment number, 0 = unknown)
; The caller's return address is replaced by the return trampoline of the record that
; remembers it. For a known caller segment X nothing is locked: on return the segment is
; (re)loaded through GetCodeHandle on a thunk of X and the return goes to its current address.
; For an unknown caller (callback through a pointer table) its code segment is locked for
; the duration of the call instead.  If no record is free the application is terminated
; (FatalAppExit) rather than letting the call return unprotected.
;
; Each record slot k has its own return trampoline (ctab + k*RS/2), so a return identifies
; its record exactly, wherever the callee left its return address and whatever stale
; records a non-local exit (error reset, Throw) left behind.  Records whose frames are gone
; are reclaimed when a call made from an outer frame of the same stack returns.
bits 16
cpu 8086
org BASE
%ifdef STATS
RS equ 10                       ; record also keeps the caller's CS at call time
%else
RS equ 8
%endif
wtop:   dw wstk                 ; one past the highest slot in use
wstk:   times RS*NSLOT db 0     ; SS (0 = free), SPe, IP, X (<0x100: segment number) or locked raw CS [, CS]
wend:
xthunk: times 4*NSEG db 0       ; far pointer to an entry of each segment (fixups)
%ifdef STATS
        db 'WSTATS'
st_call: dw 0           ; wrapped calls
st_raw:  dw 0           ; of which unknown caller (locked)
st_same: dw 0           ; returns where the caller's segment was where it was left
st_moved: dw 0          ; returns where it was moved or discarded and reloaded
st_throw: dw 0          ; records abandoned by a non-local exit
st_fallb: dw 0          ; (unused: returns are identified by trampoline)
st_maxd: dw 0           ; highest slot in use
st_full: dw 0           ; calls not hooked because no record was free
st_chain: dw 0          ; entries by jump from an already-wrapped call (no new record)
%endif

ctab:                           ; return trampolines, one per record slot, RS/2 bytes each
%rep NSLOT
        call cexit
        times RS/2-3 nop
%endrep
cend:

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
        mov ax,cs               ; entered by a jump from a callee that is itself wrapped
        cmp [bp+8],ax           ; (e.g. a dispatcher doing jmp far [table] into a W stub):
        jne .new                ; the return address is already a trampoline and its record
        mov ax,[bp+6]           ; describes the real caller, so just go on to the target
        cmp ax,ctab
        jb .new
        cmp ax,cend
        jae .new
%ifdef STATS
        inc word [cs:st_chain]
%endif
        jmp .go
.new:   mov si,[cs:wtop]
        cmp si,wend
        jb .top
        mov si,wstk             ; no slot above the high-water mark: reuse a free one below
.h1:    cmp word [cs:si],0
        je .slot
        add si,RS
        cmp si,wend
        jb .h1
%ifdef STATS
        inc word [cs:st_full]
%endif
        jmp full                ; no record: the return could not be re-derived (fail closed)
.top:   lea ax,[si+RS]
        mov [cs:wtop],ax
.slot:
%ifdef STATS
        inc word [cs:st_call]
        mov ax,[bp+8]
        mov [cs:si+8],ax
        call depth
%endif
        mov ax,ss
        mov [cs:si],ax
        lea ax,[bp+6]
        mov [cs:si+2],ax
        mov ax,[bp+6]
        mov [cs:si+4],ax
        mov ax,si               ; this record's trampoline: ctab + (si-wstk)/2
        sub ax,wstk
        shr ax,1
        add ax,ctab
        mov [bp+6],ax
        mov ax,[cs:bx+4]
        or ax,ax
        jnz .known
        mov ax,[bp+8]   ; unknown caller: remember raw CS and lock it
        mov [cs:si+6],ax
%ifdef STATS
        inc word [cs:st_raw]
%endif
        push ax
..@lockcall: call 0:0xffff      ; KERNEL.LockSegment
        jmp .hook
.known: mov [cs:si+6],ax
.hook:  mov bx,[bp+4]
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

; No record free.  Going on without a record would leave the caller's raw return address
; on the stack, and if the caller's segment moved during the call the return would land in
; the old copy.  Terminate the application instead.  FatalAppExit does not return; if it
; ever does, stop here rather than run the unprotected call.
full:   mov ax,msg_full
fatal:  xor bx,bx
        push bx
        push cs
        push ax
..@fatal: call 0:0xffff         ; KERNEL.FatalAppExit(0, msg)
.hang:  jmp short .hang
msg_full: db 'VBRUN real-mode call wrapper: too many nested calls',0
msg_lost: db 'VBRUN real-mode call wrapper: return without a record',0

cexit:                  ; trampoline k called here after the callee's RETF (args popped,
        push bp         ; SP = S-2, [S-2] = ctab + k*RS/2 + 3)
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
        mov si,[bp+4]
        sub si,ctab+3
        shl si,1
        add si,wstk             ; si = record k
        mov dx,ss
        cmp si,[cs:wtop]
        jae .lost
        cmp [cs:si],dx
        jne .lost
        mov cx,[cs:si+2]        ; drop records of frames this return has unwound: same stack,
        mov di,wstk             ; return slot below this one (left by an error reset or a Throw)
.p2:    cmp di,[cs:wtop]
        jae .p2d
        cmp di,si
        je .n2
        cmp [cs:di],dx
        jne .n2
        cmp [cs:di+2],cx        ; at or below: the same slot reused after a non-local exit
        ja .n2
%ifdef STATS
        inc word [cs:st_throw]
%endif
        push si
        mov si,di
        call release            ; abandoned
        call free
        pop si
.n2:    add di,RS
        jmp .p2
.p2d:
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
.rm:    call free
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
.lost:  mov ax,msg_lost         ; a trampoline whose record is gone: never guess a return
        jmp fatal

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

free:                   ; release slot cs:si; lower the high-water mark past free slots
        push bx
        mov word [cs:si],0
.f1:    mov bx,[cs:wtop]
        cmp bx,wstk
        jbe .f2
        cmp word [cs:bx-RS],0
        jne .f2
        sub bx,RS
        mov [cs:wtop],bx
        jmp .f1
.f2:    pop bx
        ret
