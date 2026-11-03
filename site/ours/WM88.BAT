@ECHO OFF
REM WM88 bridge launcher: run this from the C:\WINDOWS directory.
REM It installs the WM88TSR translation TSR, then starts Windows 3.0
REM in real mode with the original WINMINE.EXE.
IF NOT EXIST WM88TSR.COM GOTO NOTSR
IF NOT EXIST WINMINE.EXE GOTO NOMINE
WM88TSR.COM
WIN /R WINMINE.EXE
GOTO END
:NOTSR
ECHO WM88TSR.COM not found in the current directory.
GOTO END
:NOMINE
ECHO WINMINE.EXE not found in the current directory.
:END
