@ECHO OFF
REM WM88 bridge installer. Run this from the directory that contains the
REM WM88 files, at a DOS prompt, BEFORE starting Windows.
REM It installs our small SHELL.DLL into C:\WINDOWS\SYSTEM. Windows 3.0
REM ships no SHELL.DLL; the original WINMINE.EXE imports ShellAbout from
REM module SHELL (ordinal 22), so this shim is required. If a SHELL.DLL
REM already exists it is backed up to SHELL.BAK first.
IF NOT EXIST C:\WINDOWS\SYSTEM\NUL GOTO NOWIN
IF EXIST C:\WINDOWS\SYSTEM\SHELL.DLL IF NOT EXIST C:\WINDOWS\SYSTEM\SHELL.BAK COPY C:\WINDOWS\SYSTEM\SHELL.DLL C:\WINDOWS\SYSTEM\SHELL.BAK
COPY SHELL.DLL C:\WINDOWS\SYSTEM\SHELL.DLL
COPY WM88TSR.COM C:\WINDOWS\WM88TSR.COM
COPY WM88.BAT C:\WINDOWS\WM88.BAT
ECHO.
ECHO Installed. Next steps:
ECHO   1. Copy your own unmodified WINMINE.EXE (from Windows 3.1) to C:\WINDOWS
ECHO   2. CD \WINDOWS and run WM88.BAT
GOTO END
:NOWIN
ECHO C:\WINDOWS\SYSTEM not found. Install Windows 3.0 first, or edit this file
ECHO to point at your Windows directory.
:END
