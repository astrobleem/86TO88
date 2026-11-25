; ================================================================ PrintDlg
; PRINTDLG: +4 hwndOwner, +6 hDevMode, +8 hDevNames, +10 hDC, +12 Flags, +24 nCopies, +32 print
; hook. Flags: PD_PRINTSETUP 40h, PD_RETURNDC 100h, PD_RETURNIC 200h, PD_RETURNDEFAULT 400h,
; PD_ENABLEPRINTHOOK 1000h. The printer is WIN.INI [windows] device=name,driver,port.

FARPROC PrintDlg
        mov     word [gErr], 0
        les     bx, [bp+6]
        mov     [ofn], bx
        mov     [ofn+2], es
        PUSHD   s_windows
        PUSHD   s_device
        PUSHD   s_empty
        PUSHD   devbuf
        PUSHI   80
        API     KERNEL, 58              ; GetProfileString
        or      ax, ax
        jnz     .have
        mov     word [gErr], 1008h      ; PDERR_NODEFAULTPRN
        jmp     .fail
.have:  ; split "name,driver,port"
        mov     si, devbuf
        mov     [pdev], si
        call    cut_comma
        mov     [pdrv], si
        call    cut_comma
        mov     [pport], si
        mov     si, [pdrv]
        cmp     byte [si], 0
        jne     .parsed
        mov     word [gErr], 1008h
        jmp     .fail
.parsed:
        les     bx, [ofn]
        test    byte [es:bx+13], 4      ; PD_RETURNDEFAULT (400h): no dialog
        jnz     .devnames
        mov     ax, 21                  ; PrintDlgProc
        mov     si, dlg_print
        mov     cx, dlg_print_end - dlg_print
        call    run_dialog
        cmp     ax, 1
        jne     .fail
.devnames:
        call    make_devnames
        jc      .fail
        les     bx, [ofn]
        mov     ax, [es:bx+12]
        test    ah, 3                   ; PD_RETURNDC / PD_RETURNIC
        jz      .ok
        PUSHD   [pdrv]
        PUSHD   [pdev]
        PUSHD   [pport]
        xor     ax, ax
        push    ax
        push    ax
        les     bx, [ofn]
        test    byte [es:bx+13], 1
        jz      .ic
        API     GDI, 53                 ; CreateDC
        jmp     short .dc
.ic:    API     GDI, 153                ; CreateIC
.dc:    les     bx, [ofn]
        mov     [es:bx+10], ax
        or      ax, ax
        jnz     .ok
        mov     word [gErr], 100Ah      ; PDERR_CREATEICFAILURE
        jmp     short .fail
.ok:    mov     ax, 1
        jmp     short .ret
.fail:  xor     ax, ax
.ret:   FARRET  4

; cut_comma: DS:SI -> end the field at ',' (trimming spaces) and return SI at the next field
cut_comma:
.sp:    cmp     byte [si], ' '
        jne     .f
        inc     si
        jmp     .sp
.f:     mov     di, si
.l:     mov     al, [di]
        or      al, al
        jz      .end
        cmp     al, ','
        je      .comma
        inc     di
        jmp     .l
.comma: mov     byte [di], 0
        call    .trim
        lea     si, [di+1]
.sp2:   cmp     byte [si], ' '
        jne     .r
        inc     si
        jmp     .sp2
.r:     ret
.end:   call    .trim
        mov     si, di                  ; empty next field
        ret
.trim:  push    di
.t:     cmp     di, si
        je      .td
        cmp     byte [di-1], ' '
        jne     .td
        dec     di
        mov     byte [di], 0
        jmp     .t
.td:    pop     di
        ret

; make_devnames: a DEVNAMES block (driver, device, port) in hDevNames; CF on failure
make_devnames:
        mov     si, [pdrv]
        call    slen
        mov     [l1], cx
        mov     si, [pdev]
        call    slen
        mov     [l2], cx
        mov     si, [pport]
        call    slen
        mov     [l3], cx
        les     bx, [ofn]
        mov     ax, [es:bx+8]
        or      ax, ax
        jz      .alloc
        push    ax
        API     KERNEL, 17              ; GlobalFree(old hDevNames)
.alloc: PUSHI   42h                     ; GHND
        xor     ax, ax
        push    ax
        mov     ax, [l1]
        add     ax, [l2]
        add     ax, [l3]
        add     ax, 8
        push    ax
        API     KERNEL, 15
        les     bx, [ofn]
        mov     [es:bx+8], ax
        or      ax, ax
        jnz     .lock
        mov     word [gErr], 2          ; CDERR_INITIALIZATION
        stc
        ret
.lock:  push    ax
        API     KERNEL, 18
        mov     es, dx
        mov     di, ax
        mov     ax, 8
        stosw                           ; wDriverOffset
        add     ax, [l1]
        stosw                           ; wDeviceOffset
        add     ax, [l2]
        stosw                           ; wOutputOffset
        mov     ax, 1
        stosw                           ; wDefault
        mov     si, [pdrv]
        mov     cx, [l1]
        rep     movsb
        mov     si, [pdev]
        mov     cx, [l2]
        rep     movsb
        mov     si, [pport]
        mov     cx, [l3]
        rep     movsb
        les     bx, [ofn]
        push    word [es:bx+8]
        API     KERNEL, 19
        clc
        ret

; slen: CX = length of DS:SI including the terminator
slen:   xor     cx, cx
.l:     inc     cx
        lodsb
        or      al, al
        jnz     .l
        ret

FARPROC PrintDlgProc
        mov     ax, [bp+12]
        cmp     ax, WM_INITDIALOG
        jne     .ni
        mov     ax, [bp+14]
        mov     [hdlg], ax
        les     bx, [ofn]
        mov     ax, 1000h
        mov     cx, 12
        mov     dx, 32
        call    load_hook
        call    print_init
        call    call_hook
        mov     ax, 1
        jmp     .ret
.ni:    call    call_hook
        or      ax, ax
        jnz     .ret
        cmp     word [bp+12], WM_COMMAND
        jne     .z
        mov     ax, [bp+10]
        cmp     ax, IDOK
        je      .okb
        cmp     ax, IDCANCEL
        jne     .z
        xor     ax, ax
        call    end_dlg
        jmp     short .one
.okb:   push    word [hdlg]
        PUSHI   edt1
        xor     ax, ax
        push    ax
        push    ax
        push    ax
        API     USER, 95                ; GetDlgItemInt(copies)
        or      ax, ax
        jnz     .c
        inc     ax
.c:     les     bx, [ofn]
        mov     [es:bx+24], ax
        mov     ax, 1
        call    end_dlg
.one:   mov     ax, 1
        jmp     short .ret
.z:     xor     ax, ax
.ret:   FARRET  10

print_init:
        les     bx, [ofn]
        test    byte [es:bx+12], 40h    ; PD_PRINTSETUP
        jz      .np
        push    word [hdlg]
        PUSHD   s_setup
        API     USER, 37
.np:    ; "name on port"
        mov     di, spec
        mov     si, [pdev]
        call    .cat
        mov     si, s_on
        call    .cat
        mov     si, [pport]
        call    .cat
        push    word [hdlg]
        PUSHI   stc1
        PUSHD   spec
        API     USER, 92
        les     bx, [ofn]
        mov     ax, [es:bx+24]
        or      ax, ax
        jnz     .cp
        inc     ax
.cp:    mov     cx, ax
        push    word [hdlg]
        PUSHI   edt1
        push    cx
        xor     ax, ax
        push    ax
        API     USER, 94                ; SetDlgItemInt(copies)
        ret
.cat:   lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .cat
        dec     di
        ret
