# 文字の出どころごとの読み書き（抜き出しと組み立ての両方で使う）
import re, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, '..', '..'))
WORK = os.path.normpath(os.path.join(HERE, '..'))
BS = chr(92)

def esc(s):
    return s.replace(BS, BS + BS).replace('\r', BS + 'r').replace('\n', BS + 'n').replace('\t', BS + 't')

def unesc(s):
    out = []; i = 0
    while i < len(s):
        if s[i] == BS and i + 3 < len(s) and s[i + 1] == 'x' and all(ch in '0123456789abcdefABCDEF' for ch in s[i + 2:i + 4]):
            out.append(chr(int(s[i + 2:i + 4], 16))); i += 4; continue
        if s[i] == BS and i + 1 < len(s):
            c = s[i + 1]
            out.append({'r': '\r', 'n': '\n', 't': '\t', '0': '\0'}.get(c, c)); i += 2
        else:
            out.append(s[i]); i += 1
    return ''.join(out)

def enc(s):
    # 日本語は EUC-JP、0x80〜0xFF の字（訳の表で 逆斜線+xNN と書いた制御バイト）はそのまま 1 バイトにする
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if o < 0x100: out.append(o)
        else: out += ch.encode('euc_jp')
    return bytes(out)

def read_game(name):
    return open(os.path.join(GAME, name), 'rb').read()

# ---------- TEMPLATE.DAT ----------
def template_parse(b):
    """[(key_line, [variant_text, ...], raw_tail)] を返す。variant_text は行をつないだ 1 行"""
    t = b.decode('latin1')
    heads = [m.start() for m in re.finditer(r'(?m)^#', t)]
    ents = []
    for i, h in enumerate(heads):
        end = heads[i + 1] if i + 1 < len(heads) else len(t)
        body = t[h:end]
        nl = body.find('\r\n')
        keyline = body[:nl]
        rest = body[nl + 2:]
        parts = rest.split('&')
        vars_ = []
        for p in parts[:-1] if len(parts) > 1 else parts:
            lines = [ln.strip() for ln in p.replace('\r', '').split('\n')]
            vars_.append(re.sub(' +', ' ', ' '.join(ln for ln in lines if ln)).strip())
        ents.append((keyline, vars_, len(parts) > 1))
    return ents

def template_build(ents, tr):
    """tr: id -> 訳。id は '見出し番号:変種番号'（見出しの並び順で）"""
    out = []
    for i, (keyline, vars_, amp) in enumerate(ents):
        out.append(keyline + '\r\n')
        for j, v in enumerate(vars_):
            s = tr.get(f'{i:03d}:{j}', v)
            out.append(s + ('&\r\n\r\n' if amp else '\r\n\r\n'))
    return ''.join(out)

# ---------- NUL 区切りの .DAT ----------
def nul_parse(b):
    return b.decode('latin1').split('\0')

def nul_build(items, tr, prefix):
    return '\0'.join(tr.get(f'{prefix}{i:03d}', s) for i, s in enumerate(items))

# ---------- DUNGEON.TXT（名前\r\n説明…\r\n#\r\n） ----------
def dungeon_parse(b):
    t = b.decode('latin1')
    blocks = t.split('#\r\n')
    ents = []
    for blk in blocks:
        if not blk.strip(): ents.append(None); continue
        name, _, desc = blk.partition('\r\n')
        lines = [ln.strip() for ln in desc.split('\r\n')]
        ents.append((name.strip(), ' '.join(ln for ln in lines if ln)))
    return ents

# ---------- SPELLMKR.TXT（#NN\r\n説明…） ----------
def spellmkr_parse(b):
    t = b.decode('latin1')
    ents = []
    for m in re.finditer(r'#(\d+)\r\n(.*?)(?=\r\n#|\Z)', t, re.S):
        lines = [ln.strip() for ln in m.group(2).split('\r\n')]
        ents.append((m.group(1), ' '.join(ln for ln in lines if ln)))
    return ents

# ---------- QUESTION.TXT ----------
def question_parse(b):
    """[(番号, 問い, [(記号, 答え, 印)...])]"""
    t = b.decode('latin1')
    qs = []
    cur = None
    for ln in t.split('\n'):
        m = re.match(r'^(\d+)\.\s+(.*)$', ln)
        a = re.match(r'^([abc])\)\s*(.*)$', ln)
        if m:
            cur = [m.group(1), m.group(2).strip(), []]; qs.append(cur)
        elif a and cur:
            cur[2].append([a.group(1), a.group(2).strip()])
        elif ln.strip() and cur:
            if cur[2]: cur[2][-1][1] += ' ' + ln.strip()
            else: cur[1] += ' ' + ln.strip()
    out = []
    for n, q, ans in qs:
        aa = []
        for k, s in ans:
            mm = re.search(r'\s*\((\d+[a-z])\)\s*$', s)
            aa.append((k, s[:mm.start()] if mm else s, mm.group(1) if mm else ''))
        out.append((n, q, aa))
    return out
