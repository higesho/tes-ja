# 絵の中の英語を日本語に替える指示（DLL の IMGP）を作る
#   translation/imgtext.tsv（訳）と orig/boxes/boxes.tsv（imgtext.py が見つけた文字の囲み）から
#   指示: 写す [行き先, 写し元]（英語の点を、近くの字でない点で埋める）／置く [行き先, 色]（日本語の字）
#   原作の画素そのものは入れない（写し元は位置で指す）
import os, sys, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import img, imgtext, jpdata, mkdata

JP = os.path.join(HERE, '..')
T = os.path.join(JP, 'translation')

_misaki = None
def misaki(ch):
    """美咲 8x8 の行（左詰め 8 ビット）"""
    global _misaki
    if _misaki is None:
        g, fbb = mkdata.load_bdf(os.path.join(mkdata.FONT, 'misaki_gothic_2nd.bdf'))
        _misaki = (g, fbb)
    g, fbb = _misaki
    e = g.get(ord(ch))
    if not e:
        return [0] * 8
    return mkdata.to_rows(e, fbb, 8, 8)

_big = None
def bigfont(ch):
    """東雲 14 ドット太字の行（左詰め 16 ビット）"""
    global _big
    if _big is None:
        _big = mkdata.load_bdf(os.path.join(mkdata.FONT, 'shnmk14b.bdf'))
    g, fbb = _big
    try:
        e = ch.encode('euc_jp')
        code = ((e[0] - 0x80) << 8) | (e[1] - 0x80)
    except Exception:
        return [0] * 14
    ent = g.get(code)
    return mkdata.to_rows(ent, fbb, 14, 16) if ent else [0] * 14

def load_boxes():
    d = collections.defaultdict(dict)
    for l in open(os.path.join(JP, 'orig', 'boxes', 'boxes.tsv'), encoding='utf-8'):
        f = l.rstrip('\n').split('\t')
        if len(f) < 7: continue
        d[(f[0], int(f[1]))][int(f[2])] = tuple(int(v) for v in f[3:7])
    return d

def load_map():
    """(絵, 番号) → [(日本語, [囲み番号...])]（= で前とまとめる）"""
    out = collections.OrderedDict()
    last = None
    for l in open(os.path.join(T, 'imgtext.tsv'), encoding='utf-8'):
        if l.startswith('#') or not l.strip(): continue
        f = l.rstrip('\n').split('\t')
        key = (f[0], int(f[1])); bi = tuple(int(v) for v in f[2].split(',')) if ',' in f[2] else int(f[2]); ja = f[3] if len(f) > 3 else '-'
        grp = out.setdefault(key, [])
        if ja == '=' and grp:
            grp[-1][1].append(bi)
        else:
            grp.append([ja, [bi]])
    return out

TRACE = None      # Daggerfall Unity 用の絵を作るときだけ [] にする

