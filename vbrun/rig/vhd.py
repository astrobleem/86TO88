import struct, sys
def footer(size, c, h, s, template):
    f = bytearray(template[-512:])
    struct.pack_into('>QQ', f, 40, size, size)
    struct.pack_into('>HBB', f, 56, c, h, s)
    f[64:68] = b'\0\0\0\0'
    f[64:68] = struct.pack('>I', (~sum(f)) & 0xFFFFFFFF)
    return bytes(f)
def to_vhd(raw_path, out_path, c, h, s, template_path=None):
    import os
    template_path = template_path or os.environ['VBW_VHD_TEMPLATE']   # MartyPC media/hdds/default_xtide.vhd
    raw = open(raw_path, 'rb').read()
    assert len(raw) == c*h*s*512
    t = open(template_path, 'rb').read()
    open(out_path, 'wb').write(raw + footer(len(raw), c, h, s, t))
if __name__ == '__main__':
    to_vhd(sys.argv[1], sys.argv[2], 615, 4, 17)
