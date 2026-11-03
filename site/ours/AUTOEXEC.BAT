ECHO OFF
PATH C:\;C:\WINDOWS
SET TEMP=C:\WINDOWS\TEMP
CD \WINDOWS
ECHO 86TO88 judge fixture - 80286, Windows 3.0 real mode
ECHO The 286 browser demo is NOT an 8088 hardware proof.
WM88TSR.COM
IF ERRORLEVEL 1 GOTO FAILED
TEST88.COM
IF ERRORLEVEL 1 GOTO FAILED
RTEST2.COM
IF ERRORLEVEL 1 GOTO FAILED
ECHO Starting Windows 3.0 with WIN /R WINMINE.EXE
WIN /R WINMINE.EXE
GOTO END
:FAILED
ECHO VALIDATION FAILED - Windows was NOT launched.
ECHO Keep the error above for diagnosis. Do not report this run as passing.
:END
