# Daggerfall の絵（IMG / CIF / 生の画素）を読む
#   IMG: [x i16][y i16][w i16][h i16][圧縮 u16][長さ u16] + 画素（圧縮 0 なら w*h）。頭の無いものは大きさで決まる
#   CIF: IMG の頭つきの絵がいくつも並ぶ（無圧縮のもの）
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
A2 = os.path.join(HERE, '..', '..', 'arena2')

RAW = {64000: (320, 200, 0), 64768: (320, 200, 768), 112128: (320, 200, 0), 720: (9, 80, 0), 990: (45, 22, 0),
       1720: (43, 40, 0), 2140: (107, 20, 0), 2916: (81, 36, 0), 3200: (40, 80, 0), 3938: (179, 22, 0),
       4280: (107, 40, 0), 4508: (322, 14, 0), 20480: (320, 64, 0), 26496: (184, 144, 0), 27876: (318, 87, 0),
       68800: (320, 215, 0)}

def palette(name='ART_PAL.COL'):
    b = open(os.path.join(A2, name), 'rb').read()
    p = b[8:8 + 768] if len(b) >= 776 else b[:768]
    return list(p)

def load(path):
    """[(位置(画素の先頭のファイル位置), w, h, 画素 bytes)] と、絵に付いた色（あれば）"""
    b = open(path, 'rb').read()
    out = []
    pal = None
    ext = path[-3:].upper()
    if ext == 'IMG':
        if len(b) >= 12:
            x, y, w, h, cm, dl = struct.unpack_from('<hhhhHH', b, 0)
            if cm == 0 and 0 < w <= 320 and 0 < h <= 200 and 12 + w * h <= len(b):
                out.append((12, w, h, b[12:12 + w * h]))
                return out, pal
        if len(b) in RAW:
            w, h, pl = RAW[len(b)]
            out.append((0, w, h, b[:w * h]))
            if pl: pal = list(b[w * h:w * h + 768])
        return out, pal
    if ext == 'RCI':
        fw, fh = {'BUTTONS.RCI': (32, 16)}.get(os.path.basename(path).upper(), (0, 0))
        if fw:
            for i in range(len(b) // (fw * fh)):
                out.append((i * fw * fh, fw, fh, b[i * fw * fh:(i + 1) * fw * fh]))
        return out, pal
    if ext == 'CIF':
        p = 0
        while p + 12 <= len(b):
            x, y, w, h, cm, dl = struct.unpack_from('<hhhhHH', b, p)
            if cm != 0 or not (0 < w <= 320 and 0 < h <= 200) or p + 12 + w * h > len(b):
                break
            out.append((p + 12, w, h, b[p + 12:p + 12 + w * h]))
            p += 12 + w * h
        return out, pal
    return out, pal

def to_png(w, h, px, pal, path, scale=1):
    from PIL import Image
    im = Image.frombytes('P', (w, h), bytes(px))
    p6 = max(pal) <= 63
    im.putpalette([v * 4 if p6 else v for v in pal])
    im = im.convert('RGB')
    if scale != 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)

if __name__ == '__main__':
    import glob
    outd = sys.argv[1]
    os.makedirs(outd, exist_ok=True)
    base = palette()
    n = 0
    for f in sorted(glob.glob(os.path.join(A2, '*.IMG')) + glob.glob(os.path.join(A2, '*.CIF'))):
        imgs, pal = load(f)
        for k, (off, w, h, px) in enumerate(imgs):
            to_png(w, h, px, pal or base, os.path.join(outd, '%s_%d.png' % (os.path.basename(f), k)))
            n += 1
    print(n, '枚')
