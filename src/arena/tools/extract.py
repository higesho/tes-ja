# 訳す英文を全部抜き出す → translation/en/*.tsv（id \t 英文 [\t 枠]）
import re, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import *
import exe_strings, bsa

OUT = os.path.join(WORK, 'translation', 'en')
NL, TAB = chr(10), chr(9)

# ---------- exe ----------
CITY_RANGES = [(0x3e954, 0x3eb7b), (0x43afa, 0x43b3f)]
# 先頭にデータのごみが付いているもの: 本当の始まりへずらす
SHIFT = {0x3765d: 'You have arrived in ', 0x3ec20: 'Morndas'}
KEEP_EXACT = {
    'Init entry.', 'Did load.', 'Must decompress.', 'Decompress done.', 'Copying blocks.', 'Done section.',
    'SpaceWare (R)', 'Bad segment', 'Too many conditions', 'FPS: %d', 'STA=', 'ARENADATA',
    'Unknown Memory Error!', 'Memory list blown!', 'Insufficient Base Memory!', 'Insufficient Expanded (EMS) Memory!',
    'Not enough EMS....\n', 'WARNING: City data file corrupted!', 'Module PlayFlc.asm. Error opening file',
    '%qf', '%dnl ', '%non', '%tem', '%nt', '%ef\'s', 'Uriel Septim',
}

JUNK = {'FK22Z<Z', 'AF2KZZ', 'Z2FUZZ', 'U}2PZZK', 'NIgI', 'iKnK', 'GxPx', 'tC', 'dS', ',o5oGoRo', 'mopqYN',
        'G' + chr(13) + 'anh' + chr(13) + 'c', 'KK22ZZ', 'pp', 'dd', 'Ej' + chr(10)}
TOKENS = {'acc', 'bc', 'dff', 'ef', 'gih', 'ih', 'jll', 'kl', 'chn', 'ltr', 'una', 'mag', 'mnk', 'bar',
          'bs', 'noble', 'tavern', 'temple', 'equip', 'mage', 'wcrypt', 'townpal', 'vilpal', 'tower', 'xfm'}

def exe_keep(off, s):
    """訳さない（そのまま残す）なら理由を返す"""
    if any(a <= off < b for a, b in CITY_RANGES): return 'city'
    if s in KEEP_EXACT: return 'internal'
    if s in JUNK: return 'junk'
    if s in TOKENS: return 'token'
    if s.endswith('$'): return 'dos'
    if s.startswith(chr(9)) and re.search('[A-Za-z]', s): return None
    if re.fullmatch(r'[a-z0-9_.*?$]+', s) and re.search(r'[0-9_.*?$]', s): return 'file'
    if re.fullmatch(r'[A-Z0-9 _<>?|:;"~%#`,./!@^&*()+=\[\]{}' + "'" + BS + BS + '-]+', s): return 'caps'
    if s.startswith('SpScale') or 'XXXX' in s or s.startswith('SPACEPLAYER'): return 'internal'
    if re.search(r'\.[a-z0-9$]{2,3}$', s) and ' ' not in s: return 'file'
    if 'C:' + BS in s: return 'file'
    return None

