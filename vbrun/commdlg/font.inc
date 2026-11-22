; ================================================================ ChooseFont
; CHOOSEFONT: +4 hwndOwner, +6 hDC, +8 lpLogFont, +12 iPointSize, +14 Flags, +26 hook,
; +40 nFontType. Flags: CF_PRINTERFONTS 2, CF_ENABLEHOOK 8, CF_INITTOLOGFONTSTRUCT 40h,
; CF_EFFECTS 100h. LOGFONT: +0 lfHeight, +8 lfWeight, +10 lfItalic, +11 lfUnderline,
; +12 lfStrikeOut, +18 lfFaceName[32].

FARPROC ChooseFont
        mov     word [gErr], 0
        les     bx, [bp+6]
        mov     [ofn], bx
        mov     [ofn+2], es
        mov     word [freldc], 0
        mov     ax, [es:bx+6]           ; hDC
        test    byte [es:bx+14], 2      ; CF_PRINTERFONTS with a printer DC: its fonts
        jz      .screen
        or      ax, ax
        jnz     .have
.screen:
        xor     ax, ax
        push    ax
        API     USER, 66                ; GetDC(NULL)
        mov     word [freldc], 1
.have:  mov     [fdc], ax
        push    ax
        PUSHI   90                      ; LOGPIXELSY
        API     GDI, 80                 ; GetDeviceCaps
        mov     [logpy], ax
        mov     ax, 16                  ; FormatCharDlgProc
        mov     si, dlg_font
        mov     cx, dlg_font_end - dlg_font
        call    run_dialog
        push    ax
        cmp     word [freldc], 0
        je      .norel
        xor     ax, ax
        push    ax
        push    word [fdc]
        API     USER, 68                ; ReleaseDC
.norel: pop     ax
        cmp     ax, 1
        je      .ok
        xor     ax, ax
.ok:    FARRET  4

; FontFamilyEnumProc(lpLogFont, lpTextMetric, nFontType, lpData): one call per typeface
FARPROC FontFamilyEnumProc
        push    word [hdlg]
        PUSHI   cmb1
        PUSHI   CB_ADDSTRING
        xor     ax, ax
        push    ax
        mov     ax, [bp+16]
        add     ax, 18                  ; lfFaceName
        push    word [bp+18]
        push    ax
        API     USER, 101
        inc     word [fcount]
        mov     ax, 1
        FARRET  14

FARPROC FontDlgProc
        mov     ax, [bp+12]
        cmp     ax, WM_INITDIALOG
        jne     .ni
        mov     ax, [bp+14]
        mov     [hdlg], ax
        les     bx, [ofn]
        mov     ax, 8
        mov     cx, 14
        mov     dx, 26
        call    load_hook
        call    font_init
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
.okb:   call    font_ok
.one:   mov     ax, 1
        jmp     short .ret
.z:     xor     ax, ax
.ret:   FARRET  10

; end_dlg: EndDialog(hdlg, AX)
end_dlg:
        push    word [hdlg]
        push    ax
        API     USER, 88
        ret

; cb_add: AX = combo id, SI = string in DS
cb_add:
        push    word [hdlg]
        push    ax
        PUSHI   CB_ADDSTRING
        xor     ax, ax
        push    ax
        PUSHD   si
        API     USER, 101
        ret

; cb_msg: AX = combo id, BX = message, CX = wParam, DX:SI = lParam; returns AX
cb_msg:
        push    word [hdlg]
        push    ax
        push    bx
        push    cx
        push    dx
        push    si
        API     USER, 101
        ret

font_init:
        mov     word [fcount], 0
        push    word [hInst]
        xor     ax, ax
        push    ax
        PUSHI   19                      ; FontFamilyEnumProc
        API     KERNEL, 50              ; GetProcAddress
        push    word [fdc]
        xor     cx, cx
        push    cx
        push    cx                      ; all typefaces
        push    dx
        push    ax
        push    cx
        push    cx                      ; lpData
        API     GDI, 70                 ; EnumFonts
        cmp     word [fcount], 0
        jne     .faces
        mov     word [gErr], 2001h      ; CFERR_NOFONTS
        xor     ax, ax
        call    end_dlg
        ret
.faces: mov     si, st_styles
.st:    cmp     byte [si], 0
        je      .sizes
        mov     ax, cmb2
        push    si
        call    cb_add
        pop     si
.sk1:   lodsb
        or      al, al
        jnz     .sk1
        jmp     .st
.sizes: mov     si, st_sizes
.sz:    cmp     byte [si], 0
        je      .init
        mov     ax, cmb3
        push    si
        call    cb_add
        pop     si
.sk2:   lodsb
        or      al, al
        jnz     .sk2
        jmp     .sz
.init:  les     bx, [ofn]
        test    byte [es:bx+15], 1      ; CF_EFFECTS (100h)
        jnz     .eff
        mov     ax, chx1
        call    hide_item
        mov     ax, chx2
        call    hide_item
.eff:   les     bx, [ofn]
        mov     word [fsize], 10
        xor     di, di                  ; style index
        test    byte [es:bx+14], 40h    ; CF_INITTOLOGFONTSTRUCT
        jz      .def
        les     bx, [es:bx+8]
        mov     ax, es
        or      ax, bx
        jz      .def
        ; typeface
        push    es
        push    bx
        mov     ax, cmb1
        mov     dx, es
        lea     si, [bx+18]
        mov     bx, CB_SELECTSTRING
        mov     cx, -1
        call    cb_msg
        pop     bx
        pop     es
        cmp     ax, -1
        jne     .face
        push    es
        push    bx
        call    sel_first_face
        pop     bx
        pop     es
