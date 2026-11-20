# Arena の IMG / CIF を読む（OpenTESArena の IMGFile・Compression を写したもの）
#   python img.py dump 出力フォルダ   … BSA と遊びのフォルダの IMG・CIF・MNU を全部 PNG にする
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RAW = {'ARENARW.IMG': (16, 16), 'CITY.IMG': (16, 11), 'DITHER.IMG': (8, 100), 'DITHER2.IMG': (8, 100),
       'DUNGEON.IMG': (14, 8), 'DZTTAV.IMG': (32, 34), 'NOCAMP.IMG': (25, 19), 'NOSPELL.IMG': (25, 19),
       'P1.IMG': (320, 53), 'POPTALK.IMG': (320, 77), 'S2.IMG': (320, 36), 'SLIDER.IMG': (289, 7),
       'TOWN.IMG': (9, 10), 'UPDOWN.IMG': (8, 16), 'VILLAGE.IMG': (8, 8)}

def type04(src, n):
    out = bytearray(); hist = bytearray(b'\x20' * 4096); hp = 0
    i = 0; bitcount = 0; mask = 0
    while i < len(src) and len(out) < n:
        if not bitcount:
            bitcount = 8; mask = src[i]; i += 1
        else:
            mask >>= 1
        if mask & 1:
            if i >= len(src): break
            hist[hp & 0xFFF] = src[i]; hp += 1; out.append(src[i]); i += 1
        else:
            if i + 1 >= len(src): break
            b1, b2 = src[i], src[i + 1]; i += 2
            cnt = (b2 & 0x0F) + 3; cp = (((b2 & 0xF0) << 4) | b1) + 18
            for _ in range(cnt):
                v = hist[cp & 0xFFF]; cp += 1
                hist[hp & 0xFFF] = v; hp += 1; out.append(v)
        bitcount -= 1
    out += bytes(max(0, n - len(out)))
    return bytes(out[:n])

HIGH = []
for v, c in [(0, 32), (1, 16), (2, 16), (3, 16)]: HIGH += [v] * c
for v in range(4, 12): HIGH += [v] * 8
for v in range(12, 24): HIGH += [v] * 4
for v in range(24, 48): HIGH += [v] * 2
HIGH += list(range(48, 64))
LOWC = [3] * 32 + [4] * 48 + [5] * 64 + [6] * 48 + [7] * 48 + [8] * 16

def type08(src, n):
    hist = bytearray(b'\x20' * 4096); hp = 0
    idxmap = [(v >> 1) + 314 for v in range(626)] + [0] + list(range(941 - 627))
    tree = list(range(627, 627 + 314)) + [v * 2 for v in range(313)]
    freq = [1] * 314 + [0] * 313
    k = 0
    for j in range(314, 627):
        freq[j] = freq[k] + freq[k + 1]; k += 2
    bm = 0; vb = 0; i = 0
    out = bytearray()
    def fill():
        nonlocal bm, vb, i
        while vb < 9:
            if i < len(src):
                bm |= src[i] << (8 - vb); i += 1
            vb += 8
        bm &= 0xFFFF
    while len(out) < n:
        node = tree[626]
        while node < 627:
            fill()
            node = tree[node + ((bm >> 15) & 1)]
            bm = (bm << 1) & 0xFFFF; vb -= 1
        fi = idxmap[node]
        while True:
            freq[fi] += 1
            f = freq[fi]; ni = fi + 1
            if ni < 627 and freq[ni] < f:
                while ni < 627 and freq[ni] < f: ni += 1
                ni -= 1
                freq[fi] = freq[ni]; freq[ni] = f
                tree[fi], tree[ni] = tree[ni], tree[fi]
                m = tree[ni]; idxmap[m] = ni
                if m < 627: idxmap[m + 1] = ni
                m = tree[fi]; idxmap[m] = fi
                if m < 627: idxmap[m + 1] = fi
                fi = ni
            fi = idxmap[fi]
            if fi == 0: break
        cw = node - 627
        if cw < 256:
            hist[hp & 0xFFF] = cw; hp += 1; out.append(cw)
        else:
            fill()
            ti = bm >> 8; bm = (bm << 8) & 0xFFFF; vb -= 8
            oh = HIGH[ti] << 6; bc = LOWC[ti] - 2; ol = ti
            for _ in range(bc):
                fill()
                ol = (ol << 1) | ((bm >> 15) & 1); bm = (bm << 1) & 0xFFFF; vb -= 1
            cp = (hp - (oh | (ol & 0x3F)) - 1) & 0xFFFF
            for _ in range(cw - 256 + 3):
                v = hist[cp & 0xFFF]; cp += 1
                hist[hp & 0xFFF] = v; hp += 1; out.append(v)
    return bytes(out[:n])

def decode_img(name, d):
    """(幅, 高さ, 画素, パレットか None, 頭の 12 バイトか None)"""
    if name.upper() in RAW:
        w, h = RAW[name.upper()]; return w, h, d[:w * h], None, None
    if len(d) == 4096: return 64, 64, d, None, None
    x, y, w, h, flags, ln = struct.unpack_from('<6H', d, 0)
    body = d[12:12 + ln]
    t = flags & 0xFF
    if t == 0: pix = d[12:12 + w * h]
    elif t == 4: pix = type04(body, w * h)
    elif t == 8: pix = type08(d[14:12 + ln], w * h)
    else: return None
    pal = d[12 + ln:12 + ln + 768] if flags & 0x100 else None
    return w, h, pix, pal, d[:12]

def default_pal():
    from textutil import read_game
    p = read_game('PAL.COL')[8:8 + 768]
    return p

def to_png(w, h, pix, pal, path, scale=63):
    from PIL import Image
    im = Image.frombytes('P', (w, h), bytes(pix))
    pl = bytes(min(255, c * 255 // 63) for c in pal) if scale == 63 else pal
    im.putpalette(pl)
    im.convert('RGB').save(path)

if __name__ == '__main__':
    import bsa
    from textutil import GAME
    if sys.argv[1] == 'dump':
        od = sys.argv[2]; os.makedirs(od, exist_ok=True)
        pal = default_pal()
        d, ents = bsa.read()
        items = [(e[0], d[e[1]:e[1] + e[2]]) for e in ents if e[0].upper().endswith(('.IMG', '.MNU'))]
        for fn in os.listdir(GAME):
            if fn.upper().endswith(('.IMG', '.MNU')):
                items.append(('_' + fn, open(os.path.join(GAME, fn), 'rb').read()))
        ok = ng = 0
        for name, b in items:
            try:
                r = decode_img(name.lstrip('_'), b)
                if not r: ng += 1; continue
                w, h, pix, p, _ = r
                if w * h == 0 or w > 1000 or h > 1000: ng += 1; continue
                to_png(w, h, pix, p or pal, os.path.join(od, name + '.png'))
                ok += 1
            except Exception as ex:
                ng += 1; print('NG', name, ex)
        print(ok, 'ok', ng, 'ng')
