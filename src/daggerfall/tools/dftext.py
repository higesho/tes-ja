# Daggerfall の文章ファイルを「訳す単位（段落）」に分け、訳から組み立て直す
#
#   TEXT.RSC / *.QRC : 記録 → 0xFF で候補に分け → 0xFC/0xFD で行に分け → 段落にまとめる
#   本（BOK*.TXT）  : 頁ごとに行（0x00 区切り）を段落にまとめ、組み立てでは流し込み直す
#   経歴（BIOG*.TXT）: 問いと答えの文
#
# 段落の英文は 1 行の文にして訳者に渡す。組み立てでは日本語を画素の幅で折り返し、
# 元の行の終わりの符号（0xFC 中寄せ / 0xFD 左寄せ）で行を区切る。
# 日本語の字と字の間には 0x1F（幅 0 の折り返しの目印）を入れる（ゲームの自動折り返し用）。
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rsc

GAME = os.path.join(HERE, '..', '..')
A2 = os.path.join(GAME, 'arena2')

# ---------- 字の幅（FONT0003 が本文の字体） ----------
def _font_widths(n):
    b = open(os.path.join(A2, 'FONT%04d.FNT' % n), 'rb').read()
    spw, h = struct.unpack_from('<HH', b, 0)
    w = {}
    for c in range(0x21, 0x100):
        w[c] = struct.unpack_from('<HH', b, 4 + (c - 0x21) * 4)[1] + 1
    w[0x20] = spw
    return w
FW = _font_widths(3)
JW = 8                 # 日本語 1 字（美咲 8x8）
MACRO_W = 30           # %xxx・_xxx_ などの差し込みは目安 30 画素

MACRO_RE = re.compile(r'(%[a-z][a-z0-9]*|[_=]{1,2}[A-Za-z][A-Za-z0-9]*_)')

def en_width(b):
    """英文（バイト列）の画素幅（差し込みは目安で数える）"""
    s = b.decode('latin1')
    w = 0
    for part in MACRO_RE.split(s):
        if MACRO_RE.fullmatch(part):
            w += MACRO_W
        else:
            w += sum(FW.get(ord(c), 0) for c in part if ord(c) >= 0x20)
    return w

def ja_width(s):
    w = 0
    for part in MACRO_RE.split(s):
        if MACRO_RE.fullmatch(part):
            w += MACRO_W
        else:
            for c in part:
                o = ord(c)
                w += JW if o >= 0x80 else FW.get(o, 0)
    return w

# ---------- 折り返し ----------
NOSTART = set('、。，．・：；？！゛゜ヽヾゝゞ々ー）］｝」』〉》】〕’”…‥ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ〜～!?,.)')
NOEND = set('（［｛「『〈《【〔‘“(')

def tokens(s):
    """折り返しの単位: 差し込み・半角の語・日本語 1 字"""
    out = []
    for part in MACRO_RE.split(s):
        if not part:
            continue
        if MACRO_RE.fullmatch(part):
            out.append(part); continue
        for m in re.finditer(r'[\x21-\x7e]+|\s|.', part):
            out.append(m.group())
    return out

def wrap(s, maxw, first=None):
    """日本語の文を画素幅 maxw（1 行目だけ first）で折り返す（行頭・行末の禁則あり）"""
    toks = tokens(s)
    lines, cur = [], []
    def w(ts): return ja_width(''.join(ts))
    for t in toks:
        lim = first if (first is not None and not lines) else maxw
        if cur and w(cur + [t]) > lim:
            if t in NOSTART or (t.isspace() and False):
                cur.append(t); continue
            carry = []
            while len(cur) > 1 and cur[-1] in NOEND:
                carry.insert(0, cur.pop())
            lines.append(''.join(cur).rstrip())
            cur = carry + ([] if t.isspace() else [t])
        else:
            cur.append(t)
    if cur:
        lines.append(''.join(cur).rstrip())
    return lines or ['']

# ---------- ゲームのバイト列へ ----------
import jpdata