.face:  cmp     word [es:bx+8], 600     ; lfWeight
        jb      .nb
        or      di, 2
.nb:    cmp     byte [es:bx+10], 0      ; lfItalic
        je      .ni
        or      di, 1
.ni:    mov     ax, [es:bx]             ; lfHeight -> points
        or      ax, ax
        jz      .chk
        jns     .pos
        neg     ax
.pos:   push    es
        push    bx
        push    ax
        PUSHI   72
        push    word [logpy]
        API     GDI, 128                ; MulDiv(|h|, 72, LOGPIXELSY)
        pop     bx
        pop     es
        or      ax, ax
        jz      .chk
        mov     [fsize], ax
.chk:   mov     al, [es:bx+12]          ; lfStrikeOut
        mov     [fstrike], al
        mov     al, [es:bx+11]          ; lfUnderline
        mov     [funder], al
        jmp     short .apply
.def:   call    sel_first_face
        mov     byte [fstrike], 0
        mov     byte [funder], 0
.apply: mov     ax, cmb2
        mov     bx, CB_SETCURSEL
        mov     cx, di
        xor     dx, dx
        xor     si, si
        call    cb_msg
        push    word [hdlg]
        PUSHI   cmb3
        push    word [fsize]
        xor     ax, ax
        push    ax
        API     USER, 94                ; SetDlgItemInt
        push    word [hdlg]
        PUSHI   chx1
        mov     al, [fstrike]
        xor     ah, ah
        push    ax
        API     USER, 97                ; CheckDlgButton
        push    word [hdlg]
        PUSHI   chx2
        mov     al, [funder]
        xor     ah, ah
        push    ax
        API     USER, 97
        ret

sel_first_face:
        mov     ax, cmb1
        mov     bx, CB_SETCURSEL
        xor     cx, cx
        xor     dx, dx
        xor     si, si
        call    cb_msg
        ret

; hide_item: AX = control id
hide_item:
        push    word [hdlg]
        push    ax
        API     USER, 91
        push    ax
        xor     ax, ax
        push    ax
        API     USER, 42                ; ShowWindow(SW_HIDE)
        ret

font_ok:
        push    word [hdlg]
        PUSHI   cmb1
        PUSHD   facebuf
        PUSHI   32
        API     USER, 93                ; GetDlgItemText(cmb1)
        or      ax, ax
        jz      .beep
        push    word [hdlg]
        PUSHI   cmb3
        xor     ax, ax
        push    ax
        push    ax                      ; no translated flag
        push    ax                      ; unsigned
        API     USER, 95                ; GetDlgItemInt
        or      ax, ax
        jz      .beep
        cmp     ax, 999
        ja      .beep
        mov     [fsize], ax
        mov     ax, cmb2
        mov     bx, CB_GETCURSEL
        xor     cx, cx
        xor     dx, dx
        xor     si, si
        call    cb_msg
        or      ax, ax
        jns     .st
        xor     ax, ax
.st:    and     ax, 3
        mov     [fstyle], ax
        push    word [hdlg]
        PUSHI   chx1
        API     USER, 98                ; IsDlgButtonChecked
        mov     [fstrike], al
        push    word [hdlg]
        PUSHI   chx2
        API     USER, 98
        mov     [funder], al
        push    word [fsize]
        push    word [logpy]
        PUSHI   72
        API     GDI, 128                ; MulDiv(size, LOGPIXELSY, 72)
        neg     ax
        mov     [fheight], ax
        les     bx, [ofn]
        mov     ax, [fsize]
        mov     cx, 10
        mul     cx
        mov     [es:bx+12], ax          ; iPointSize
        mov     ax, 2000h               ; SCREEN_FONTTYPE
        mov     cx, [fstyle]
        test    cl, 2
        jz      .nbold
        or      ax, 100h                ; BOLD_FONTTYPE
.nbold: test    cl, 1
        jz      .nit
        or      ax, 200h                ; ITALIC_FONTTYPE
.nit:   test    cl, 3
        jnz     .ft
        or      ax, 400h                ; REGULAR_FONTTYPE
.ft:    mov     [es:bx+40], ax
        les     di, [es:bx+8]
        mov     ax, es
        or      ax, di
        jz      .done
        push    di
        mov     cx, 25
        xor     ax, ax
        rep     stosw                   ; clear the 50-byte LOGFONT
        pop     di
        mov     ax, [fheight]
        mov     [es:di], ax
        mov     ax, 400
        test    byte [fstyle], 2
        jz      .w
        mov     ax, 700
.w:     mov     [es:di+8], ax
        mov     al, [fstyle]
        and     al, 1
        mov     [es:di+10], al
        mov     al, [funder]
        mov     [es:di+11], al
        mov     al, [fstrike]
        mov     [es:di+12], al
        add     di, 18
        mov     si, facebuf
        mov     cx, 31
.fc:    lodsb
        stosb
        or      al, al
        jz      .done
        loop    .fc
        mov     byte [es:di], 0
.done:  mov     ax, 1
        call    end_dlg
        ret
.beep:  xor     ax, ax
        push    ax
        API     USER, 104
        ret
