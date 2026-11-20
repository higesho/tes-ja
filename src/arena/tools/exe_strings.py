# 展開した ACD の像から、画面に出そうな英文の候補を抜き出す → translation/en/exe_all.tsv
# 列: 番地(hex) \t 枠(バイト) \t 英文（\r \n \t \\ を逃がす）
import re, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = open(os.path.join(HERE, '..', 'orig', 'acd_unpacked.bin'), 'rb').read()
LO, HI = 0x32760, len(d)

FILEEXT = re.compile(rb'\.(img|dat|cif|cfa|mif|inf|voc|xmi|xfm|flc|cel|mnu|set|col|lgt|rci|65|txt|bnk|adv|exe|com|bat|cfg|ini|dfa|rmd|sav|ntz|lst|gld|clr|bak|cpy|ico)$', re.I)

def esc(b):
    s = b.decode('latin1')
    return s.replace('\\', '\\\\').replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t')

def cands():
    out = []
    i = LO
    while i < HI:
        if d[i] == 0:
            i += 1; continue
        j = d.index(b'\0', i)
        s = d[i:j]
        # 直前が NUL のものだけ（文字列の途中から始まる断片は除く）
        if d[i - 1] == 0 and len(s) >= 2 and all(32 <= c < 127 or c in (9, 10, 13) for c in s):
            out.append((i, s))
        i = j + 1
    return out

def looks_text(s):
    if FILEEXT.search(s.strip()): return False
    letters = sum(c.isalpha() for c in s.decode('latin1'))
    if letters < 2: return False
    if not re.search(rb'[A-Za-z]{2}', s): return False
    # 記号ばかり・同じ字の繰り返しは除く
    if re.fullmatch(rb'[A-Z0-9_]{1,3}', s): return False
    return True

if __name__ == '__main__':
    os.makedirs(os.path.join(HERE, '..', 'translation', 'en'), exist_ok=True)
    rows = [(a, s) for a, s in cands() if looks_text(s)]
    with open(os.path.join(HERE, '..', 'translation', 'en', 'exe_all.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for a, s in rows:
            # 枠 = 英文の長さ（NUL の後ろに続く NUL も使える）
            k = a + len(s)
            while k + 1 < HI and d[k + 1] == 0 and k - a < len(s) + 0: k += 1
            f.write(f'{a:05x}\t{len(s)}\t{esc(s)}\n')
    print(len(rows), sum(len(s) for a, s in rows))
