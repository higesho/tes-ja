# DOS 版の絵の訳（Daggerfall/jp_work/translation/imgtext.tsv）から、Daggerfall Unity の差し替え画像を作る
#   英語を消した元の絵を SCALE 倍に拡大し、日本語を TTF で細かく描く
#   IMG → out/StreamingAssets/Textures/Img/<名前>.png、CIF・RCI → Textures/CifRci/<名前>_<番号>-0.png
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
DFJP = os.path.join(HERE, '..', '..', '..', 'Daggerfall', 'jp_work', 'tools')
sys.path.insert(0, DFJP)
import img, imgpatch
from PIL import Image, ImageDraw, ImageFont
OUT = os.path.join(HERE, '..', 'out', 'StreamingAssets', 'Textures')
SCALE = 4
FONT = os.path.join(HERE, '..', 'fonts', 'BIZUDPGothic-Bold.ttf')

def rgb(pal, c):
    p6 = max(pal) <= 63
    r, g, b = pal[c * 3:c * 3 + 3]
    return (r * 4, g * 4, b * 4) if p6 else (r, g, b)

def main():
    boxes = imgpatch.load_boxes(); mp = imgpatch.load_map()
    os.makedirs(os.path.join(OUT, 'Img'), exist_ok=True); os.makedirs(os.path.join(OUT, 'CifRci'), exist_ok=True)
    f8 = ImageFont.truetype(FONT, 8 * SCALE)
    f14 = ImageFont.truetype(FONT, 14 * SCALE)
    n = 0
    for (name, k), groups in mp.items():
        imgpatch.TRACE = []
        c, s, hi = imgpatch.build_image(name, k, groups, boxes.get((name, k), {}))
        tr = imgpatch.TRACE; imgpatch.TRACE = None
        path = os.path.join(img.A2, name)
        raw = bytearray(open(path, 'rb').read()); orig = bytes(raw)
        for d, sr in c: raw[d] = orig[sr]                # 英語を消すだけ（8 ドットの字は置かない）
        tmp = os.path.join(HERE, '..', 'test', '_img', name)      # 読み手は名前で形を決めるので同じ名前にする
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        open(tmp, 'wb').write(raw)
        ims, pal = img.load(tmp)
        off, w, h, px = ims[k]
        if not pal:
            # DFU の ImgFile.PaletteName と同じ選び方
            u = name.upper()
            pn = 'FMAP_PAL.COL' if u.startswith('FMAP') else 'NIGHTSKY.COL' if u.startswith('NITE') else \
                 {'DANK02I0.IMG': 'DANKBMAP.COL', 'TMAP00I0.IMG': 'MAP.PAL'}.get(u, 'ART_PAL.COL')
            pal = img.palette(pn)
            for t in tr: t['pal'] = pal
        im = Image.frombytes('P', (w, h), bytes(px))
        im.putpalette([v * 4 for v in pal] if max(pal) <= 63 else pal)
        im = im.convert('RGBA').resize((w * SCALE, h * SCALE), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for t in tr:
            f = f14 if t['big'] else f8
            gh = 14 if t['big'] else 8
            x, y = t['x'] * SCALE, t['y'] * SCALE
            # 字の大きさの枠（gh × gh）の真ん中に置く
            bb = f.getbbox(t['ch'])
            cx = x + (gh * SCALE - (bb[2] - bb[0])) // 2 - bb[0]
            cy = y + (gh * SCALE - (bb[3] - bb[1])) // 2 - bb[1]
            if t['shadow'] is not None:
                offs = [(1, 1)] if not t['outline'] else [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
                for a, b in offs:
                    d.text((cx + a * SCALE // 2, cy + b * SCALE // 2), t['ch'], font=f, fill=rgb(t['pal'], t['shadow']))
            d.text((cx, cy), t['ch'], font=f, fill=rgb(t['pal'], t['color']))
        ext = name.split('.')[-1].upper()
        if ext == 'IMG':
            out = os.path.join(OUT, 'Img', name.upper() + '.png')
        else:
            out = os.path.join(OUT, 'CifRci', '%s_%d-0.png' % (name.upper(), k))
        im.save(out)
        n += 1
    print('絵', n)

if __name__ == '__main__':
    main()
