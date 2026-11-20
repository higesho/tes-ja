# FORM*.IMG の文字（255 と影 229）のかたまりを拾う。枠（高さ 11 以上）は除く
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_pics
def words(name, gap=4):
    w, h, p, emb = make_pics.original(name)
    pts = {(x, y) for y in range(h) for x in range(w) if p[y * w + x] in (255, 229)}
    # まず 8 近傍でつながる部分に分け、高さ 11 以上（枠）を外す
    seen = set(); comps = []
    for s in pts:
        if s in seen: continue
        st = [s]; seen.add(s); c = []
        while st:
            x, y = st.pop(); c.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pts and q not in seen: seen.add(q); st.append(q)
        ys = [q[1] for q in c]; xs = [q[0] for q in c]
        if max(ys) - min(ys) >= 11 or max(xs) - min(xs) >= 130: continue
        comps.append((min(xs), min(ys), max(xs), max(ys)))
    # 横に近いものをまとめて語にする
    comps.sort()
    out = []
    for c in comps:
        for o in out:
            if c[0] - o[2] <= gap and o[0] - c[2] <= gap and not (c[1] > o[3] + 2 or o[1] > c[3] + 2):
                o[0] = min(o[0], c[0]); o[1] = min(o[1], c[1]); o[2] = max(o[2], c[2]); o[3] = max(o[3], c[3]); break
        else: out.append(list(c))
    return w, h, [(a, b, c - a + 1, d - b + 1) for a, b, c, d in sorted(out, key=lambda o: (o[1] // 4, o[0]))]
if __name__ == '__main__':
    from PIL import Image, ImageDraw
    import bsa
    d, ents = bsa.read()
    ns = sorted([e[0] for e in ents if e[0].startswith('FORM')], key=lambda n: (len(n), n))
    for n in ns:
        w, h, ws = words(n)
        print(n, ws)
        W, H, p, emb = make_pics.original(n)
        im = Image.frombytes('P', (w, h), bytes(p)); im.putpalette(make_pics.palette({'pal': 'DAYTIME.COL'}, emb))
        im = im.convert('RGB').resize((w * 4, h * 4), Image.NEAREST); dr = ImageDraw.Draw(im)
        for i, (x, y, ww, hh) in enumerate(ws):
            dr.rectangle((x * 4 - 2, y * 4 - 2, (x + ww) * 4 + 1, (y + hh) * 4 + 1), outline=(0, 255, 0))
            dr.text((x * 4, y * 4 - 12), str(i), fill=(0, 0, 0))
        im.save(os.path.join(make_pics.WORK, 'test', 'f_' + n + '.png'))
