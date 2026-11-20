# 絵に描く日本語の字体（東雲・美咲の BDF）
import os
HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, '..', 'font')

def load_bdf(path):
    """{文字コード: (幅, 高さ, x 補正, y 補正, 行のビット列[], 送り幅)}"""
    g = {}; cur = None; bits = None; enc = None
    bbx = None; dw = None; fbb = None
    for ln in open(path, encoding='latin1'):
        f = ln.split()
        if not f: continue
        k = f[0]
        if k == 'FONTBOUNDINGBOX': fbb = tuple(int(v) for v in f[1:5])
        elif k == 'ENCODING': enc = int(f[1])
        elif k == 'DWIDTH': dw = int(f[1])
        elif k == 'BBX': bbx = tuple(int(v) for v in f[1:5])
        elif k == 'BITMAP': bits = []
        elif k == 'ENDCHAR':
            if enc is not None and bits is not None:
                g[enc] = (bbx, bits, dw)
            bits = None; enc = None; bbx = None; dw = None
        elif bits is not None:
            v = int(f[0], 16); n = len(f[0]) * 4
            bits.append((v, n))
    return g, fbb

class Font:
    def __init__(self, kanji, ascii_=None):
        self.k, self.kbb = load_bdf(os.path.join(FD, kanji))
        self.uni = 'ISO10646' in open(os.path.join(FD, kanji), encoding='latin1').read(2000)
        self.a, self.abb = load_bdf(os.path.join(FD, ascii_)) if ascii_ else (None, None)
        self.h = self.kbb[1]
        self.asc = self.kbb[1] + self.kbb[3]   # ベースラインから上の高さ

    def glyph(self, ch):
        o = ord(ch)
        if self.uni:
            e = self.k.get(o); bb = self.kbb
        elif o < 0x80 and self.a is not None:
            e = self.a.get(o); bb = self.abb
        else:
            try: b = ch.encode('euc_jp')
            except UnicodeEncodeError: b = '〓'.encode('euc_jp')
            if len(b) == 1:
                b = (chr(0xFF01 + o - 0x21) if 0x21 <= o <= 0x7E else '　').encode('euc_jp')
            code = ((b[0] & 0x7F) << 8) | (b[1] & 0x7F)
            e = self.k.get(code); bb = self.kbb
        if e is None: return [], self.h // 2
        (w, h, xo, yo), bits, dw = e
        pts = []
        top = self.asc - (h + yo)
        for r, (v, n) in enumerate(bits):
            for c in range(w):
                if v & (1 << (n - 1 - c)): pts.append((xo + c, top + r))
        return pts, dw if dw else w

    def width(self, s):
        return sum(self.glyph(c)[1] for c in s)

FONTS = {}
def font(name):
    if name not in FONTS:
        FONTS[name] = {
            '8': lambda: Font('misaki_gothic_2nd.bdf'),
            '12': lambda: Font('shnmk12.bdf', 'shnm6x12a.bdf'),
            '12b': lambda: Font('shnmk12b.bdf', 'shnm6x12ab.bdf'),
            '14': lambda: Font('shnmk14.bdf', 'shnm7x14a.bdf'),
            '14b': lambda: Font('shnmk14b.bdf', 'shnm7x14ab.bdf'),
            '16': lambda: Font('shnmk16.bdf', 'shnm8x16a.bdf'),
            '16b': lambda: Font('shnmk16b.bdf', 'shnm8x16a.bdf'),
        }[name]()
    return FONTS[name]

NOHEAD = set('、。，．・：；？！ー」』）】〉》…‥ぁぃぅぇぉっゃゅょァィゥェォッャュョ〜')

def wrap(f, text, width):
    lines = []
    for para in text.split('\n'):
        cur = ''
        for ch in para:
            if cur and f.width(cur + ch) > width:
                if ch not in NOHEAD:
                    lines.append(cur); cur = ''
                elif len(cur) > 1 and f.width(cur + ch) > width + 2:
                    # 行頭に来られない字は、前の字といっしょに次の行へ送る
                    lines.append(cur[:-1]); cur = cur[-1]
            cur += ch
        lines.append(cur)
    return lines
