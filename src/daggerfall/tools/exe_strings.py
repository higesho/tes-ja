# FALL.EXE の中の画面用の文字列を選び出す → translation/en/exe.tsv（番号 番地 種類 英文）
#   種類 P: 参照（再配置）で指される文字列。日本語は広げた所に置き、参照を張り替える（長さの制限なし）
#   種類 I: 品物の型の名前（24 バイトの欄、日本語 11 字まで）。その場で書き換える
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dfdis import L, XREF

T = os.path.join(HERE, '..', 'translation')

# 画面に出ない（内部の名前・設定・試験用・エラー）範囲 [始め, 終わり)
EXCLUDE = [
    (0x170000, 0x170077),   # main.c など
    (0x1700a0, 0x170133 + 8),
    (0x170140, 0x1701ac),
    (0x1701ac, 0x1702cc),   # 出来事の内部名（War Beg など）
    (0x170e54, 0x170edb),   # 操作の設定名（JOY 1 など）
    (0x170f7c, 0x171044),   # 試験用の命令
    (0x171083, 0x17110c),   # 試験用
    (0x171975, 0x171995),   # STR INT …
    (0x171eec, 0x171f03),   # 代名詞（%g 用。英語のまま）
    (0x173120, 0x173126),   # euioa
    (0x174395, 0x1744c4),   # 内部の名前（World Flat …）
    (0x174f71, 0x175277),   # 内部・エラー
    (0x175adb, 0x175c40),
    (0x176a97, 0x176b6c),   # 設定の名前
    (0x176bc1, 0x176cc0),
    (0x176e4d, 0x176e9e),
    (0x17748e, 0x1774a3),   # "the "
    (0x1774b4, 0x17d000),   # 実行時ライブラリ・MemCheck・差し込み記号の表
]
SKIP_RE = re.compile(r'^(Invalid|Unable|Error|ERROR|bad faction|Insufficent|Exceeded|Bad |Failed|MEM |Clean exit|TES: |Memory |Object count|Quest DEBUG|Cheat code|LOC: |Last object|Duplicate|Inconsistent|Allocating|flag %d|Player : |Quest : |\(wisdom\?\)|text\.rsc|abcb|o0a0|%s \(|Today is a day for summoning)')
FILE_RE = re.compile(r'\.(c|img|cif|cfa|rci|vid|hmi|dat|flc|wav|raw|txt|bsa|def|std|pak|col|pal|bnk|qbn|qrc|amf|atf|rmb|rdb|rdi|sav|fnt|exe|bin|cfg|lst|gfx|snd|tbl|bmp|hs2|grd|wld|bss|anc|cel|386|inf|tde|\?\?\?|\d{3})$|\\|%\d*[a-z]?\.|\.%', re.I)
ITEM_START, ITEM_END, ITEM_STRIDE = 0x17d22a, 0x18082a, 0x30

def excluded(a):
    return any(s <= a < e for s, e in EXCLUDE)

def pointer_strings():
    ob = L.objs[2]; buf = bytes(L.img[3])
    out = []
    for m in re.finditer(rb'[\x20-\x7e]{2,}\x00', buf):
        a = ob['base'] + m.start()
        s = m.group()[:-1].decode('latin1')
        if a >= 0x177460 or excluded(a) or not XREF.get(a):
            continue
        if not re.search(r'[A-Za-z]{2}', s) or FILE_RE.search(s) or SKIP_RE.search(s):
            continue
        if re.fullmatch(r'%[a-z0-9]+', s) or re.fullmatch(r'[A-Z]{2,8}', s) and s not in ('NONE', 'ACTIVE', 'OVERDUE', 'PAST DUE'):
            continue
        if re.fullmatch(r'[A-Z][a-z]+[A-Z][A-Za-z]*', s):     # QuestHolder のような内部の名前
            continue
        out.append((a, 'P', s))
    return out

def item_names():
    out = []
    for a in range(ITEM_START, ITEM_END, ITEM_STRIDE):
        nm = L.read(a, 24).split(b'\0')[0].decode('latin1')
        if nm:
            out.append((a, 'I', nm))
    return out

if __name__ == '__main__':
    ps = pointer_strings(); it = item_names()
    os.makedirs(os.path.join(T, 'en'), exist_ok=True)
    with open(os.path.join(T, 'en', 'exe.tsv'), 'w', encoding='utf-8') as f:
        for a, k, s in ps + it:
            f.write('e%06x\t%x\t%s\t%s\n' % (a, a, k, s))
    print('参照つき', len(ps), '品物', len(it))
