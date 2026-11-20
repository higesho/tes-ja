# 文章ファイルから訳す単位を抜き出す
#   translation/en/units.tsv : 番号<TAB>英文（全部）
#   translation/en/uniq.tsv  : uid<TAB>出どころ<TAB>英文（同じ英文は 1 つにまとめる）
#   translation/en/map.tsv   : 番号<TAB>uid
import os, sys, glob, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dftext

JP = os.path.join(HERE, '..')
A2 = dftext.A2
EN = os.path.join(JP, 'translation', 'en')

def all_units():
    """[(番号, 英文, 情報, 出どころ)]"""
    out = []
    sk, us = dftext.rsc_file_units(os.path.join(A2, 'TEXT.RSC'), 'rsc:')
    out += [(k, e, i, 'TEXT') for k, e, i in us]
    for f in sorted(glob.glob(os.path.join(A2, '*.QRC'))):
        nm = os.path.basename(f)[:-4]
        sk, us = dftext.rsc_file_units(f, 'q:%s:' % nm)
        out += [(k, e, i, nm) for k, e, i in us]
    for f in sorted(glob.glob(os.path.join(A2, 'books', '*.TXT'))):
        nm = os.path.basename(f)[:-4]
        sk, us = dftext.book_units(nm, open(f, 'rb').read())
        out += [(k, e, i, nm) for k, e, i in us]
    for f in sorted(glob.glob(os.path.join(A2, 'BIOG*.TXT'))):
        nm = os.path.basename(f)[:-4]
        fl, us = dftext.biog_units(nm, open(f, 'rb').read())
        out += [(k, e, i, nm) for k, e, i in us]
    return out

def clean(s):
    return s.replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')

if __name__ == '__main__':
    os.makedirs(EN, exist_ok=True)
    us = all_units()
    uniq, umap = {}, []
    order = []
    # 前に振った番号はそのまま使う（訳の組がずれないように）。新しい英文は続きの番号
    reg = {}
    regp = os.path.join(EN, 'registry.tsv')
    if os.path.exists(regp):
        for l in open(regp, encoding='utf-8'):
            uid, e = l.rstrip('\n').split('\t', 1); reg[e] = uid
    elif os.path.exists(os.path.join(EN, 'uniq.tsv')):
        for l in open(os.path.join(EN, 'uniq.tsv'), encoding='utf-8'):
            uid, src, kind, e = l.rstrip('\n').split('\t', 3); reg[e] = uid
    nxt = max([int(u[1:]) for u in reg.values()] + [-1]) + 1
    for k, e, i, src in us:
        e2 = clean(e)
        if not re.search(r'[A-Za-z]{2}', e2):
            continue          # 数字や記号だけのもの
        if e2 not in uniq:
            if e2 in reg:
                uid = reg[e2]
            else:
                uid = 'u%05d' % nxt; nxt += 1; reg[e2] = uid
            uniq[e2] = uid
            order.append((uid, src, e2, i))
        umap.append((k, uniq[e2]))
    with open(regp, 'w', encoding='utf-8') as f:
        for e, uid in sorted(reg.items(), key=lambda x: x[1]):
            f.write('%s\t%s\n' % (uid, e))
    with open(os.path.join(EN, 'units.tsv'), 'w', encoding='utf-8') as f:
        for k, e, i, src in us:
            f.write('%s\t%s\n' % (k, clean(e)))
    with open(os.path.join(EN, 'uniq.tsv'), 'w', encoding='utf-8') as f:
        for uid, src, e, i in order:
            f.write('%s\t%s\t%s\t%s\n' % (uid, src, 'q' if 'q' in i else ('1' if 'single' in i else ''), e))
    with open(os.path.join(EN, 'map.tsv'), 'w', encoding='utf-8') as f:
        for k, uid in umap:
            f.write('%s\t%s\n' % (k, uid))
    words = sum(len(re.findall(r'[A-Za-z]+', e)) for _, _, e, _ in order)
    print('単位', len(us), '異なる英文', len(order), '語数', words)
    by = {}
    for uid, src, e, i in order:
        t = 'TEXT' if src == 'TEXT' else 'BOOK' if src.startswith('BOK') else 'BIOG' if src.startswith('BIOG') else 'QRC'
        by.setdefault(t, [0, 0]); by[t][0] += 1; by[t][1] += len(re.findall(r'[A-Za-z]+', e))
    print(by)
