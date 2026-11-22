# COMMDLG.DLL for Windows 3.0 real mode on an 8088

A replacement for the Windows 3.1 common dialog library, written for Windows 3.0 real mode
and the 8086 instruction set. Microsoft's COMMDLG.DLL is marked protected-mode only, has
80186 code and 64 KB of code in eight segments; games that use it (Entertainment Pack 4's
Chess directly, Tic Tac Drop through CMDIALOG.VBX) cannot load it in real mode unconverted.

| | |
| --- | --- |
| file | about 8.4 KB |
| code | one fixed segment, about 5 KB, 8086 only (`cpu 8086` in nasm) |
| data | one fixed segment, about 2 KB, plus a 2 KB local heap (edit controls keep their text there) |

## Entry points

| ordinal | name | |
| --- | --- | --- |
| 1, 2 | GetOpenFileName, GetSaveFileName | file name edit, files list, directories and drives list, file types (first pattern of each), read-only box; OFN_FILEMUSTEXIST, OFN_OVERWRITEPROMPT, OFN_HIDEREADONLY, OFN_READONLY, OFN_NOCHANGEDIR, default extension, nFileOffset/nFileExtension, lpstrFileTitle, FNERR_BUFFERTOOSMALL, hook (OFN_ENABLEHOOK) |
| 5 | ChooseColor | the 16 basic colours; CC_RGBINIT, hook. No custom colours. |
| 15 | ChooseFont | typefaces (EnumFonts on the screen, or the printer DC with CF_PRINTERFONTS), style, size, strikeout/underline (CF_EFFECTS); CF_INITTOLOGFONTSTRUCT; fills LOGFONT, iPointSize, nFontType; hook |
| 20 | PrintDlg | printer from WIN.INI `[windows] device=`; dialog with copies (or PD_RETURNDEFAULT); DEVNAMES; PD_RETURNDC / PD_RETURNIC; PDERR_NODEFAULTPRN when no printer is set up. No DEVMODE, no page range. |
| 26 | CommDlgExtendedError | |
| 27 | GetFileTitle | |
| 11, 12 | FindText, ReplaceText | return NULL (CDERR_DIALOGFAILURE) |
| 6, 7, 8, 16, 19, 21, 22 | dialog and enumeration procedures | exported under the original names |
| 28 | WEP | |

Custom templates (`*_ENABLETEMPLATE`) are ignored; hooks see the Windows 3.1 control ids
(edt1, lst1, lst2, cmb1, stc1, chx1, ...). Drives are listed in the directories box (as in
Windows 3.0's own dialogs) rather than a separate drives combo box.

## Build

    commdlg/build.sh OUTDIR            # COMMDLG.DLL
    CDTEST=1 commdlg/build.sh OUTDIR   # also CDTEST.EXE, which opens every dialog in turn

`mkne.py` links nasm's flat output into an NE file: relocations are labels the source macros
emit (`API MODULE, ordinal` far calls). Exported functions use the standard
`push ds / pop ax / nop` prologue that KERNEL rewrites to load the data segment, and a real-mode
far frame (`inc bp`), so KERNEL's stack walk can follow them.
