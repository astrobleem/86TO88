; COMMDLG.DLL for Windows 3.0 real mode on an 8088 -- a small replacement for the Windows 3.1
; common dialogs: GetOpenFileName, GetSaveFileName, ChooseColor, ChooseFont, PrintDlg,
; CommDlgExtendedError, GetFileTitle (FindText/ReplaceText report failure).
; 8086 instructions only; one fixed code segment and one fixed data segment with a local
; heap (edit controls of the dialogs keep their text there). Built with nasm + mkne.py.
[map all commdlg.map]
cpu 8086
%include "macros.inc"

section code vstart=0

; ---------------------------------------------------------------- library entry
; KERNEL calls it far with DI = hInstance, DS = data segment, CX = heap size
LibEntry:
        mov     [hInst], di
        jcxz    .noheap
        push    ds
        xor     ax, ax
        push    ax
        push    cx
        API     KERNEL, 4               ; LocalInit(ds, 0, cx)
.noheap:
        mov     ax, 1
        retf

FARPROC WEP
        mov     ax, 1
        FARRET  2

FARPROC CommDlgExtendedError
        mov     ax, [gErr]
        xor     dx, dx
        FARRET  0

FARPROC FindText
        mov     word [gErr], 6          ; CDERR_DIALOGFAILURE: not provided
        xor     ax, ax
        FARRET  4

; ---------------------------------------------------------------- GetFileTitle(file, title, cb)
; returns 0, or the size needed when cb is too small
FARPROC GetFileTitle
        les     si, [bp+12]             ; file
        call    name_part_es            ; ES:SI -> name part
        mov     di, si
        xor     cx, cx
.len:   cmp     byte [es:di], 0
        je      .gl
        inc     di
        inc     cx
        jmp     .len
.gl:    inc     cx                      ; with terminator
        mov     ax, cx
        cmp     cx, [bp+6]
        ja      .done
        push    ds
        push    es
        pop     ds                      ; DS:SI source
        les     di, [bp+8]
        rep     movsb
        pop     ds
        xor     ax, ax
.done:  FARRET  10

; name_part_es: ES:SI string -> ES:SI after its last '\' or ':'
name_part_es:
        mov     di, si
.l:     mov     al, [es:di]
        or      al, al
        jz      .e
        inc     di
        cmp     al, '\'
        je      .s
        cmp     al, ':'
        jne     .l
.s:     mov     si, di
        jmp     .l
.e:     ret

; ================================================================ file dialogs
FARPROC GetOpenFileName
        xor     ax, ax
        jmp     short ofn_common
FARPROC GetSaveFileName
        mov     ax, 1
ofn_common:
        mov     [fmode], ax
        mov     word [gErr], 0
        les     bx, [bp+6]
        mov     [ofn], bx
        mov     [ofn+2], es
        ; remember the current drive and directory (OFN_NOCHANGEDIR restores them)
        mov     ah, 19h
        int     21h
        mov     [savedrv], al
        mov     ah, 47h
        mov     dl, 0
        mov     si, savedir+1
        mov     byte [savedir], '\'
        int     21h
        mov     ax, 6                   ; FileOpenDlgProc
        mov     si, dlg_file
        mov     cx, dlg_file_end - dlg_file
        call    run_dialog              ; AX = dialog result
        push    ax
        les     bx, [ofn]
        test    byte [es:bx+48], 8      ; OFN_NOCHANGEDIR
        jz      .keep
        mov     dl, [savedrv]
        mov     ah, 0Eh
        int     21h
        mov     dx, savedir
        mov     ah, 3Bh
        int     21h
.keep:  pop     ax
        cmp     ax, 1
        je      .ok
        xor     ax, ax
.ok:    FARRET  4

