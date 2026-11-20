# 絵の日本語化: tools/pics_spec.py の指定どおり原作の絵の文字を消して日本語を描き、
# 変えた四角い部分だけを test/arenajp/pics.bin に書く。見本は test/pics/*.png
#   python make_pics.py [絵の名前 ...]（省略で全部）
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import WORK, GAME, read_game
import img, bsa, picfont
from PIL import Image
import importlib

OUTD = os.path.join(WORK, 'test', 'pics')
_bsa = None
def original(name, loose=False):
    global _bsa
    if loose:
        b = read_game(name)
    else:
        if _bsa is None:
            d, ents = bsa.read(); _bsa = {e[0]: d[e[1]:e[1] + e[2]] for e in ents}
        b = _bsa[name]
    w, h, pix, pal, head = img.decode_img(name, b)
    return w, h, bytearray(pix), pal

def palette(spec, embedded):
    p = spec.get('pal', 'embedded')
    if p == 'embedded' and embedded: raw = embedded
    elif p == 'scroll': return open(os.path.join(WORK, 'orig', 'pal_SCROLL.bin'), 'rb').read()
    elif p.endswith('.COL'): raw = read_game(p)[8:8 + 768]
    else: raw = read_game('PAL.COL')[8:8 + 768]
    return bytes(min(255, c * 255 // 63) for c in raw)

def lum(pal, c):
    r, g, b = pal[c * 3:c * 3 + 3]
    return (r * 3 + g * 6 + b) / 10

class Pic:
    def __init__(self, w, h, pix, pal):
        self.w, self.h, self.p, self.pal = w, h, pix, pal
        self.inkcol = None
    def get(self, x, y): return self.p[y * self.w + x]
    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h: self.p[y * self.w + x] = c

    def ink(self, x, y, w, h, mode='dark', thr=90):
        """文字の点を見つけて、まわりの地の色で埋める"""
        if mode == 'dark': isink = lambda c: lum(self.pal, c) < thr
        elif mode == 'light': isink = lambda c: lum(self.pal, c) > thr
        elif mode == 'red':
            def isink(c, pal=self.pal):
                r, g, b = pal[c * 3:c * 3 + 3]; return r > 90 and r > 1.8 * g and r > 1.8 * b
        elif mode == 'yd':
            def isink(c, pal=self.pal):
                r, g, b = pal[c * 3:c * 3 + 3]
                return (r > 140 and g > 120 and b < 0.7 * g) or (r * 3 + g * 6 + b) / 10 < thr
        elif mode == 'yellow':
            def isink(c, pal=self.pal):
                r, g, b = pal[c * 3:c * 3 + 3]; return r > 140 and g > 120 and b < 0.7 * g
        else: isink = lambda c, s=set(thr): c in s
        mask = set()
        from collections import Counter
        cnt = Counter()
        for yy in range(y, min(y + h, self.h)):
            for xx in range(x, min(x + w, self.w)):
                c = self.get(xx, yy)
                if isink(c): mask.add((xx, yy)); cnt[c] += 1
        if cnt and self.inkcol is None:
            # 文字の色: いちばん暗い（明るい）よく使われた色
            cs = [c for c, n in cnt.most_common(6)]
            if mode in ('red', 'yellow', 'colors', 'yd'): self.inkcol = cnt.most_common(1)[0][0]
            else: self.inkcol = min(cs, key=lambda c: lum(self.pal, c)) if mode != 'light' else max(cs, key=lambda c: lum(self.pal, c))
        while mask:
            done = []
            for (xx, yy) in mask:
                nb = []
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                    q = (xx + dx, yy + dy)
                    if q in mask: continue
                    if 0 <= q[0] < self.w and 0 <= q[1] < self.h: nb.append(self.get(*q))
                if nb:
                    done.append(((xx, yy), Counter(nb).most_common(1)[0][0]))
            if not done: break
            for q, c in done:
                self.put(q[0], q[1], c); mask.discard(q)

    def auto(self, x, y, w, h, bx, by):
        """(bx,by) から同じ大きさの文字のない所と色の数を比べ、文字の所にだけ多い色をインクとして消す"""
        from collections import Counter
        a = Counter(self.get(x + i, y + j) for j in range(h) for i in range(w) if x + i < self.w and y + j < self.h)
        b = Counter(self.get(bx + i, by + j) for j in range(h) for i in range(w) if bx + i < self.w and by + j < self.h)
        ink = [c for c, n in a.items() if n > 2 * b.get(c, 0) + 2]
        if ink and self.inkcol is None:
            self.inkcol = max(ink, key=lambda c: a[c] - b.get(c, 0))
        self.ink(x, y, w, h, 'colors', ink)

    def label(self, x, y, w, h):
        """暗い字と左の明るい縁取りの 2 色で書かれたラベルを消す"""
        from collections import Counter
        cnt = Counter(self.get(x + i, y + j) for j in range(h) for i in range(w) if x + i < self.w and y + j < self.h)
        top = [c for c, n in cnt.most_common(4)]
        d = min(top, key=lambda c: lum(self.pal, c))
        left = Counter(self.get(x + i - 1, y + j) for j in range(h) for i in range(w)
                       if 0 < x + i < self.w and y + j < self.h and self.get(x + i, y + j) == d and self.get(x + i - 1, y + j) != d)
        l = left.most_common(1)[0][0]
        if self.inkcol is None: self.inkcol = d
        # 字のすぐ隣の、地より暗い点（影のにじみ）も消す
        ring = [self.get(i, j) for j in range(y - 5, y + h + 5) for i in range(x - 5, x + w + 5)
                if 0 <= i < self.w and 0 <= j < self.h and not (x - 1 <= i < x + w + 1 and y - 1 <= j < y + h + 1)]
        base = sorted(lum(self.pal, c) for c in ring)[len(ring) // 2] if ring else 128
        core = {(i, j) for j in range(y - 1, y + h + 1) for i in range(x - 2, x + w + 2)
                if 0 <= i < self.w and 0 <= j < self.h and self.get(i, j) in (d, l)}
        halo = set()
        for (i, j) in core:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (i + dx, j + dy)
                    if q not in core and 0 <= q[0] < self.w and 0 <= q[1] < self.h and lum(self.pal, self.get(*q)) < base - 20:
                        halo.add(q)
        self.fill(core | halo)

    def fill(self, mask):
        from collections import Counter
        mask = set(mask)
        while mask:
            done = []
            for (xx, yy) in mask:
                nb = [self.get(xx + dx, yy + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1))
                      if (xx + dx, yy + dy) not in mask and 0 <= xx + dx < self.w and 0 <= yy + dy < self.h]
                if nb: done.append(((xx, yy), Counter(nb).most_common(1)[0][0]))
            if not done: break
            for q, c in done:
                self.put(q[0], q[1], c); mask.discard(q)

    def clone(self, x, y, w, h, sx, sy):
        src = [[self.get(sx + i % max(1, w), sy + j) for i in range(w)] for j in range(h)]
        for j in range(h):
            for i in range(w): self.put(x + i, y + j, src[j][i])

    def rect(self, x, y, w, h, c):
        for j in range(h):
            for i in range(w): self.put(x + i, y + j, c)

    def text(self, x, y, w, s, fname='12', color=None, align='l', lh=None, shadow=None, outline=None, bold=False, nowrap=False):
        f = picfont.font(fname)
        col = self.inkcol if color in (None, 'ink') else color
        lines = picfont.wrap(f, s, w) if w and not nowrap else s.split('\n')
        lh = lh or f.h + 2
        for n, line in enumerate(lines):
            lw = f.width(line)
            cx = x + (w - lw) // 2 if align == 'c' else (x + w - lw if align == 'r' else x)
            cy = y + n * lh
            pts = []
            for ch in line:
                g, adv = f.glyph(ch)
                pts += [(cx + px, cy + py) for px, py in g]
                if bold: pts += [(cx + px + 1, cy + py) for px, py in g]
                cx += adv
            if outline is not None:
                ps = set(pts)
                for px, py in pts:
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                        if (px + dx, py + dy) not in ps: self.put(px + dx, py + dy, outline)
            if shadow:
                sc, sdx, sdy = shadow
                for px, py in pts: self.put(px + sdx, py + sdy, sc)
            for px, py in pts: self.put(px, py, col)
        return len(lines)

def run(name, spec):
    loose = name.startswith('_')
    w, h, pix, emb = original(name[1:] if loose else name, loose)
    pal = palette(spec, emb)
    P = Pic(w, h, bytearray(pix), pal)
    orig = bytes(pix)
    rects = []
    for op in spec['ops']:
        kind, a = op[0], op[1:]
        if kind == 'ink': P.ink(*a); rects.append(a[:4])
        elif kind == 'auto': P.auto(*a)
        elif kind == 'label': P.label(*a); rects.append(a[:4])
        elif kind == 'inkcol': P.inkcol = a[0]
        elif kind == 'clone': P.clone(*a); rects.append(a[:4])
        elif kind == 'rect': P.rect(*a); rects.append(a[:4])
        elif kind == 'copyfrom':
            # ('copyfrom', ほかの絵, x, y, w, h, 元x, 元y)
            on, x, y, cw, chh, sx, sy = a
            ow, oh, op, _ = original(on)
            for j in range(chh):
                for i in range(cw): P.put(x + i, y + j, op[(sy + j) * ow + sx + i])
        elif kind == 'text':
            kw = a[-1] if isinstance(a[-1], dict) else {}
            args = a[:-1] if kw else a
            P.text(*args, **kw)
    # 変わった所の外接四角（文字は消した範囲の外にはみ出すことがある）
    ch = [(i % w, i // w) for i in range(w * h) if P.p[i] != orig[i]]
    out = []
    if ch:
        # 行ごとに分けて小さくまとめる
        rows = {}
        for x, y in ch: rows.setdefault(y, []).append(x)
        y0 = None
        cur = None
        for y in range(h + 1):
            xs = rows.get(y)
            if xs and cur is None: cur = [y, y, min(xs), max(xs)]
            elif xs: cur[1] = y; cur[2] = min(cur[2], min(xs)); cur[3] = max(cur[3], max(xs))
            if (not xs or y == h) and cur is not None:
                out.append((cur[2], cur[0], cur[3] - cur[2] + 1, cur[1] - cur[0] + 1)); cur = None
    os.makedirs(OUTD, exist_ok=True)
    im = Image.frombytes('P', (w, h), bytes(P.p)); im.putpalette(pal)
    im.convert('RGB').resize((w * 2, h * 2), Image.NEAREST).save(os.path.join(OUTD, name + '.png'))
    data = []
    for x, y, rw, rh in out:
        # 原作の画素を持たないよう、元の絵との XOR にする
        px = bytes(P.p[(y + j) * w + x + i] ^ orig[(y + j) * w + x + i] for j in range(rh) for i in range(rw))
        data.append((x, y, rw, rh, px))
    return data

if __name__ == '__main__':
    import pics_spec
    importlib.reload(pics_spec)
    names = sys.argv[1:] or list(pics_spec.SPEC)
    allp = {}
    pb = os.path.join(WORK, 'test', 'arenajp', 'pics.bin')
    for n in pics_spec.SPEC:
        if n in names:
            allp[n] = run(n, pics_spec.SPEC[n]); print(n, len(allp[n]), '個の四角')
    # 名前を指定したときは、ほかの絵は前回の pics.bin のものを残すため全部作り直す
    if sys.argv[1:]:
        for n in pics_spec.SPEC:
            if n not in allp: allp[n] = run(n, pics_spec.SPEC[n])
    out = bytearray(b'ARJX')
    items = [(n, r) for n in allp for r in allp[n]]
    out += struct.pack('<I', len(items))
    for n, (x, y, w, h, px) in items:
        out += n.encode('ascii').ljust(13, bytes(1)) + struct.pack('<4H', x, y, w, h) + px
    open(pb, 'wb').write(out)
    print('pics.bin', len(items), '個', len(out), 'バイト')