def to_game(s, hints=True):
    """日本語の文 → ゲームのバイト列。日本語の字の間（禁則を守る所）に 0x1F を入れる"""
    out = bytearray()
    prev = None
    mac = False          # %記号（名前などに置き換わる所）の中
    for ch in s:
        jp = ord(ch) >= 0x80 and not (0xF0 <= ord(ch) <= 0xFF)
        pjp = prev is not None and ord(prev) >= 0x80 and not (0xF0 <= ord(prev) <= 0xFF)
        if hints and prev is not None:
            if jp and pjp and ch not in NOSTART and prev not in NOEND:
                out.append(0x1F)
            # 日本語と %記号の境目でも折り返せるように（名前が長いと前の字ごと次の行へ送られるため）
            elif pjp and ch == '%' and prev not in NOEND:
                out.append(0x1F)
            elif mac and jp and ch not in NOSTART:
                out.append(0x1F)
        if ch == '%':
            mac = True
        elif mac and not (ch.isascii() and ch.isalnum()):
            mac = False
        out += jpdata.to_game(ch)
        prev = ch
    return bytes(out)

# ---------- TEXT.RSC / QRC ----------
def _split_lines(sub):
    """候補 1 つ → [(内容, 終わりの符号 or None)]"""
    lines, cur = [], bytearray()
    i = 0
    while i < len(sub):
        c = sub[i]
        if c == 0xFB and i + 1 < len(sub):
            cur += sub[i:i + 2]; i += 2; continue
        if c in (0xFC, 0xFD):
            lines.append((bytes(cur), c)); cur = bytearray()
        else:
            cur.append(c)
        i += 1
    if cur:
        lines.append((bytes(cur), None))
    return lines

def _is_text(b):
    return bool(re.search(rb'[A-Za-z]{2}', b))

# 新しい段落の始まり: 「{1.」「a)」「Duration:」のような項目の頭
ITEM_RE = re.compile(rb'^\s*(\{?\d+\.\s|[a-z]\)\s|[A-Z][a-z]+(?: [A-Z][a-z]+)?:\s)')
WRAP_MAX = 260         # 日本語の折り返しの幅の上限（英語にも 300 画素を超える行があり、画面からはみ出す）
# 訳さない頭: 空白と「{1.」「a)」
LEAD_RE = re.compile(rb'^\s*(?:\{?\d+\.\s*|[a-z]\)\s*)?')

def rsc_units(rid, data):
    """記録 → (骨組み, [(番号, 英文, 情報)])。骨組みは組み立てに使う"""
    end = data.endswith(b'\xfe')
    body = data[:-1] if end else data
    subs = body.split(b'\xff')
    skel = []
    units = []
    for si, sub in enumerate(subs):
        lines = _split_lines(sub)
        maxw = max([en_width(l) for l, t in lines] + [0])
        paras = []          # [('raw', bytes) | ('para', [lines], term)]
        for l, t in lines:
            if b'\xfb' in l or not _is_text(l):
                paras.append(['raw', l, t]); continue
            if paras and paras[-1][0] == 'para' and paras[-1][2] == t and t is not None and not ITEM_RE.match(l):
                prev = paras[-1][1][-1]
                if en_width(prev) >= maxw * 0.6 and not prev.rstrip().endswith(b':'):
                    paras[-1][1].append(l); continue
            paras.append(['para', [l], t])
        sk = []
        for p in paras:
            if p[0] == 'raw':
                l, t = p[1], p[2]
                # 位置の符号のある行: 符号の後の語の塊ごとに訳す
                segs = re.split(rb'(\xfb.)', l, flags=re.S)
                out = []
                for seg in segs:
                    if seg.startswith(b'\xfb') or not _is_text(seg):
                        out.append(('raw', seg))
                    else:
                        key = '%d:%d:%d' % (rid, si, len(units))
                        lead = re.match(rb'\s*', seg).group()
                        units.append((key, seg.strip().decode('latin1'), {'single': 1}))
                        out.append(('unit', key, lead, seg))
                sk.append(('line', out, t))
            else:
                ls, t = p[1], p[2]
                key = '%d:%d:%d' % (rid, si, len(units))
                lead = LEAD_RE.match(ls[0]).group()          # 頭の空白と「{1.」「a)」の印は訳さない
                en = ' '.join([ls[0][len(lead):].strip().decode('latin1')] + [x.strip().decode('latin1') for x in ls[1:]])
                # 続きの行の字下げ（2 行目以降に共通の頭の空白）
                cont = b''
                if len(ls) > 1:
                    ind = [re.match(rb' *', x).group() for x in ls[1:]]
                    cont = min(ind, key=len)
                    if len(cont) < 2: cont = b''
                w = max(en_width(x) for x in ls)
                units.append((key, en, {'lines': len(ls)}))
                sk.append(('para', key, (lead, cont), t, len(ls), max(w, maxw if len(ls) > 1 else w), ls))
        skel.append(sk)
    return (skel, end), units

