# DOS 版の訳から「英語 → 日本語」の辞書を作り、DFU の CSV の値に当てる
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
DFJP = os.path.join(HERE, '..', '..', '..', 'Daggerfall', 'jp_work')
sys.path.insert(0, os.path.join(DFJP, 'tools')); sys.path.insert(0, HERE)
import dfumark

def norm(s):
    return re.sub(r'\s+', ' ', s.replace('\r', '')).strip().lower()

def en_ja():
    import build
    uja = build.apply_fixes(build.load_ja())
    d = {}
    for l in open(os.path.join(DFJP, 'translation', 'en', 'uniq.tsv'), encoding='utf-8'):
        uid, src, kind, e = l.rstrip('\n').split('\t', 3)
        if uid in uja:
            d.setdefault(norm(e), uja[uid])
    for l in list(open(os.path.join(DFJP, 'translation', 'glossary.tsv'), encoding='utf-8'))[1:]:
        f = l.rstrip('\n').split('\t')
        if len(f) >= 2 and f[1]:
            d.setdefault(norm(f[0]), f[1])
    # DFU 用に新しく訳したもの（translation/out/*.tsv: 表<TAB>キー<TAB>日本語）は apply の extra で使う
    for l in open(os.path.join(DFJP, 'translation', 'en', 'exe.tsv'), encoding='utf-8'):
        eid, addr, k, s = l.rstrip('\n').split('\t', 3)
        if eid in uja:
            d.setdefault(norm(s), uja[eid])
    return d

def apply(name, d, extra=None):
    """CSV の各行: 訳があれば (key, ja, en) 、無ければ (key, None, en)"""
    rows = []
    for k, v in dfumark.read_csv(name):
        j = (extra or {}).get(k) or d.get(norm(v))
        rows.append((k, j, v))
    return rows

if __name__ == '__main__':
    d = en_ja()
    print('辞書', len(d))
    for n in ('Strings', 'Items', 'Spells', 'MagicItems', 'Factions', 'Flats', 'Settings', 'Locations'):
        rows = apply('Internal_%s.csv' % n, d)
        hit = sum(1 for r in rows if r[1])
        print(n, hit, '/', len(rows))
