import sys, struct

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

def parse(path):
    b = open(path, "rb").read()
    print(f"== {path} len={len(b)}")
    if b[:2] != b"MZ":
        print("  no MZ"); return
    ne = u32(b, 0x3C)
    print(f"  MZ e_cp={u16(b,4)} e_cparhdr={u16(b,8)} e_minalloc={u16(b,10)} e_lfanew={ne:#x}")
    if b[ne:ne+2] != b"NE":
        print("  no NE"); return
    h = ne
    print(f"  linker={b[h+2]}.{b[h+3]} enttab_off={u16(b,h+4):#x} enttab_len={u16(b,h+6)} "
          f"flags_prog={b[h+0xC]:#x} flags_app={b[h+0xD]:#x} autoDSseg={u16(b,h+0xE)} "
          f"heap={u16(b,h+0x10)} stack={u16(b,h+0x12)}")
    print(f"  CS:IP={u16(b,h+0x16)}:{u16(b,h+0x14):#x} SS:SP={u16(b,h+0x1A)}:{u16(b,h+0x18):#x} "
          f"cseg={u16(b,h+0x1C)} cmod={u16(b,h+0x1E)} cbnres={u16(b,h+0x20)}")
    segtab, rsrctab, restab, modtab, imptab = (u16(b,h+0x22), u16(b,h+0x24), u16(b,h+0x26),
                                              u16(b,h+0x28), u16(b,h+0x2A))
    nonres = u32(b, h+0x2C)
    print(f"  segtab={segtab:#x} rsrctab={rsrctab:#x} restab={restab:#x} modtab={modtab:#x} "
          f"imptab={imptab:#x} nonres_off={nonres:#x} cmovent={u16(b,h+0x30)} align={u16(b,h+0x32)} "
          f"exetyp={b[h+0x36]} expver={u16(b,h+0x3E):#06x}")
    align = u16(b, h+0x32)
    for i in range(u16(b, h+0x1C)):
        o = h + segtab + i*8
        off, ln, fl, al = struct.unpack_from("<HHHH", b, o)
        print(f"  seg{i+1}: file={off<<align:#x} len={ln:#x} flags={fl:#06x} alloc={al:#x}")
        if fl & 0x0100 and ln:
            fo = (off << align) + ln
            cnt = u16(b, fo)
            print(f"    relocs: count={cnt}")
            for r in range(cnt):
                ro = fo + 2 + r*8
                at, rf, rfo, mod, val = struct.unpack_from("<BBHHH", b, ro)
                print(f"    rec{r}: addrType={at} flags={rf} off={rfo:#x} modidx={mod} val={val}")
    # resident names
    print("  resident names:")
    o = h + restab
    while b[o]:
        ln = b[o]; nm = b[o+1:o+1+ln].decode("latin1"); print(f"    ord={u16(b,o+1+ln)} {nm}"); o += 1 + ln + 2
    o += 1
    # module reference table + imported names
    mods = []
    for i in range(u16(b, h+0x1E)):
        noff = u16(b, h + modtab + i*2)
        p = h + imptab + noff
        ln = b[p]; nm = b[p+1:p+1+ln].decode("latin1")
        mods.append(nm)
    print("  imported modules:", mods)
    # entry table
    print("  entry table:")
    o = h + u16(b, h+4); end = o + u16(b, h+6); ordinal = 1
    while o < end and b[o]:
        cnt, seg = b[o], b[o+1]; o += 2
        if seg == 0:
            print(f"    skip {cnt} (ord {ordinal}..{ordinal+cnt-1})"); ordinal += cnt
        elif seg == 0xFF:
            for _ in range(cnt):
                fl, segb, off = b[o], b[o+3], u16(b, o+4)
                print(f"    ord={ordinal} MOVABLE seg={segb} off={off:#x} flags={fl:#x}"); o += 6; ordinal += 1
        else:
            for _ in range(cnt):
                fl, off = b[o], u16(b, o+1)
                print(f"    ord={ordinal} FIXED seg={seg} off={off:#x} flags={fl:#x}"); o += 3; ordinal += 1
    # nonresident names
    if nonres and nonres < len(b):
        print("  nonresident names:")
        o = nonres
        while o < len(b) and b[o]:
            ln = b[o]; nm = b[o+1:o+1+ln].decode("latin1"); print(f"    ord={u16(b,o+1+ln)} {nm}"); o += 1 + ln + 2
    # import relocations grouped (for WINMINE)
    return b, ne

for p in sys.argv[1:]:
    parse(p)
    print()
