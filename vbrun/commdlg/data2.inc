; data for ChooseColor, ChooseFont and PrintDlg (included in the data section)
csel    dw      0
cidx    dw      0
cdc     dw      0
cbr     dw      0
rc      dw      0, 0, 0, 0
colors  dd      000000h, 000080h, 008000h, 008080h, 800000h, 800080h, 808000h, 808080h
        dd      0C0C0C0h, 0000FFh, 00FF00h, 00FFFFh, 0FF0000h, 0FF00FFh, 0FFFF00h, 0FFFFFFh
freldc  dw      0
fdc     dw      0
logpy   dw      0
fcount  dw      0
fsize   dw      0
fstyle  dw      0
fheight dw      0
fstrike db      0
funder  db      0
facebuf times 32 db 0
st_styles db    'Regular', 0, 'Italic', 0, 'Bold', 0, 'Bold Italic', 0, 0
st_sizes db     '8', 0, '9', 0, '10', 0, '11', 0, '12', 0, '14', 0, '16', 0, '18', 0, '20', 0
        db      '24', 0, '28', 0, '36', 0, '48', 0, '72', 0, 0
s_windows db    'windows', 0
s_device db     'device', 0
s_empty db      0
s_setup db      'Print Setup', 0
s_on    db      ' on ', 0
pdev    dw      0
pdrv    dw      0
pport   dw      0
l1      dw      0
l2      dw      0
l3      dw      0
devbuf  times 82 db 0

%macro SWATCH 3          ; index, x, y
        ITEM    C_BUTTON, COLBASE+%1, CHILD|WS_TABSTOP|BS_OWNERDRAW, '', %2, %3, 16, 12
%endmacro
dlg_color:
        DLG     DLGSTYLE, 19, 30, 20, 164, 70
        DLGCAP  'Color'
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, '&Basic Colors:', 6, 4, 100, 9
        SWATCH  0, 6, 16
        SWATCH  1, 25, 16
        SWATCH  2, 44, 16
        SWATCH  3, 63, 16
        SWATCH  4, 82, 16
        SWATCH  5, 101, 16
        SWATCH  6, 120, 16
        SWATCH  7, 139, 16
        SWATCH  8, 6, 32
        SWATCH  9, 25, 32
        SWATCH  10, 44, 32
        SWATCH  11, 63, 32
        SWATCH  12, 82, 32
        SWATCH  13, 101, 32
        SWATCH  14, 120, 32
        SWATCH  15, 139, 32
        ITEM    C_BUTTON, IDOK, CHILD|WS_TABSTOP|BS_DEFPUSH, 'OK', 36, 50, 44, 14
        ITEM    C_BUTTON, IDCANCEL, CHILD|WS_TABSTOP|BS_PUSHBUTTON, 'Cancel', 88, 50, 44, 14
dlg_color_end:

dlg_font:
        DLG     DLGSTYLE, 10, 20, 16, 232, 104
        DLGCAP  'Font'
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, '&Font:', 6, 4, 90, 9
        ITEM    C_COMBO, cmb1, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|CBS_DROPDOWNLIST|CBS_SORT, '', 6, 14, 90, 70
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, 'Font St&yle:', 102, 4, 60, 9
        ITEM    C_COMBO, cmb2, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|CBS_DROPDOWNLIST, '', 102, 14, 62, 50
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, '&Size:', 170, 4, 30, 9
        ITEM    C_COMBO, cmb3, CHILD|WS_BORDER|WS_VSCROLL|WS_TABSTOP|CBS_DROPDOWN, '', 170, 14, 30, 70
        ITEM    C_BUTTON, chx1, CHILD|WS_TABSTOP|BS_AUTOCHECK, 'Stri&keout', 6, 34, 60, 12
        ITEM    C_BUTTON, chx2, CHILD|WS_TABSTOP|BS_AUTOCHECK, '&Underline', 6, 48, 60, 12
        ITEM    C_BUTTON, IDOK, CHILD|WS_TABSTOP|BS_DEFPUSH, 'OK', 120, 84, 50, 14
        ITEM    C_BUTTON, IDCANCEL, CHILD|WS_TABSTOP|BS_PUSHBUTTON, 'Cancel', 176, 84, 50, 14
dlg_font_end:

dlg_print:
        DLG     DLGSTYLE, 5, 30, 20, 206, 58
        DLGCAP  'Print'
        ITEM    C_STATIC, stc1, CHILD|SS_LEFT|SS_NOPREFIX, '', 6, 6, 194, 9
        ITEM    C_STATIC, -1, CHILD|SS_LEFT, '&Copies:', 6, 24, 36, 9
        ITEM    C_EDIT, edt1, CHILD|WS_BORDER|WS_TABSTOP, '1', 44, 22, 24, 12
        ITEM    C_BUTTON, IDOK, CHILD|WS_TABSTOP|BS_DEFPUSH, 'OK', 96, 40, 50, 14
        ITEM    C_BUTTON, IDCANCEL, CHILD|WS_TABSTOP|BS_PUSHBUTTON, 'Cancel', 150, 40, 50, 14
dlg_print_end:
