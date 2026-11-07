"""Builds the three replacement DLLs Glider for Windows 3 needs on real-mode Windows 3.0: MMSYSTEM, COMMDLG, WAVEMIX.

What Glider actually calls (traced from its import relocations and call sites):
  MMSYSTEM  joyGetNumDevs 101, joyGetDevCaps 102, joyGetPos 103 (joystick probe), timeGetTime 607 (frame pacing)
  COMMDLG   GetOpenFileName 1, GetSaveFileName 2 (house file dialogs)
  WAVEMIX   WaveMix* x10 (sound); Glider calls WaveMixInit first and, when it returns 0, clears its sound flag and
            never calls the others
  USER      OpenDriver 252, SendDriverMessage 251, CloseDriver 253 are Windows 3.1 exports Windows 3.0 lacks; the
            bridge points those three import records at the MMSYSTEM replacement (see gen_profile.py), which
            answers 'no joystick driver installed'.
Behaviour is the documented no-hardware behaviour of each API, not a blanket success answer:
  joyGetNumDevs -> 0 devices; joyGetDevCaps -> MMSYSERR_NODRIVER; joyGetPos -> JOYERR_UNPLUGGED
  timeGetTime -> real millisecond clock (USER.GetTickCount)
  GetOpenFileName/GetSaveFileName -> FALSE with no extended error (the user cancelled)
  WaveMixInit -> NULL (no wave device); every other WaveMix call -> 0 / FALSE
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_ne_dll import build_dll

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "shims"
OUT.mkdir(parents=True, exist_ok=True)

mmsystem = build_dll("MMSYSTEM", [
    (2, "SNDPLAYSOUND", "sndplaysound"),
    (101, "JOYGETNUMDEVS", "joygetnumdevs"),
    (102, "JOYGETDEVCAPS", "joygetdevcaps"),
    (103, "JOYGETPOS", "joygetpos"),
    (251, "SENDDRIVERMESSAGE", "senddrivermessage"),
    (252, "OPENDRIVER", "opendriver"),
    (253, "CLOSEDRIVER", "closedriver"),
    (607, "TIMEGETTIME", "timegettime"),
], r"""
sndplaysound:
 XOR AX, AX
 RETF 6
joygetnumdevs:
 XOR AX, AX
 RETF
joygetdevcaps:
 MOV AX, 6
 RETF 8
joygetpos:
 MOV AX, 167
 RETF 6
senddrivermessage:
 XOR AX, AX
 XOR DX, DX
 RETF 12
opendriver:
 XOR AX, AX
 RETF 12
closedriver:
 XOR AX, AX
 XOR DX, DX
 RETF 10
timegettime:
jmp_tick: DB 0EAh,255,255,0,0
""", imports=[("jmp_tick", "USER", 13)])

commdlg = build_dll("COMMDLG", [
    (1, "GETOPENFILENAME", "getopen"),
    (2, "GETSAVEFILENAME", "getsave"),
    (4, "COMMDLGEXTENDEDERROR", "extErr"),
], r"""
getopen:
getsave:
 XOR AX, AX
 RETF 4
extErr:
 XOR AX, AX
 RETF
""")

wm = [("WAVEMIXINIT", 0), ("WAVEMIXACTIVATE", 4), ("WAVEMIXOPENWAVE", 12), ("WAVEMIXOPENCHANNEL", 8),
      ("WAVEMIXPLAY", 4), ("WAVEMIXFLUSHCHANNEL", 8), ("WAVEMIXCLOSECHANNEL", 8), ("WAVEMIXPUMP", 0),
      ("WAVEMIXFREEWAVE", 6), ("WAVEMIXCLOSESESSION", 2)]
src = ""
for i, (nm, n) in enumerate(wm):
    src += "w%d:\n XOR AX, AX\n XOR DX, DX\n RETF%s\n" % (i, (" %d" % n) if n else "")
wavemix = build_dll("WAVEMIX", [(i + 1, nm, "w%d" % i) for i, (nm, n) in enumerate(wm)], src)

for name, blob in (("MMSYSTEM.DLL", mmsystem), ("COMMDLG.DLL", commdlg), ("WAVEMIX.DLL", wavemix)):
    (OUT / name).write_bytes(blob)
    print(name, len(blob))
