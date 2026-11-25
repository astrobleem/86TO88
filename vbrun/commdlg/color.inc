; ================================================================ ChooseColor
; CHOOSECOLOR: +4 hwndOwner, +8 rgbResult, +16 Flags (CC_RGBINIT 1, CC_ENABLEHOOK 10h), +24 hook
COLBASE equ 2D0h                        ; ids of the 16 colour buttons

FARPROC ChooseColor
        mov     word [gErr], 0
        les     bx, [bp+6]
        mov     [ofn], bx
        mov     [ofn+2], es
        mov     word [csel], 0
        test    byte [es:bx+16], 1      ; CC_RGBINIT: preselect the matching basic colour
        jz      .go
        mov     ax, [es:bx+8]
        mov     dx, [es:bx+10]
        mov     si, colors
        mov     cx, 16
        xor     di, di
.f:     cmp     ax, [si]
        jne     .n
        cmp     dx, [si+2]
        jne     .n
        mov     [csel], di
        jmp     short .go
.n:     add     si, 4
        inc     di
        loop    .f
.go:    mov     ax, 8                   ; ColorDlgProc
        mov     si, dlg_color
        mov     cx, dlg_color_end - dlg_color
        call    run_dialog
        cmp     ax, 1
        je      .ok
        xor     ax, ax
.ok:    FARRET  4

FARPROC ColorDlgProc
        mov     ax, [bp+12]
        cmp     ax, WM_INITDIALOG
        jne     .ni
        mov     ax, [bp+14]
        mov     [hdlg], ax
        les     bx, [ofn]
        mov     ax, 10h
        mov     cx, 16
        mov     dx, 24
        call    load_hook
        call    call_hook
        mov     ax, 1
        jmp     .ret
.ni:    call    call_hook
        or      ax, ax
        jnz     .ret
        mov     ax, [bp+12]
        cmp     ax, WM_DRAWITEM
        jne     .nd
        call    color_draw
        jmp     .ret
.nd:    cmp     ax, WM_COMMAND
        jne     .z
        mov     ax, [bp+10]
        cmp     ax, IDOK
        je      .okb
        cmp     ax, IDCANCEL
        je      .cancel
        sub     ax, COLBASE
        cmp     ax, 16
        jae     .z
        mov     bx, [csel]
        mov     [csel], ax
        call    color_inval             ; old one (BX) and the new one
        mov     bx, [csel]
        call    color_inval
        jmp     short .one
.okb:   mov     si, [csel]
        shl     si, 1
        shl     si, 1
        mov     ax, [colors+si]
        mov     dx, [colors+si+2]
        les     bx, [ofn]
        mov     [es:bx+8], ax
        mov     [es:bx+10], dx
        mov     ax, 1
        jmp     short .end
.cancel:
        xor     ax, ax
.end:   push    word [hdlg]
        push    ax
        API     USER, 88                ; EndDialog
.one:   mov     ax, 1
        jmp     short .ret
.z:     xor     ax, ax
.ret:   FARRET  10

; color_inval: BX = index; repaint that button
color_inval:
        push    word [hdlg]
        lea     ax, [bx+COLBASE]
        push    ax
        API     USER, 91                ; GetDlgItem
        push    ax
        xor     ax, ax
        push    ax
        push    ax
        PUSHI   1
        API     USER, 125               ; InvalidateRect(hwnd, NULL, TRUE)
        ret

; color_draw: WM_DRAWITEM, lParam -> DRAWITEMSTRUCT (+2 CtlID, +12 hDC, +14 rcItem)
color_draw:
        les     bx, [bp+6]
        mov     ax, [es:bx+2]
        sub     ax, COLBASE
        cmp     ax, 16
        jb      .mine
        xor     ax, ax
        ret
.mine:  mov     [cidx], ax
        mov     ax, [es:bx+12]
        mov     [cdc], ax
        mov     ax, [es:bx+14]
        mov     [rc], ax
        mov     ax, [es:bx+16]
        mov     [rc+2], ax
        mov     ax, [es:bx+18]
        mov     [rc+4], ax
        mov     ax, [es:bx+20]
        mov     [rc+6], ax
        mov     si, [cidx]
        shl     si, 1
        shl     si, 1
        push    word [colors+si+2]
        push    word [colors+si]
        API     GDI, 66                 ; CreateSolidBrush
        mov     [cbr], ax
        push    word [cdc]
        PUSHD   rc
        push    word [cbr]
        API     USER, 81                ; FillRect
        push    word [cbr]
        API     GDI, 69                 ; DeleteObject
        PUSHI   4                       ; BLACK_BRUSH
        API     GDI, 87                 ; GetStockObject
        mov     [cbr], ax
        call    frame_rc                ; every swatch gets a thin frame
        mov     ax, [cidx]
        cmp     ax, [csel]
        jne     .done
        call    frame_rc                ; the selected one a thick frame
        call    frame_rc
.done:  mov     ax, 1
        ret

; frame_rc: FrameRect(cdc, rc, cbr), then shrink rc by one pixel
frame_rc:
        push    word [cdc]
        PUSHD   rc
        push    word [cbr]
        API     USER, 83                ; FrameRect
        inc     word [rc]
        inc     word [rc+2]
        dec     word [rc+4]
        dec     word [rc+6]
        ret
