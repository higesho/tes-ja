# 綴りどおりに読む名前（ハンマーフェルの名前、怪物の名前など）をカタカナにする
#   kana('Grolantor') -> 'グロラントール'
V = 'aeiou'
ROW = {  # 子音: (a, i, u, e, o)
    'k': 'カキクケコ', 'g': 'ガギグゲゴ', 's': 'サシスセソ', 'z': 'ザジズゼゾ', 'n': 'ナニヌネノ',
    'h': 'ハヒフヘホ', 'b': 'バビブベボ', 'p': 'パピプペポ', 'm': 'マミムメモ', 'r': 'ラリルレロ',
}
SPECIAL = {
    't': ['タ', 'ティ', 'トゥ', 'テ', 'ト'], 'd': ['ダ', 'ディ', 'ドゥ', 'デ', 'ド'],
    'y': ['ヤ', 'イ', 'ユ', 'イェ', 'ヨ'], 'w': ['ワ', 'ウィ', 'ウ', 'ウェ', 'ウォ'],
    'f': ['ファ', 'フィ', 'フ', 'フェ', 'フォ'], 'v': ['ヴァ', 'ヴィ', 'ヴ', 'ヴェ', 'ヴォ'],
    'j': ['ジャ', 'ジ', 'ジュ', 'ジェ', 'ジョ'], 'sh': ['シャ', 'シ', 'シュ', 'シェ', 'ショ'],
    'ch': ['チャ', 'チ', 'チュ', 'チェ', 'チョ'], 'th': ['サ', 'シ', 'ス', 'セ', 'ソ'],
    'kw': ['クァ', 'クィ', 'ク', 'クェ', 'クォ'], 'ts': ['ツァ', 'ツィ', 'ツ', 'ツェ', 'ツォ'],
}
ALONE = {  # 母音が続かない子音
    'k': 'ク', 'g': 'グ', 's': 'ス', 'z': 'ズ', 'h': 'フ', 'b': 'ブ', 'p': 'プ', 'm': 'ム', 'r': 'ル',
    'l': 'ル', 't': 'ト', 'd': 'ド', 'y': 'イ', 'w': 'ウ', 'f': 'フ', 'v': 'ヴ', 'j': 'ジ',
    'sh': 'シュ', 'ch': 'チ', 'th': 'ス', 'kw': 'ク', 'ts': 'ツ', 'x': 'クス', 'n': 'ン',
}
VK = {'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ'}
DIG = [('sh', 'sh'), ('ch', 'ch'), ('th', 'th'), ('ph', 'f'), ('kh', 'k'), ('gh', 'g'), ('ck', 'k'),
       ('qu', 'kw'), ('zh', 'j'), ('ts', 'ts')]

def cv(c, v):
    k = 'aiueo'.index(v)
    if c == 'l': c = 'r'
    if c in ROW: return ROW[c][k]
    return SPECIAL[c][k]

def kana(word):
    s = word.lower()
    out = []
    i = 0; n = len(s)
    lastv = False   # 直前に出したのが母音で終わる音か
    def isv(j):
        if j >= n: return False
        if s[j] in V: return True
        # y は次が母音でなければ母音
        return s[j] == 'y' and not (j + 1 < n and s[j + 1] in V)
    def vch(j): return 'i' if s[j] == 'y' else s[j]
    while i < n:
        ch = s[i]
        if ch in "'-": i += 1; continue
        if isv(i):
            out.append(VK[vch(i)]); i += 1; lastv = True; continue
        # 子音（二字の綴りも）
        c = None
        for a, b in DIG:
            if s.startswith(a, i): c = b; i += len(a); break
        if c is None:
            c = ch; i += 1
            if c == 'c': c = 's' if (i < n and s[i] in 'eiy') else 'k'
            if c == 'q': c = 'k'
            if c == 'x':
                if isv(i): out.append('ク'); c = 's'
                else: out.append('クス'); continue
        # 同じ子音が続く
        if i < n and s[i] == ch and ch not in 'aeiouy':
            if ch in 'lrn': i += 1
            elif ch == 'm': out.append('ン'); i += 1
            elif isv(i + 1): out.append('ッ'); i += 1
            else: i += 1
        if isv(i):
            out.append(cv(c, vch(i))); i += 1; lastv = True; continue
        if c == 'n':
            out.append('ン'); lastv = False; continue
        if c == 'm' and i < n and s[i] in 'bp':
            out.append('ン'); lastv = False; continue
        if c == 'h':   # 母音の続かない h は読まない
            continue
        if c == 'r' and lastv and i < n and s[i] not in "'-" and not isv(i) or c == 'r' and lastv and i >= n:
            # 母音のあとの r は伸ばす（ar → アー、語末は tor → トール）
            if not out[-1].endswith('ー'): out.append('ー')
            if i >= n: out.append('ル')
            lastv = False
            continue
        out.append(ALONE.get(c, '')); lastv = False
    r = ''.join(out)
    while 'ーー' in r: r = r.replace('ーー', 'ー')
    return r

if __name__ == '__main__':
    import sys
    for w in sys.argv[1:] or ['Grolantor', 'Bakan-i', 'Brimunsi', "R'zamis", 'Vladimus', 'Nebuchezzar',
                              'Demogorgon', 'Baalith', 'Hammurabi', 'Mohamtaba', 'Skolath', 'Azarthrac']:
        print(w, kana(w))