def rsc_build(skel, ja, en):
    """骨組みと訳（番号 → 日本語）から記録のバイト列を作る。訳が無ければ英文のまま"""
    skel, end = skel
    out = bytearray()
    for si, sk in enumerate(skel):
        if si:
            out.append(0xFF)
        for item in sk:
            if item[0] == 'line':
                _, segs, t = item
                for seg in segs:
                    if seg[0] == 'raw':
                        out += seg[1]
                    else:
                        _, key, lead, orig = seg
                        j = ja.get(key)
                        out += (lead + to_game(j)) if j is not None else orig
                if t is not None:
                    out.append(t)
            else:
                _, key, lead, t, nlines, w, orig = item
                j = ja.get(key)
                if j is None:
                    # 訳が無い: 元の行のまま
                    for x in orig:
                        out += x
                        if t is not None:
                            out.append(t)
                    continue
                else:
                    lead, cont = lead
                    w = min(w, WRAP_MAX)
                    # 短い段落（品物の説明など差し込みの多いもの）は折り返さない。窓は長い行に合わせて広がる
                    if t is None or w < 160 or (nlines == 1 and ja_width(j) + en_width(lead) <= max(w, 1) * 1.15):
                        lines = [j]
                    else:
                        lines = wrap(j, max(w - en_width(cont), 96), first=max(w - en_width(lead), 96))
                    enc = [to_game(x) for x in lines]
                for k, x in enumerate(enc):
                    out += (lead if k == 0 else cont) + x
                    if t is not None:
                        out.append(t)
    if end:
        out.append(0xFE)
    return bytes(out)

def _wrap_en(s, maxw):
    words = s.split(' ')
    lines, cur = [], ''
    for w in words:
        c = (cur + ' ' + w) if cur else w
        if cur and en_width(c.encode('latin1')) > maxw:
            lines.append(cur); cur = w
        else:
            cur = c
    if cur:
        lines.append(cur)
    return lines

def rsc_file_units(path, prefix):
    recs = rsc.load(open(path, 'rb').read())
    allu, skels = [], []
    for rid, d in recs:
        sk, us = rsc_units(rid, d)
        skels.append((rid, sk))
        for k, e, inf in us:
            allu.append((prefix + k, e, inf))
    return skels, allu

def rsc_file_build(skels, prefix, ja, en):
    recs = []
    for rid, sk in skels:
        pja = {k[len(prefix):]: v for k, v in ja.items() if k.startswith(prefix)} if False else None
        recs.append((rid, rsc_build(sk, _Sub(ja, prefix), _Sub(en, prefix))))
    return rsc.save(recs)

class _Sub:
    """接頭辞つきの辞書を、接頭辞なしの番号で引く"""
    def __init__(self, d, prefix): self.d, self.p = d, prefix
    def get(self, k, default=None): return self.d.get(self.p + k, default)
    def __getitem__(self, k): return self.d[self.p + k]

