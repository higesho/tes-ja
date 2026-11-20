# 絵の中の文字の塊を見つけて、番号付きの一覧の画像を作る
#   python imgtext.py 絵の名前... → orig/boxes/<名前>.png と orig/boxes/boxes.tsv
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import img

def text_colors(pal):
    """黄色・金色の濃淡（文字の色）"""
    out = set()
    for i in range(256):
        r, g, b = pal[i * 3:i * 3 + 3]
        if r >= 100 and g >= 80 and r - b >= 90 and g - b >= 70:
            out.add(i)
    return out

def boxes(w, h, px, tc, gapx=3, gapy=0):
    """文字の色の点をつないだ塊の囲み [(x0,y0,x1,y1, 点の数)]"""
    m = [[px[y * w + x] in tc for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if not m[y][x] or seen[y][x]:
                continue
            st = [(x, y)]; seen[y][x] = True
            x0 = x1 = x; y0 = y1 = y; n = 0
            while st:
                cx, cy = st.pop(); n += 1
                x0 = min(x0, cx); x1 = max(x1, cx); y0 = min(y0, cy); y1 = max(y1, cy)
                for dy in range(-1 - gapy, 2 + gapy):
                    for dx in range(-1 - gapx, 2 + gapx):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and m[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True; st.append((nx, ny))
            out.append((x0, y0, x1, y1, n))
    # 字らしい大きさのものだけ（高さ 4〜14、点が 6 以上）
    return [b for b in out if 4 <= b[3] - b[1] + 1 <= 14 and b[4] >= 6 and b[2] - b[0] + 1 >= 4]

def sheet(name, w, h, px, pal, bx, path, scale=3):
    from PIL import Image, ImageDraw
    im = Image.frombytes('P', (w, h), bytes(px))
    im.putpalette(pal)
    im = im.convert('RGB').resize((w * scale, h * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for i, (x0, y0, x1, y1, n) in enumerate(bx):
        d.rectangle([x0 * scale - 1, y0 * scale - 1, (x1 + 1) * scale, (y1 + 1) * scale], outline=(255, 0, 255))
        d.text((x0 * scale, max(0, y0 * scale - 10)), str(i), fill=(0, 255, 255))
    im.save(path)

if __name__ == '__main__':
    od = os.path.join(HERE, '..', 'orig', 'boxes')
    os.makedirs(od, exist_ok=True)
    base = img.palette()
    rows = []
    for nm in sys.argv[1:]:
        ims, pal = img.load(os.path.join(img.A2, nm))
        for k, (off, w, h, px) in enumerate(ims):
            p = pal or base
            bx = boxes(w, h, px, text_colors(p))
            sheet(nm, w, h, px, p, bx, os.path.join(od, '%s_%d.png' % (nm, k)))
            for i, b in enumerate(bx):
                rows.append('%s\t%d\t%d\t%d\t%d\t%d\t%d' % (nm, k, i, b[0], b[1], b[2], b[3]))
            print(nm, k, len(bx))
    open(os.path.join(od, 'boxes.tsv'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