; run_dialog: AX = ordinal of our dialog procedure, DS:SI/CX = template; [ofn] = lParam
; (the caller's structure). Returns the EndDialog value, or 0 with gErr set on failure.
run_dialog:
        push    bp
        mov     bp, sp
        push    si
        push    cx
        push    word [hInst]
        xor     dx, dx
        push    dx
        push    ax
        API     KERNEL, 50              ; GetProcAddress(hInst, MAKEINTRESOURCE(ord))
        mov     [dproc], ax
        mov     [dproc+2], dx
        mov     ax, 2                   ; GMEM_MOVEABLE
        push    ax
        xor     ax, ax
        push    ax
        push    word [bp-4]
        API     KERNEL, 15              ; GlobalAlloc
        or      ax, ax
        jz      .fail
        mov     [htmpl], ax
        push    ax
        API     KERNEL, 18              ; GlobalLock -> DX:AX
        mov     es, dx
        mov     di, ax
        mov     si, [bp-2]
        mov     cx, [bp-4]
        rep     movsb
        push    word [htmpl]
        API     KERNEL, 19              ; GlobalUnlock
        push    word [hInst]
        push    word [htmpl]
        les     bx, [ofn]
        push    word [es:bx+4]          ; hwndOwner (same offset in all four structures)
        push    word [dproc+2]
        push    word [dproc]
        push    word [ofn+2]
        push    word [ofn]
        API     USER, 240               ; DialogBoxIndirectParam
        push    ax
        push    word [htmpl]
        API     KERNEL, 17              ; GlobalFree
        pop     ax
        cmp     ax, -1
        jne     .done
.fail:  mov     word [gErr], 6          ; CDERR_DIALOGFAILURE
        xor     ax, ax
.done:  mov     sp, bp
        pop     bp
        ret

; call_hook: if [hookflag] says so, pass the current message to the application's hook
; ([hook]); returns AX (0 = not handled). Uses the FARPROC frame of the dialog procedure.
call_hook:
        xor     ax, ax
        cmp     word [hook+2], 0
        je      .r
        push    word [bp+14]
        push    word [bp+12]
        push    word [bp+10]
        push    word [bp+8]
        push    word [bp+6]
        call    far [hook]
.r:     ret

; load_hook: ES:BX = structure, AX = flag mask, CX = flag word offset, DX = hook offset
load_hook:
        mov     word [hook], 0
        mov     word [hook+2], 0
        mov     si, cx
        test    [es:bx+si], ax
        jz      .r
        mov     si, dx
        mov     ax, [es:bx+si]
        mov     [hook], ax
        mov     ax, [es:bx+si+2]
        mov     [hook+2], ax
.r:     ret

; ---------------------------------------------------------------- the file dialog procedure
; FileDlgProc(hDlg, msg, wParam, lParam): [bp+14] hDlg, [bp+12] msg, [bp+10] wParam, [bp+6] lParam
FARPROC FileDlgProc
        mov     ax, [bp+12]
        cmp     ax, WM_INITDIALOG
        jne     .notinit
        mov     ax, [bp+14]
        mov     [hdlg], ax
        les     bx, [ofn]
        mov     ax, 20h                 ; OFN_ENABLEHOOK
        mov     cx, 48
        mov     dx, 64
        call    load_hook
        call    file_init
        call    call_hook
        mov     ax, 1
        jmp     .ret
.notinit:
        call    call_hook
        or      ax, ax
        jnz     .ret
        cmp     word [bp+12], WM_COMMAND
        jne     .no
        call    file_command
        jmp     .ret
.no:    xor     ax, ax
.ret:   FARRET  10

file_init:
        les     bx, [ofn]
        ; caption
        mov     ax, [es:bx+44]
        or      ax, [es:bx+46]
        jz      .deftitle
        push    es
        push    bx
        les     bx, [es:bx+44]
        cmp     byte [es:bx], 0         ; an empty title also means the default one
        pop     bx
        pop     es
        je      .deftitle
        push    word [hdlg]
        push    word [es:bx+46]
        push    word [es:bx+44]
        jmp     short .settitle
.deftitle:
        push    word [hdlg]
        push    ds
        mov     ax, s_open
        cmp     word [fmode], 0
        je      .t1
        mov     ax, s_saveas
.t1:    push    ax
.settitle:
        API     USER, 37                ; SetWindowText
        ; file types: description / pattern pairs
        les     bx, [ofn]
        mov     si, [es:bx+8]
        mov     ax, [es:bx+10]
        mov     [filt+2], ax
        mov     [filt], si
        or      ax, si
        jz      .nofilt
.fl:    mov     es, [filt+2]
        cmp     byte [es:si], 0
        je      .fdone
        push    word [hdlg]
        mov     ax, cmb1
        push    ax
        mov     ax, CB_ADDSTRING
        push    ax
        xor     ax, ax
        push    ax
        push    es
        push    si
        API     USER, 101               ; SendDlgItemMessage(cmb1, CB_ADDSTRING, 0, desc)
        mov     es, [filt+2]
        call    skipz                   ; past the description
        call    skipz                   ; past the pattern
        jmp     .fl
.fdone: les     bx, [ofn]
        mov     ax, [es:bx+20]          ; nFilterIndex (1-based)
        or      ax, ax
        jz      .f0
        dec     ax
.f0:    call    select_filter           ; patbuf = pattern of entry AX
        jmp     short .initdir
.nofilt:
        mov     word [patbuf], '*.'
        mov     word [patbuf+2], '*'
.initdir:
        ; initial directory
        les     bx, [ofn]
        mov     ax, [es:bx+40]
        or      ax, [es:bx+42]
        jz      .file
        PUSHD   tmp
        push    word [es:bx+42]
        push    word [es:bx+40]
        API     KERNEL, 88              ; lstrcpy(tmp, lpstrInitialDir)
        mov     si, tmp
        call    add_slash_pattern       ; tmp += "\" + patbuf
        mov     si, tmp
        call    fill_lists
.file:  ; initial file name
        les     bx, [ofn]
        les     si, [es:bx+24]
        mov     ax, es
        or      ax, si
        jz      .fill
        cmp     byte [es:si], 0
        je      .fill
        call    has_wild_es
        jc      .fill
        push    word [hdlg]
        mov     ax, edt1
        push    ax
        push    es
        push    si
        API     USER, 92                ; SetDlgItemText(edt1, lpstrFile)
        mov     byte [keepname], 1
        jmp     short .fill2
.fill:  mov     byte [keepname], 0
.fill2: mov     si, patbuf
        call    fill_lists
        ; read-only box
        les     bx, [ofn]
        test    byte [es:bx+48], 4      ; OFN_HIDEREADONLY
        jz      .ro
        push    word [hdlg]
        mov     ax, chx1
        push    ax
        API     USER, 91                ; GetDlgItem
        push    ax
        xor     ax, ax
        push    ax
        API     USER, 42                ; ShowWindow(SW_HIDE)
        ret
.ro:    test    byte [es:bx+48], 1      ; OFN_READONLY
        jz      .r
        push    word [hdlg]
        mov     ax, chx1
        push    ax
        mov     ax, 1
        push    ax
        API     USER, 97                ; CheckDlgButton
.r:     ret

; skipz: ES:SI -> past the next terminating zero
skipz:  mov     al, [es:si]
        inc     si
        or      al, al
        jnz     skipz
        ret

; select_filter: AX = index of a file-type entry; copy its pattern to patbuf, select it
select_filter:
        mov     [fidx], ax
        push    word [hdlg]
        mov     bx, cmb1
        push    bx
        mov     bx, CB_SETCURSEL
        push    bx
        push    ax
        xor     bx, bx
        push    bx
        push    bx
        API     USER, 101
        mov     cx, [fidx]
        mov     si, [filt]
        mov     es, [filt+2]
.sk:    jcxz    .here
        call    skipz
        call    skipz
        cmp     byte [es:si], 0
        je      .none
        dec     cx
        jmp     .sk
.here:  cmp     byte [es:si], 0
        je      .none
        call    skipz                   ; to the pattern
        mov     di, patbuf
        mov     cx, 79
.cp:    mov     al, [es:si]
        inc     si
        mov     [di], al
        inc     di
        or      al, al
        jz      .r
        cmp     al, ';'                 ; several patterns: DlgDirList takes one, use the first
        je      .semi
        loop    .cp
        mov     byte [di], 0
.r:     ret
.semi:  mov     byte [di-1], 0
        ret
.none:  mov     word [patbuf], '*.'
        mov     word [patbuf+2], '*'
        ret

; has_wild_es: CF set if the string ES:SI contains '*' or '?'
has_wild_es:
        push    si
.l:     mov     al, [es:si]
        inc     si
        or      al, al
        jz      .no
        cmp     al, '*'
        je      .y
        cmp     al, '?'
        jne     .l
.y:     pop     si
        stc
        ret
.no:    pop     si
        clc
        ret

; add_slash_pattern: DS:SI path (in tmp-sized buffer) += ['\'] + patbuf
add_slash_pattern:
        mov     di, si
.e:     cmp     byte [di], 0
        je      .end
        inc     di
        jmp     .e
.end:   cmp     di, si
        je      .cp
        mov     al, [di-1]
        cmp     al, '\'
        je      .cp
        cmp     al, ':'
        je      .cp
        mov     byte [di], '\'
        inc     di
.cp:    push    si
        mov     si, patbuf
.c2:    lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .c2
        pop     si
        ret

; fill_lists: DS:SI = path spec (may change the current directory). Lists files of the
; spec in lst1, the directory in stc1, subdirectories and drives in lst2. CF set when the
; spec named no valid directory (nothing changed).
fill_lists:
        mov     di, spec
.c:     lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .c
        push    word [hdlg]
        PUSHD   spec
        mov     ax, lst1
        push    ax
        mov     ax, stc1
        push    ax
        xor     ax, ax
        push    ax
        API     USER, 100               ; DlgDirList(hDlg, spec, lst1, stc1, 0)
        or      ax, ax
        jnz     .ok
        stc
        ret
.ok:    mov     word [spec], '*.'
        mov     word [spec+2], '*'
        push    word [hdlg]
        PUSHD   spec
        mov     ax, lst2
        push    ax
        xor     ax, ax
        push    ax
        mov     ax, 0C010h              ; DDL_EXCLUSIVE | DDL_DRIVES | DDL_DIRECTORY
        push    ax
        API     USER, 100
        call    show_dir
        cmp     byte [keepname], 0
        jne     .k
        push    word [hdlg]
        mov     ax, edt1
        push    ax
        PUSHD   patbuf
        API     USER, 92                ; SetDlgItemText(edt1, pattern)
.k:     clc
        ret

; show_dir: stc1 = current drive and directory, lower case (as Windows 3.1 shows it)
show_dir:
        mov     ah, 19h
        int     21h
        add     al, 'a'
        mov     [spec], al
        mov     word [spec+1], 5C3Ah            ; ':\'
        mov     si, spec+3
        mov     dl, 0
        mov     ah, 47h
        int     21h
        mov     si, spec
.lc:    mov     al, [si]
        or      al, al
        jz      .set
        cmp     al, 'A'
        jb      .n
        cmp     al, 'Z'
        ja      .n
        add     byte [si], 20h
.n:     inc     si
        jmp     .lc
.set:   push    word [hdlg]
        PUSHI   stc1
        PUSHD   spec
        API     USER, 92                ; SetDlgItemText(stc1)
        ret

; file_command: WM_COMMAND in the file dialog; returns AX
file_command:
        mov     ax, [bp+10]             ; control id
        cmp     ax, lst1
        jne     .n1
        mov     ax, [bp+8]              ; notification (HIWORD lParam)
        cmp     ax, LBN_SELCHANGE
        je      .sel1
        cmp     ax, LBN_DBLCLK
        jne     .zero
        call    sel_file
        jmp     file_ok
.sel1:  call    sel_file
        jmp     .one
.n1:    cmp     ax, lst2
        jne     .n2
        cmp     word [bp+8], LBN_DBLCLK
        jne     .zero
        push    word [hdlg]
        PUSHD   tmp
        mov     ax, lst2
        push    ax
        API     USER, 99                ; DlgDirSelect -> "dir\" or "c:"
        mov     si, tmp
        call    add_slash_pattern
        mov     byte [keepname], 0
        mov     si, tmp
        call    fill_lists
        jmp     .one
.n2:    cmp     ax, cmb1
        jne     .n3
        cmp     word [bp+8], CBN_SELCHANGE
        jne     .zero
        push    word [hdlg]
        mov     ax, cmb1
        push    ax
        mov     ax, CB_GETCURSEL
        push    ax
        xor     ax, ax
        push    ax
        push    ax
        push    ax
        API     USER, 101
        call    select_filter
        mov     byte [keepname], 0
        mov     si, patbuf
        call    fill_lists
        jmp     .one
.n3:    cmp     ax, IDOK
        jne     .n4
        jmp     file_ok
.n4:    cmp     ax, IDCANCEL
        jne     .zero
        push    word [hdlg]
        xor     ax, ax
        push    ax
        API     USER, 88                ; EndDialog(0)
.one:   mov     ax, 1
        ret
.zero:  xor     ax, ax
        ret

sel_file:
        push    word [hdlg]
        PUSHD   tmp
        mov     ax, lst1
        push    ax
        API     USER, 99                ; DlgDirSelect(hDlg, tmp, lst1)
        push    word [hdlg]
        mov     ax, edt1
        push    ax
        PUSHD   tmp
        API     USER, 92
        mov     byte [keepname], 1
        ret

; file_ok: OK pressed (or a file double-clicked)
file_ok:
        push    word [hdlg]
        mov     ax, edt1
        push    ax
        PUSHD   tmp
        mov     ax, 128
        push    ax
        API     USER, 93                ; GetDlgItemText
        or      ax, ax
        jz      .beep
        ; uppercase, trim
        mov     si, tmp
.up:    mov     al, [si]
        or      al, al
        jz      .upd
        cmp     al, 'a'
        jb      .un
        cmp     al, 'z'
        ja      .un
        sub     byte [si], 20h
.un:    inc     si
        jmp     .up
.upd:   push    ds
        pop     es
        mov     si, tmp
        call    has_wild_es
        jnc     .notwild
        ; a pattern: a new filter (with any path in front of it)
        mov     si, tmp
        call    name_part_ds
        mov     di, patbuf
.cpat:  lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .cpat
        mov     byte [keepname], 0
        mov     si, tmp
        call    fill_lists
        jnc     .one
        jmp     .beep
.notwild:
        ; a directory or drive?
        mov     si, tmp
        mov     di, spec2
.cd:    lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .cd
        mov     si, spec2
        call    add_slash_pattern
        mov     byte [keepname], 0
        mov     si, spec2
        call    fill_lists
        jnc     .one                    ; was a directory: listed it
        mov     byte [keepname], 1
        ; a file: make the full path in fullbuf
        call    full_path
        ; default extension
        les     bx, [ofn]
        mov     ax, [es:bx+56]
        or      ax, [es:bx+58]
        jz      .noext
        mov     si, fullbuf
        call    name_part_ds
.dot:   lodsb
        or      al, al
        jz      .adddot
        cmp     al, '.'
        je      .noext
        jmp     .dot
.adddot:
        mov     byte [si-1], '.'
        mov     di, si
        les     bx, [ofn]
        les     si, [es:bx+56]
        mov     cx, 3
.de:    mov     al, [es:si]
        inc     si
        mov     [di], al
        inc     di
        or      al, al
        jz      .noext
        loop    .de
        mov     byte [di], 0
.noext:
        ; exists?
        mov     dx, fullbuf
        mov     ax, 4300h
        int     21h                     ; CF = not found
        mov     al, 0
        jc      .ex
        mov     al, 1
.ex:    mov     [exists], al
        les     bx, [ofn]
        cmp     word [fmode], 0
        jne     .save
        test    byte [es:bx+49], 10h    ; OFN_FILEMUSTEXIST (1000h)
        jz      .store
        cmp     byte [exists], 0
        jne     .store
        mov     ax, s_notfound
        mov     cx, MB_OK | MB_ICONEXCL
        call    msgbox
        jmp     .one
.save:  test    byte [es:bx+48], 2      ; OFN_OVERWRITEPROMPT
        jz      .store
        cmp     byte [exists], 0
        je      .store
        mov     ax, s_replace
        mov     cx, MB_YESNO | MB_ICONEXCL
        call    msgbox
        cmp     ax, IDYES
        je      .store
        jmp     .one
.beep:  xor     ax, ax
        push    ax
        API     USER, 104               ; MessageBeep
.one:   mov     ax, 1
        ret
.store: call    store_result
        jmp     .one

; name_part_ds: DS:SI -> after the last '\' or ':'
name_part_ds:
        mov     di, si
.l:     mov     al, [di]
        or      al, al
        jz      .e
        inc     di
        cmp     al, '\'
        je      .s
        cmp     al, ':'
        jne     .l
.s:     mov     si, di
        jmp     .l
.e:     ret

; full_path: fullbuf = tmp made absolute with the current drive and directory
full_path:
        mov     di, fullbuf
        mov     si, tmp
        cmp     byte [si+1], ':'
        je      .hasdrv
        mov     ah, 19h
        int     21h
        add     al, 'A'
        mov     [di], al
        mov     byte [di+1], ':'
        add     di, 2
        jmp     short .dir
.hasdrv:
        mov     ax, [si]
        mov     [di], ax
        add     di, 2
        add     si, 2
.dir:   cmp     byte [si], '\'
        je      .rest                   ; rooted
        mov     byte [di], '\'
        inc     di
        push    si
        mov     dl, [fullbuf]
        sub     dl, 'A'-1
        mov     si, di
        mov     ah, 47h
        int     21h                     ; current directory of that drive, no leading '\'
        pop     si
.end:   cmp     byte [di], 0
        je      .ended
        inc     di
        jmp     .end
.ended: cmp     byte [di-1], '\'
        je      .rest
        mov     byte [di], '\'
        inc     di
.rest:  lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .rest
        ret

; msgbox: AX = text (in DS), CX = style; caption = dialog title. Returns AX.
msgbox:
        push    ax
        push    cx
        push    word [hdlg]
        PUSHD   spec2                   ; caption buffer
        mov     ax, 40
        push    ax
        API     USER, 36                ; GetWindowText(hDlg, spec2, 40)
        ; text = fullbuf + message
        mov     si, fullbuf
        mov     di, spec
.c1:    lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .c1
        dec     di
        pop     cx
        pop     si
.c2:    lodsb
        mov     [di], al
        inc     di
        or      al, al
        jnz     .c2
        push    word [hdlg]
        PUSHD   spec
        PUSHD   spec2
        push    cx
        API     USER, 1                 ; MessageBox
        ret

; store_result: copy fullbuf into the caller's structure and end the dialog
store_result:
        mov     si, fullbuf
        xor     cx, cx
.l:     cmp     byte [si], 0
        je      .gl
        inc     si
        inc     cx
        jmp     .l
.gl:    inc     cx
        les     bx, [ofn]
        cmp     word [es:bx+30], 0      ; nMaxFile high word
        jne     .fits
        cmp     cx, [es:bx+28]
        jbe     .fits
        mov     word [gErr], 3003h      ; FNERR_BUFFERTOOSMALL
        les     di, [es:bx+24]
        mov     ax, es
        or      ax, di
        jz      .fail
        mov     [es:di], cx             ; the size needed
.fail:  push    word [hdlg]
        xor     ax, ax
        push    ax
        API     USER, 88
        ret
.fits:  les     di, [es:bx+24]
        mov     si, fullbuf
        push    cx
        rep     movsb
        pop     cx
        ; nFileOffset, nFileExtension
        mov     si, fullbuf
        call    name_part_ds
        mov     ax, si
        sub     ax, fullbuf
        les     bx, [ofn]
        mov     [es:bx+52], ax
        mov     dx, cx
        dec     dx                      ; no extension: offset of the terminator
.x:     lodsb
        or      al, al
        jz      .xe
        cmp     al, '.'
        jne     .x
        mov     dx, si
        sub     dx, fullbuf
.xe:    mov     [es:bx+54], dx
        ; file title
        mov     ax, [es:bx+32]
        or      ax, [es:bx+34]
        jz      .nt
        mov     cx, [es:bx+36]
        jcxz    .nt
        mov     si, fullbuf
        add     si, [es:bx+52]
        les     di, [es:bx+32]
.tc:    lodsb
        stosb
        or      al, al
        jz      .nt
        loop    .tc
        mov     byte [es:di-1], 0
.nt:    ; filter index and read-only state
        les     bx, [ofn]
        mov     ax, [fidx]
        inc     ax
        mov     [es:bx+20], ax
        mov     word [es:bx+22], 0
        push    word [hdlg]
        mov     ax, chx1
        push    ax
        API     USER, 98                ; IsDlgButtonChecked
        les     bx, [ofn]
        and     byte [es:bx+48], 0FEh
        or      ax, ax
        jz      .nr
        or      byte [es:bx+48], 1      ; OFN_READONLY
.nr:    push    word [hdlg]
        mov     ax, 1
        push    ax
        API     USER, 88                ; EndDialog(1)
        ret

%include "color.inc"
%include "font.inc"
%include "print.inc"

; ================================================================ data
section data vstart=0 align=16 follows=code
        times 16 db 0                   ; instance data header (KERNEL keeps the local heap pointer here)
hInst   dw      0
gErr    dw      0
fmode   dw      0
ofn     dd      0
hook    dd      0
dproc   dd      0
htmpl   dw      0
hdlg    dw      0
filt    dd      0
fidx    dw      0
keepname db     0
exists  db      0
savedrv db      0
s_open  db      'Open', 0
s_saveas db     'Save As', 0
s_notfound db   0Dh, 0Ah, 'File not found.', 0
s_replace db    ' already exists.', 0Dh, 0Ah, 'Replace it?', 0
savedir times 68 db 0
patbuf  times 80 db 0
tmp     times 130 db 0
spec    times 200 db 0
spec2   times 140 db 0
fullbuf times 140 db 0

dlg_file:
        DLG     DLGSTYLE, 11, 20, 16, 262, 132
        DLGCAP  'Open'
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, 'File &Name:', 6, 6, 90, 9
        ITEM    C_EDIT, edt1, CHILD|WS_BORDER|WS_TABSTOP|ES_AUTOHSCROLL, '', 6, 16, 90, 12
        ITEM    C_LISTBOX, lst1, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|LBS_SORT|LBS_NOTIFY, '', 6, 30, 90, 68
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, '&Directories:', 104, 6, 96, 9
        ITEM    C_STATIC, stc1, CHILD|SS_LEFT|SS_NOPREFIX, '', 104, 16, 96, 9
        ITEM    C_LISTBOX, lst2, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|LBS_SORT|LBS_NOTIFY, '', 104, 30, 96, 68
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, 'List Files of &Type:', 6, 102, 96, 9
        ITEM    C_COMBO, cmb1, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|CBS_DROPDOWNLIST, '', 6, 112, 96, 50
        ITEM    C_BUTTON, chx1, CHILD|WS_TABSTOP|BS_AUTOCHECK, '&Read Only', 104, 112, 70, 12
        ITEM    C_BUTTON, IDOK, CHILD|WS_TABSTOP|BS_DEFPUSH, 'OK', 206, 6, 50, 14
        ITEM    C_BUTTON, IDCANCEL, CHILD|WS_TABSTOP|BS_PUSHBUTTON, 'Cancel', 206, 24, 50, 14
dlg_file_end:

%include "data2.inc"
