; CDTEST.EXE -- calls every COMMDLG dialog in turn and shows what came back in a message box:
; GetOpenFileName, ChooseColor, ChooseFont, PrintDlg (PD_RETURNDC), GetSaveFileName.
; Test program for the 8086 COMMDLG; 8086 instructions only.
[map all cdtest.map]
cpu 8086
%include "macros.inc"

section code vstart=0
start:  API     KERNEL, 91              ; InitTask
        or      ax, ax
        jnz     .go
        jmp     quit
.go:    mov     [hInst], di
        xor     ax, ax
        push    ax
        API     KERNEL, 30              ; WaitEvent(0)
        push    word [hInst]
        API     USER, 5                 ; InitApp

        ; ---- GetOpenFileName
        mov     word [ofn], 72
        mov     word [ofn+8], filter
        mov     [ofn+10], ds
        mov     word [ofn+20], 1
        mov     word [ofn+24], fname
        mov     [ofn+26], ds
        mov     word [ofn+28], 128
        mov     word [ofn+48], 1004h    ; OFN_FILEMUSTEXIST | OFN_HIDEREADONLY
        PUSHD   ofn
        API     COMMDLG, 1
        mov     si, t_open
        call    result_file

        ; ---- ChooseColor
        mov     word [cc], 32
        mov     word [cc+8], 00FFh      ; red
        mov     word [cc+12], cust
        mov     [cc+14], ds
        mov     word [cc+16], 1         ; CC_RGBINIT
        PUSHD   cc
        API     COMMDLG, 5
        mov     di, msg
        mov     si, t_color
        call    cat
        or      ax, ax
        jz      .ccx
        mov     ax, [cc+10]
        call    hex4
        mov     ax, [cc+8]
        call    hex4
        jmp     short .ccs
.ccx:   call    cancelled
.ccs:   call    show

        ; ---- ChooseFont
        mov     word [cf], 46
        mov     word [cf+8], lf
        mov     [cf+10], ds
        mov     word [cf+14], 141h      ; CF_SCREENFONTS | CF_INITTOLOGFONTSTRUCT | CF_EFFECTS
        mov     word [lf], -13
        mov     word [lf+8], 700
        PUSHD   cf
        API     COMMDLG, 15
        mov     di, msg
        mov     si, t_font
        call    cat
        or      ax, ax
        jz      .cfx
        mov     si, lf+18
        call    cat
        mov     si, t_sp
        call    cat
        mov     ax, [cf+12]             ; iPointSize (tenths)
        call    hex4
        mov     si, t_h
        call    cat
        mov     ax, [lf]
        call    hex4
        mov     si, t_w
        call    cat
        mov     ax, [lf+8]
        call    hex4
        jmp     short .cfs
.cfx:   call    cancelled
.cfs:   call    show

        ; ---- PrintDlg
        mov     word [pd], 52
        mov     word [pd+12], 100h      ; PD_RETURNDC
        mov     word [pd+24], 1
        PUSHD   pd
        API     COMMDLG, 20
        mov     di, msg
        mov     si, t_print
        call    cat
        or      ax, ax
        jz      .pdx
        mov     si, t_dc
        call    cat
        mov     ax, [pd+10]
        call    hex4
        mov     si, t_copies
        call    cat
        mov     ax, [pd+24]
        call    hex4
        jmp     short .pds
.pdx:   call    exterr
.pds:   call    show

        ; ---- GetSaveFileName
        mov     byte [fname], 0
        mov     word [ofn+48], 6        ; OFN_OVERWRITEPROMPT | OFN_HIDEREADONLY
        mov     word [ofn+56], defext
        mov     [ofn+58], ds
        PUSHD   ofn
        API     COMMDLG, 2
        mov     si, t_save
        call    result_file
quit:   mov     ax, 4C00h
        int     21h

; result_file: AX = result of Get*FileName, SI = title
result_file:
        mov     di, msg
        call    cat
        or      ax, ax
        jz      .x
        mov     si, fname
        call    cat
        mov     si, t_off
        call    cat
        mov     ax, [ofn+52]
        call    hex4
        jmp     short show
.x:     call    exterr
        ; fall through
show:   mov     byte [di], 0
        xor     ax, ax
        push    ax
        PUSHD   msg
        PUSHD   t_cap
        xor     ax, ax
        push    ax
        API     USER, 1                 ; MessageBox
        ret

cancelled:
        mov     si, t_cancel
        jmp     cat

exterr: push    di
        API     COMMDLG, 26             ; CommDlgExtendedError
        pop     di
        push    ax
        mov     si, t_err
        call    cat
        pop     ax
        call    hex4
        ret

; cat: append DS:SI to DS:DI (DI left on the terminator position); keeps AX
cat:    push    ax
.l:     lodsb
        or      al, al
        jz      .e
        mov     [di], al
        inc     di
        jmp     .l
.e:     pop     ax
        ret

; hex4: AX as 4 hex digits at DS:DI
hex4:   mov     cx, 4
.l:     push    cx
        mov     cl, 4
        rol     ax, cl
        pop     cx
        push    ax
        and     al, 0Fh
        add     al, '0'
        cmp     al, '9'
        jbe     .d
        add     al, 7
.d:     mov     [di], al
        inc     di
        pop     ax
        loop    .l
        ret

section data vstart=0 align=16 follows=code
        times 16 db 0
hInst   dw      0
ofn     times 72 db 0
cc      times 32 db 0
cf      times 46 db 0
lf      dw      0, 0, 0, 0, 0
        db      0, 0, 0, 0, 0, 0, 0, 0
        db      'Helv'
        times 28 db 0
pd      times 52 db 0
cust    times 64 db 0
fname   times 130 db 0
msg     times 200 db 0
filter  db      'Text Files (*.TXT)', 0, '*.TXT', 0, 'Windows Files (*.INI)', 0, '*.INI', 0
        db      'All Files (*.*)', 0, '*.*', 0, 0
defext  db      'TXT', 0
t_cap   db      'CDTEST', 0
t_open  db      'GetOpenFileName: ', 0
t_save  db      'GetSaveFileName: ', 0
t_color db      'ChooseColor: ', 0
t_font  db      'ChooseFont: ', 0
t_print db      'PrintDlg: ', 0
t_sp    db      ' pt*10=', 0
t_h     db      ' h=', 0
t_w     db      ' w=', 0
t_dc    db      'hDC=', 0
t_copies db     ' copies=', 0
t_off   db      ' off=', 0
t_cancel db     'cancelled', 0
t_err   db      'FALSE, error ', 0
