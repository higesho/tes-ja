# 試験: 元の TEXT.RSC を DFU の書き方にして、Internal_RSC.csv（英語）と比べる
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'Daggerfall', 'jp_work', 'tools'))
import dfumark, rsc
A2 = os.path.join(HERE, '..', '..', '..', 'Daggerfall', 'arena2')

def records():
    return dict(rsc.load(open(os.path.join(A2, 'TEXT.RSC'), 'rb').read()))

def keyed(recs, conv):
    """id → DFU の書き方（[/record] で分かれる記録は id.n にも分ける）"""
    d = {}
    for rid, b in recs.items():
        m = conv(b)
        d[str(rid)] = m
        if '[/record]' in m:
            for n, part in enumerate(m.split('[/record]\n')):
                d['%d.%d' % (rid, n)] = part
    return d

if __name__ == '__main__':
    d = keyed(records(), dfumark.to_markup)
    m = dfumark.read_csv('Internal_RSC.csv')
    ok = bad = miss = 0; shown = 0
    for k, v in m:
        if k not in d: miss += 1; continue
        if d[k] == v.replace('\r', ''): ok += 1
        else:
            bad += 1
            if shown < int(sys.argv[1] if len(sys.argv) > 1 else 5):
                shown += 1
                a, b = v.replace('\r', ''), d[k]
                j = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
                print('ID', k, 'at', j); print('  dfu ', repr(a[max(0, j - 40):j + 60])); print('  mine', repr(b[max(0, j - 40):j + 60]))
    print('一致', ok, '違う', bad, 'なし', miss, '/', len(m))