if __name__ == '__main__':
    sk, us = rsc_file_units(os.path.join(A2, 'TEXT.RSC'), 'rsc:')
    print(len(us), 'units')
    en = {k: e for k, e, _ in us}
    b = rsc_file_build(sk, 'rsc:', {}, en)
    orig = open(os.path.join(A2, 'TEXT.RSC'), 'rb').read()
    # 英文のまま組み立てて、元とどれだけ違うか
    r1 = dict(rsc.load(orig)); r2 = dict(rsc.load(b))
    diff = [k for k in r1 if r1[k] != r2[k]]
    print('違う記録', len(diff), '/', len(r1))
    for k in diff[:3]:
        print(k, r1[k][:200]); print('  ', r2[k][:200])

# ---------- 本（BOK*.TXT） ----------
BOOK_LINES = 22        # 組み立てで 1 頁に入れる行数（英語の頁は 23 行前後）

def book_load(b):
    title = b[:64].split(b'\0')[0]; author = b[64:128].split(b'\0')[0]
    n = struct.unpack_from('<H', b, 0xE0 + 10)[0]
    offs = struct.unpack_from('<%dI' % n, b, 0xE0 + 12)
    pages = [b[offs[i]:(offs[i + 1] if i + 1 < n else len(b))] for i in range(n)]
    return title, author, pages

def book_save(head, title, author, pages):
    """head: 元の先頭 0xEA バイト（値段など）"""
    h = bytearray(head[:0xEA])
    h[0:64] = title[:63].ljust(64, b'\0'); h[64:128] = author[:63].ljust(64, b'\0')
    n = len(pages)
    struct.pack_into('<H', h, 0xEA - 2, n)
    base = 0xEA + 4 * n
    offs, body = [], bytearray()
    for p in pages:
        offs.append(base + len(body)); body += p
    return bytes(h) + struct.pack('<%dI' % n, *offs) + bytes(body)

def _book_lines(pages):
    """全頁を行の並びに: ('line', bytes) と ('page',)"""
    out = []
    for p in pages:
        body = p[:-1] if p.endswith(b'\xf6') else p
        parts = body.split(b'\x00')
        for i, l in enumerate(parts):
            if i == len(parts) - 1:
                if l.strip():
                    out.append(('tail', l))
            else:
                out.append(('line', l))
        out.append(('page',))
    return out

def book_units(name, b):
    """本 → (骨組み, units)。骨組みは段落の流れ"""
    title, author, pages = book_load(b)
    units = [('b:%s:title' % name, title.decode('latin1'), {'single': 1}),
             ('b:%s:author' % name, author.decode('latin1'), {'single': 1})]
    flow = []          # ('raw', bytes) / ('blank',) / ('para', key, indent) / ('center', prefix, key)
    cur = None
    maxw = 0
    def newpara(text, indent):
        nonlocal cur
        key = 'b:%s:%d' % (name, len(units))
        units.append([key, text, {}])
        flow.append(('para', key, indent))
        cur = units[-1]
    for it in _book_lines(pages):
        if it[0] == 'page':
            continue
        l = it[1]
        if it[0] == 'tail':
            flow.append(('rawtail', l)); cur = None; continue
        if not l.strip():
            flow.append(('blank',)); cur = None; continue
        m = re.match(rb'^((?:[\xf9\xfa\xfb].|[\xf0-\xf8\xfc-\xff]|[\x00-\x1f])*)(.*)$', l, re.S)
        pre, txt = m.group(1), m.group(2)
        if pre:
            if pre.startswith(b'\xfd') and _is_text(txt):
                key = 'b:%s:%d' % (name, len(units))
                units.append([key, txt.decode('latin1').strip(), {'single': 1}])
                flow.append(('center', pre, key)); cur = None
            elif not txt.strip():
                flow.append(('raw', l)); cur = None
            else:
                flow.append(('raw', pre)); cur = None
                newpara(txt.decode('latin1').strip(), 1)
            continue
        maxw = max(maxw, en_width(l))
        # 行の途中の 4 つ以上の空白は段落の始まり
        pieces = re.split(rb'\s{4,}', l)
        for k, pc in enumerate(pieces):
            t = pc.decode('latin1').strip()
            if not t:
                if k > 0: cur = None
                continue
            if k == 0 and cur is not None and not l.startswith(b' '):
                cur[1] += ' ' + t
            else:
                newpara(t, 1 if (k > 0 or l.startswith(b' ')) else 0)
    units = [tuple(u) for u in units]
    return (b[:0xEA], flow, maxw), units