def extract_exe():
    rows, kept = [], []
    for off, b in exe_strings.cands():
        s = b.decode('latin1')
        if not exe_strings.looks_text(b):
            continue
        if off in SHIFT:
            k = s.index(SHIFT[off]); off += k; s = s[k:]
        why = exe_keep(off, s)
        if why: kept.append((off, why, s)); continue
        rows.append((off, len(s.encode('latin1')), s))
    # NUL で終わらない固定長のもの・色の制御を含むもの
    rows.append((0x3F8AA, 18, 'Know ye this also:'))
    rows.append((0x3F9A5, 14, chr(9) + chr(0xFE) + 'S' + chr(9) + chr(0xFD) + 'ave stats' + chr(13)))
    rows.append((0x3F9B5, 16, chr(9) + chr(0xFE) + 'R' + chr(9) + chr(0xFD) + 'eroll stats' + chr(13)))
    rows.append((0x409fa, 2, 'st'))
    # 頭文字だけ色を変える（\t+0x80 以上の指定）メニューの項目
    for m in re.finditer(rb'(?<=\x00)[\t\r\n\x20-\x7e\x80-\xff]*\t[\x80-\xff][\t\r\n\x20-\x7e\x80-\xff]*?(?=\x00)', exe_strings.d[0x32760:]):
        b = m.group()
        off = m.start() + 0x32760
        if len(re.findall(rb'[A-Za-z]', b)) >= 3 and off not in (0x3F9A5, 0x3F9B5):
            rows.append((off, len(b), b.decode('latin1')))
    rows.sort()
    with open(os.path.join(OUT, 'exe.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for off, n, s in rows: f.write(f'x{off:05x}\t{esc(s)}\t{n}\n')
    with open(os.path.join(OUT, 'exe_kept.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for off, why, s in kept: f.write(f'x{off:05x}\t{why}\t{esc(s)}\n')
    return len(rows), len(kept)

def extract_template():
    ents = template_parse(read_game('TEMPLATE.DAT'))
    n = 0
    with open(os.path.join(OUT, 'template.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for i, (keyline, vars_, amp) in enumerate(ents):
            for j, v in enumerate(vars_):
                if not v.strip(): continue
                f.write(f't{i:03d}:{j}\t{esc(v)}\t{keyline.strip()}\n'); n += 1
    return n

def extract_nul():
    n = 0
    for name, pre in [('ARTFACT1.DAT', 'a1_'), ('ARTFACT2.DAT', 'a2_'), ('EQUIP.DAT', 'eq_'),
                      ('MUGUILD.DAT', 'mg_'), ('SELLING.DAT', 'se_'), ('TAVERN.DAT', 'tv_')]:
        items = nul_parse(read_game(name))
        with open(os.path.join(OUT, pre[:-1] + '.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            for i, s in enumerate(items):
                if not s.strip() or s == '?': continue
                f.write(f'{pre}{i:03d}\t{esc(s)}\n'); n += 1
    return n

def extract_misc():
    n = 0
    with open(os.path.join(OUT, 'dungeon.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for i, e in enumerate(dungeon_parse(read_game('DUNGEON.TXT'))):
            if not e: continue
            f.write(f'dn{i}\t{esc(e[0])}\n'); f.write(f'dd{i}\t{esc(e[1])}\n'); n += 2
    with open(os.path.join(OUT, 'spellmkr.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for k, s in spellmkr_parse(read_game('SPELLMKR.TXT')):
            f.write(f'sm{k}\t{esc(s)}\n'); n += 1
    with open(os.path.join(OUT, 'question.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for num, q, ans in question_parse(read_game('QUESTION.TXT')):
            f.write(f'q{int(num):02d}\t{esc(q)}\n'); n += 1
            for k, s, mark in ans:
                f.write(f'q{int(num):02d}{k}\t{esc(s)}\n'); n += 1
    return n

def extract_inf():
    d, ents = bsa.read()
    n = 0
    with open(os.path.join(OUT, 'inf.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for e in ents:
            if not e[0].upper().endswith('.INF'): continue
            t = bsa.get(d, e).decode('latin1')
            i = t.find('@TEXT')
            if i < 0: continue
            # *TEXT n の塊ごと
            for m in re.finditer(r'\*TEXT\s+(\d+)\r\n(.*?)(?=\r\n\*TEXT|\r\n@|\Z)', t[i:], re.S):
                body = m.group(2)
                f.write(f'i_{e[0]}#{m.group(1)}\t{esc(body)}\n'); n += 1
    return n

def extract_spellsg():
    d = read_game('SPELLSG.65')
    n = 0
    with open(os.path.join(OUT, 'spellsg.tsv'), 'w', encoding='utf-8', newline=NL) as f:
        for i in range(len(d) // 85):
            name = d[i * 85 + 52:i * 85 + 85].split(bytes(1))[0].decode('latin1')
            if name.strip():
                f.write('sg_%03d' % i + TAB + esc(name) + TAB + '32' + NL); n += 1
    return n

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    print('exe', extract_exe())
    print('template', extract_template())
    print('dat', extract_nul())
    print('misc', extract_misc())
    print('inf', extract_inf())
    print('spellsg', extract_spellsg())