def build_image(name, k, groups, boxes):
    path = os.path.join(img.A2, name)
    ims, pal = img.load(path)
    base_off, w, h, px = ims[k]
    # 画面の上の位置: 頭つきの IMG は頭の x,y、320x200 の生の絵は 0,0。ほか（CIF・RCI）は分からないので細かい字なし
    scr = None
    if name.upper().endswith('.IMG'):
        if base_off == 12:
            sx, sy = struct.unpack_from('<hh', open(path, 'rb').read(), 0)
            if 0 <= sx < 320 and 0 <= sy < 200: scr = (sx, sy)
        elif w == 320 and h == 200:
            scr = (0, 0)
    pal = pal or img.palette()
    tc = imgtext.text_colors(pal)
    px = bytearray(px)
    copies, sets, his = [], {}, []
    for ja, bis in groups:
        rs = [b if isinstance(b, tuple) else boxes[b] for b in bis if isinstance(b, tuple) or b in boxes]
        if not rs: continue
        # 頭の記号: < 左寄せ、> 右寄せ、~ 模様を敷き詰める（既定は平塗り）、^ 明るい字、! 暗い字、| 改行
        flags = set()
        while ja and ja[0] in '<>#~^!@%*':
            flags.add(ja[0]); ja = ja[1:]
        x0 = min(r[0] for r in rs); y0 = min(r[1] for r in rs); x1 = max(r[2] for r in rs); y1 = max(r[3] for r in rs)
        # 英語の点と影
        T_ = set((x, y) for y in range(max(0, y0 - 1), min(h, y1 + 2)) for x in range(max(0, x0 - 1), min(w, x1 + 2)) if px[y * w + x] in tc)
        if flags & set('^!'):
            T_ = set()
        cand = collections.Counter()
        for (x, y) in T_:
            for dx, dy in ((1, 1), (1, 0), (0, 1)):
                q = (x + dx, y + dy)
                if q not in T_ and q[0] < w and q[1] < h:
                    cand[px[q[1] * w + q[0]]] += 1
        shadow = None
        if cand:
            c, n = cand.most_common(1)[0]
            r, g, b = pal[c * 3:c * 3 + 3]
            if r + g + b < 200: shadow = c
        # 影: 字の点の右・下 2 画素以内で、囲みの周りの下地よりかなり暗い点
        def lum(i): return pal[i * 3] * 3 + pal[i * 3 + 1] * 6 + pal[i * 3 + 2]
        ring = [lum(px[y * w + x]) for y in range(max(0, y0 - 3), min(h, y1 + 4)) for x in range(max(0, x0 - 4), min(w, x1 + 5))
                if not (x0 - 1 <= x <= x1 + 2 and y0 - 1 <= y <= y1 + 2) and px[y * w + x] not in tc]
        if len(ring) < 20 or flags & set('^!'):      # 周りが狭い（小さいボタンの絵）・地の中の文章は、囲みの中の明るさの真ん中を下地とする
            ring = [lum(px[y * w + x]) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
        ring.sort()
        bgl = ring[len(ring) // 2] if ring else 0
        gray = not T_
        if '!' in flags:
            # 暗い字: 下地より暗い点を字とする。影なし
            T_ = set((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if lum(px[y * w + x]) < bgl * 0.75)
            shadow = None
        elif not T_:
            # 黄色い字が無い（灰色の彫り込みの字）か ^ の明るい字: 下地より明るい点を字、暗い点を影とする
            T_ = set((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if lum(px[y * w + x]) > bgl * 1.2)
            dk = collections.Counter(px[y * w + x] for y in range(y0, y1 + 2) for x in range(x0, x1 + 2)
                                     if x < w and y < h and lum(px[y * w + x]) < bgl * 0.8)
            shadow = dk.most_common(1)[0][0] if dk else None
        S = set()
        for (x, y) in T_:
            for dx in range(-1, 3):
                for dy in range(-1, 3):
                    q = (x + dx, y + dy)
                    if q in T_ or not (0 <= q[0] < w and 0 <= q[1] < h): continue
                    ci = px[q[1] * w + q[0]]
                    lq = lum(ci)
                    yellowish = pal[ci * 3] - pal[ci * 3 + 2] > 35 and pal[ci * 3 + 1] - pal[ci * 3 + 2] > 25
                    # 字の周り（左上 1・右下 2）は、影や縁取りの色が下地と見分けにくいので、明るさに関係なく消す
                    if True or lq < bgl * (0.85 if dx >= 0 and dy >= 0 else 0.6) or ((lq > bgl * 1.5 or yellowish) and abs(dx) <= 1 and abs(dy) <= 1):
                        S.add(q)
        # 字の囲みの中で、下地の明るさから外れる点（字の縁の色）も消す
        for yy in range(y0, y1 + 1):
            for xx in range(max(0, x0 - 1), min(w, x1 + 2)):
                lq = lum(px[yy * w + xx])
                if lq < bgl * 0.75 or lq > bgl * 1.3:
                    S.add((xx, yy))
        E = T_ | S
        if '%' in flags:
            # 囲みを丸ごと消し、すぐ上と下の行（字の無い下地）を写して埋める
            E = set((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
        def okp(xx, yy):
            l2 = lum(px[yy * w + xx])
            return (xx, yy) not in E and (px[yy * w + xx] not in tc or flags & set('^!')) and bgl * 0.6 <= l2 <= bgl * 1.5
        ex0 = min(x for x, y in E) if E else x0; ex1 = max(x for x, y in E) if E else x1
        span = ex1 - ex0 + 2
        def reach(x, y, xx):
            """x から xx までの間に、ボタンの縁（字でも下地でもない点）を挟まないか"""
            st = 1 if xx > x else -1
            for q in range(x + st, xx, st):
                if (q, y) not in E and not okp(q, y):
                    return False
            return True
        shifts = []
        for s in (span, span // 2, span // 3, span * 2 // 3, 6, 4):
            if s > 0: shifts += [s, -s]
        fill = {}
        if '%' in flags:
            mid = (y0 + y1) // 2
            for (x, y) in E:
                sy = y0 - 2 - (y - y0) % 3
                if 0 <= sy < h: fill[(x, y)] = (x, sy)
        # 既定は平らに塗る（模様を敷き詰めると縁や印が写り込みやすい）。~ を付けたものだけ模様を敷き詰める
        flat = '~' not in flags and '%' not in flags
        if flags & set('^!') and '~' not in flags and '%' not in flags:
            # 地の中の文章: 囲みの中で、字でも影でもない点のうち下地の明るさに近い、いちばん多い色で塗る
            inner = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if (x, y) not in E]
            cc = collections.Counter(px[y * w + x] for x, y in inner if abs(lum(px[y * w + x]) - bgl) <= bgl * 0.15)
            if cc:
                best = cc.most_common(1)[0][0]
                sp = next(p for p in inner if px[p[1] * w + p[0]] == best)
                for p in E: fill[p] = sp
            flat = False
        if flat:
            # 平らに塗る: 行ごとに、英語の左右の下地のうちいちばん多い色（その色の点を写し元にする）
            rows_e = collections.defaultdict(list)
            for (x, y) in E: rows_e[y].append(x)
            for y, xs in rows_e.items():
                a, b = min(xs), max(xs)
                cand = [xx for xx in list(range(a - 1, max(-1, a - 12), -1)) + list(range(b + 1, min(w, b + 12))) if okp(xx, y)]
                if not cand: continue
                cc = collections.Counter(px[y * w + xx] for xx in cand)
                best = min(cc, key=lambda ci: (abs(lum(ci) - bgl), -cc[ci]))
                srcx = next(xx for xx in cand if px[y * w + xx] == best)
                for x in xs: fill[(x, y)] = (srcx, y)
        # 行ごとに、英語の左右で縁に当たるまでの下地の点を集め、それを並べて敷き詰める
        rows_e = collections.defaultdict(list)
        for (x, y) in E: rows_e[y].append(x)
        for y, xs in rows_e.items():
            a, b = min(xs), max(xs)
            pool_l, pool_r = [], []
            xx = a - 1
            while xx >= 0 and len(pool_l) < 24:
                if (xx, y) in E: xx -= 1; continue
                if not okp(xx, y): break
                pool_l.append(xx); xx -= 1
            xx = b + 1
            while xx < w and len(pool_r) < 24:
                if (xx, y) in E: xx += 1; continue
                if not okp(xx, y): break
                pool_r.append(xx); xx += 1
            pool = pool_l[::-1] + pool_r
            if len(pool) < 3 or flat or "%" in flags or (flags & set("^!") and "~" not in flags): continue
            for x in xs:
                fill[(x, y)] = (pool[(x - a) % len(pool)], y)
        # 残りは、埋まった隣の写し元を引き継ぐ（上下左右）。全部埋まるまで繰り返す
        for _ in range(64):
            changed = False
            for (x, y) in E:
                if (x, y) in fill: continue
                for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if q in fill:
                        fill[(x, y)] = fill[q]; changed = True; break
                    if 0 <= q[0] < w and 0 <= q[1] < h and okp(*q):
                        fill[(x, y)] = q; changed = True; break
            if not changed: break
        for (x, y), src in fill.items():
            copies.append((base_off + y * w + x, base_off + src[1] * w + src[0]))
        if ja == '-' or not ja:
            continue
        # 日本語を置く
        left = '<' in flags; right = '>' in flags
        cnt = collections.Counter(px[y * w + x] for (x, y) in T_)
        if '!' in flags and cnt:
            top = [ci for ci, n in cnt.most_common(4) if n >= 3] or [cnt.most_common(1)[0][0]]
            color = min(top, key=lum)
        elif gray and cnt:
            # 灰色の字: よく使われている色のうち、いちばん明るいもの
            top = [ci for ci, n in cnt.most_common(4) if n >= 3] or [cnt.most_common(1)[0][0]]
            color = max(top, key=lum)
        else:
            color = cnt.most_common(1)[0][0] if cnt else 146
        lines = ja.split('|')
        big = '@' in flags
        gw, gh = (15, 14) if big else (8, 8)      # 1 字の送りと高さ
        lh = gh + 2
        top_y = (y0 + y1 + 1) // 2 - (lh * len(lines) - 2) // 2
        for li, line in enumerate(lines):
            cw = gw * len(line) - 1
            gx = x0 if left else (x1 - cw + 1) if right else (x0 + x1 + 1) // 2 - cw // 2
            gy = top_y + li * lh if len(lines) > 1 else (y0 + y1 + 1) // 2 - gh // 2
            for i, ch in enumerate(line):
                rows = bigfont(ch) if big else [r << 8 for r in misaki(ch)]
                ox = gx + i * gw
                if TRACE is not None:
                    # Daggerfall Unity 用（高解像度の絵に字を描き直すため）: 字の位置・色など
                    TRACE.append(dict(name=name, k=k, x=ox, y=gy, ch=ch, color=color, shadow=shadow, big=big,
                                      outline='*' in flags, pal=pal))
                offs = [(1, 1)] if '*' not in flags else [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
                for col, ddx, ddy in [(shadow, a, b) for a, b in offs] + [(color, 0, 0)]:
                    if col is None: continue
                    for yy in range(len(rows)):
                        for xx in range(16):
                            if rows[yy] & (0x8000 >> xx):
                                X, Y = ox + xx + ddx, gy + yy + ddy
                                if 0 <= X < w and 0 <= Y < h:
                                    sets[base_off + Y * w + X] = col
                if scr is not None and not big:
                    for col, dx in ((shadow, 1), (color, 0)):
                        if col is None: continue
                        b = jpdata.to_game(ch)
                        if len(b) == 2 and 0 <= scr[0] + ox + dx <= 312 and 0 <= scr[1] + gy + dx < 200:
                            # 末尾: 絵の中の字の左上の位置（ファイル上）と幅・高さ（出来上がった絵で、字の色が残る点を後で調べる）
                            his.append((scr[0] + ox + dx, scr[1] + gy + dx, b[0], b[1], col, base_off, w, h, ox + dx, gy + dx))
    return copies, sets, his

def build():
    boxes = load_boxes()
    mp = load_map()
    per_file = collections.OrderedDict()
    for (name, k), groups in mp.items():
        c, s, hi = build_image(name, k, groups, boxes.get((name, k), {}))
        pf = per_file.setdefault(name, [[], {}, []])
        pf[0] += c; pf[1].update(s); pf[2] += hi
    out = bytearray()
    for name, (c, s, hi) in per_file.items():
        body = bytearray(struct.pack('<III', len(c), len(s), len(hi)))
        for d, sr in c: body += struct.pack('<II', d, sr)
        for d, v in sorted(s.items()): body += struct.pack('<I', d | (v << 24))
        for x, y, a, b, col, *_ in hi: body += struct.pack('<HHBBBB', x, y, a, b, col, 0)
        # 字ごとの 8x8 の印: 出来上がった絵で、その位置の点が字の色のままなら 1（影の重なりなどで色が変わる点は見ない）
        raw = bytearray(open(os.path.join(img.A2, name), 'rb').read())
        fin = bytearray(raw)
        for d, sr in c:
            if d < len(fin) and sr < len(raw): fin[d] = raw[sr]
        for d, v in s.items():
            if d < len(fin): fin[d] = v
        for x, y, a, b, col, bo, w, h, ix, iy in hi:
            m = bytearray(8)
            for r in range(8):
                for cc in range(8):
                    X, Y = ix + cc, iy + r
                    if 0 <= X < w and 0 <= Y < h and fin[bo + Y * w + X] == col: m[r] |= 0x80 >> cc
            body += bytes(m)
        out += ('ARENA2\\' + name.upper()).encode().ljust(32, b'\0') + struct.pack('<I', len(body)) + body
        while len(out) % 4: out += b'\0'
    print('絵', len(per_file), '指示', len(out))
    return bytes(out)

def preview(name, k=0, scale=3):
    """確認用: 指示を当てた絵を orig/boxes/<名前>_ja.png に書く"""
    boxes = load_boxes(); mp = load_map()
    c, s, hi = build_image(name, k, mp[(name, k)], boxes[(name, k)])
    path = os.path.join(img.A2, name)
    raw = bytearray(open(path, 'rb').read())
    orig = bytes(raw)
    for d, sr in c: raw[d] = orig[sr]
    for d, v in s.items(): raw[d] = v
    open(os.path.join(JP, 'orig', 'boxes', '_tmp.img'), 'wb').write(raw)
    ims, pal = img.load(os.path.join(JP, 'orig', 'boxes', '_tmp.img'))
    off, w, h, px = ims[k]
    img.to_png(w, h, px, pal or img.palette(), os.path.join(JP, 'orig', 'boxes', '%s_ja.png' % name), scale)

if __name__ == '__main__':
    for n in sys.argv[1:]:
        preview(n)