def book_build(skel, ja, en, name):
    head, flow, maxw = skel
    title = ja.get('b:%s:title' % name); author = ja.get('b:%s:author' % name)
    title = to_game(title, hints=False) if title else en['b:%s:title' % name].encode('latin1')
    author = to_game(author, hints=False) if author else en['b:%s:author' % name].encode('latin1')
    W = max(maxw, 200)
    lines = []
    for it in flow:
        if it[0] == 'blank':
            lines.append(b'')
        elif it[0] in ('raw', 'rawtail'):
            lines.append(it[1])
        elif it[0] == 'center':
            j = ja.get(it[2])
            lines.append(it[1] + (to_game(j) if j else en[it[2]].encode('latin1')))
        else:
            _, key, indent = it
            j = ja.get(key)
            if j is None:
                ls = _wrap_en(en[key], W)
                ls = [x.encode('latin1') for x in ls]
                if indent and ls: ls[0] = b' ' + ls[0]
            else:
                if indent: j = '　' + j
                ls = [to_game(x) for x in wrap(j, W)]
            lines += ls
    # 頁に詰める（段落の途中でも切る。空行で始まる頁は空行を落とす）
    pages, cur = [], []
    for l in lines:
        if len(cur) >= BOOK_LINES:
            pages.append(cur); cur = []
            if not l: continue
        cur.append(l)
    if cur: pages.append(cur)
    pb = [b''.join(x + b'\x00' for x in p) + b'\xf6' for p in pages]
    return book_save(head, title, author, pb)

# ---------- 経歴（BIOG*.TXT） ----------
_BIOG_EFFECT = re.compile(r'^\t\s*([#!]\d+|-?\d+ *[+-] *\d+|r[a-z]*\d+ *[+-] *\d+|IT\b.*|GP\b.*|[A-Z]{2}\b.*|Q\d.*)\s*$')

def biog_units(name, b):
    # 改行は \r\n と \n が混ざっている。行は \n で分け、行末の \r は行の一部として残す
    lines = b.decode('latin1').split('\n')
    flow, units = [], []
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r'^(\d+\.|[a-z]\.)([ \t]+)([^\r]*)\r?$', l)
        if m and m.group(3).strip():
            label, sp, txt = m.groups()
            j = i + 1
            more = []
            if label[0].isdigit():
                while j < len(lines) and lines[j].startswith('\t') and not _BIOG_EFFECT.match(lines[j].rstrip('\r')) and lines[j].strip():
                    more.append(lines[j].strip()); j += 1
            key = 'g:%s:%d' % (name, len(units))
            en = ' '.join([txt.strip()] + more)
            w = max(en_width(x.encode('latin1')) for x in [txt] + more)
            units.append((key, en, {'q': 1} if label[0].isdigit() else {'single': 1}))
            flow.append(('unit', label, sp, key, len(more) + 1, w, lines[i:j]))
            i = j
            continue
        flow.append(('raw', l))
        i += 1
    return flow, units

def biog_build(flow, ja, en):
    out = []
    for it in flow:
        if it[0] == 'raw':
            out.append(it[1].encode('latin1')); continue
        _, label, sp, key, n, w, orig = it
        j = ja.get(key)
        if j is None:
            out += [x.encode('latin1') for x in orig]; continue
        eol = b'\r' if orig[0].endswith('\r') else b''
        ls = wrap(j, max(w, 120)) if n > 1 or ja_width(j) > w * 1.2 else [j]
        out.append(label.encode() + sp.encode() + to_game(ls[0]) + eol)
        for x in ls[1:]:
            out.append(b'\t' + to_game(x) + eol)
    return b'\n'.join(out)
