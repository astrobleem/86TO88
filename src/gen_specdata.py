#!/usr/bin/env python3
"""Generate specimen-derived build inputs for build_tsr.py (run offline, once):
  artifacts/spec-crc.bin : CRC32 (zlib) of the pinned WINMINE.EXE, u32 LE
  artifacts/cc-ctx.bin   : per INT3 site, 4 bytes [off u16][ctx3 u8][ctx4 u8]
                           ctx = runtime bytes at site+3 / site+4 after the
                           patchbytes are applied; ctx4 is 0 (=don't check)
                           when site+4 lies inside another site's relocation
                           field (loader-written, not predictable).
Usage: gen_specdata.py <path-to-pinned-WINMINE.EXE>
"""
import sys, pathlib, struct, zlib, hashlib

ROOT = pathlib.Path("/Users/macsd/winmine-hack")
SEG1_FILE_OFF = 0x620

def main():
    spec = pathlib.Path(sys.argv[1]).read_bytes()
    assert len(spec) == 27776, len(spec)
    assert hashlib.sha256(spec).hexdigest() == \
        "633c1328922b4092351e0019b1ba1c6d56c0f0fea83824cc8b7e2e731b15e80b"
    crc = zlib.crc32(spec) & 0xFFFFFFFF
    (ROOT / "artifacts/spec-crc.bin").write_bytes(struct.pack("<I", crc))
    print("spec-crc.bin crc=%08X" % crc)

    pb = (ROOT / "artifacts/patchbytes.bin").read_bytes()
    seg = bytearray(spec[SEG1_FILE_OFF:SEG1_FILE_OFF + 0x2BD0])
    for i in range(0, len(pb), 4):
        fo, b = struct.unpack_from("<HB", pb, i)
        if SEG1_FILE_OFF <= fo < SEG1_FILE_OFF + len(seg):
            seg[fo - SEG1_FILE_OFF] = b
    ccb = (ROOT / "artifacts/cc-sites.bin").read_bytes()
    offs = [struct.unpack_from("<H", ccb, i)[0] for i in range(0, len(ccb), 2)]
    reloc_bytes = set()
    for o in offs:
        reloc_bytes.add(o + 1); reloc_bytes.add(o + 2)
    out = bytearray()
    for o in offs:
        ctx3 = seg[o + 3]
        ctx4 = 0 if (o + 4) in reloc_bytes else seg[o + 4]
        out += struct.pack("<HBB", o, ctx3, ctx4)
        print("site %04X ctx3=%02X ctx4=%02X" % (o, ctx3, ctx4))
    (ROOT / "artifacts/cc-ctx.bin").write_bytes(bytes(out))
    print("cc-ctx.bin", len(out), "bytes")

if __name__ == "__main__":
    main()
