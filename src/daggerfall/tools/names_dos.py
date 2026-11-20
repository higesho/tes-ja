# 地名・人名の部品の訳（DaggerfallUnity/jp_work/translation/names・out/NG.tsv）を、DOS 版の読み込み時の書き換え（PTCH）にする
#   MAPS.BSA: 地域ごとの MAPNAMES（32 バイトの欄）と、場所の記録（MAPPITEM・MAPDITEM）の中の同じ名前の欄
#   NAMEGEN.DAT: 名前の部品（10 バイトの欄）
import os, sys, struct, glob, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
A2 = os.path.join(HERE, '..', '..', 'arena2')
DFU_T = os.path.join(HERE, '..', '..', '..', 'DaggerfallUnity', 'jp_work', 'translation')

def location_ja():
    """英語の地名 → 日本語"""
    idx = {}
    p = os.path.join(DFU_T, 'names', 'index.tsv')
    for l in open(p, encoding='utf-8'):
        u, e = l.rstrip('\n').split('\t', 1); idx[u] = e
    d = {}
    for p in sorted(glob.glob(os.path.join(DFU_T, 'names', 'out', 'L*.tsv'))) + sorted(glob.glob(os.path.join(DFU_T, 'names', 'fix', '*.tsv'))):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if '\t' not in l or l.startswith('#'): continue
            u, j = l.split('\t', 1); j = j.strip()
            if u in idx and j: d[idx[u]] = j
    # 英語で引く上書き（DFU の地名の表に無いもの）
    p = os.path.join(DFU_T, 'names', 'fix_en.tsv')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if '\t' in l and not l.startswith('#'):
                e, j = l.split('\t', 1); d[e] = j.strip()
    return d

def part_ja():
    """(種族, 部品) → 日本語。DFU の NameGen.txt の種族名で"""
    d = {}
    for p in [os.path.join(DFU_T, 'out', 'NG.tsv'), os.path.join(DFU_T, 'out', 'NG2.tsv')]:
        if not os.path.exists(p): continue
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if not l.startswith('NG:') or '\t' not in l: continue
            u, j = l.split('\t', 1)
            _, race, si, part = u.split(':', 3)
            d.setdefault((race, part), j.strip())
            d[(race, int(si), part)] = j.strip()
    return d

# DOS の NAMEGEN.DAT の銀行の順（DFU の種族名）
BANKS = ['Breton', 'Redguard', 'Nord', 'DarkElf', 'HighElf', 'WoodElf', 'Khajiit', 'Imperial', 'Monster1', 'Monster2', 'Monster3']

def namegen_parts():
    """[(銀行, 組, 位置, 部品)]"""
    b = open(os.path.join(A2, 'NAMEGEN.DAT'), 'rb').read()
    out = []
    for bank in range(11):
        offs = struct.unpack_from('<6I', b, bank * 48); cnt = struct.unpack_from('<6I', b, bank * 48 + 24)
        for si, (o, c) in enumerate(zip(offs, cnt)):
            for i in range(c):
                p = o + i * 10
                out.append((bank, si, p, b[p:p + 10].split(b'\0')[0].decode('latin1')))
    return out

def patches(to_game):
    """{ファイル名: [(位置, 中身)]}、足りない訳の一覧"""
    res = {}; missing = []
    # 人名の部品
    pj = part_ja()
    ng = []
    for bank, si, pos, part in namegen_parts():
        race = BANKS[bank]
        j = pj.get((race, si, part)) or pj.get((race, part))
        if not j:
            missing.append(('part', race, si, part)); continue
        g = to_game(j)
        if len(g) > 9:
            missing.append(('long', race, si, part, j)); continue
        ng.append((pos, g.ljust(10, b'\0')))
    res['ARENA2\\NAMEGEN.DAT'] = ng
    # 地名
    lj = location_ja()
    b = open(os.path.join(A2, 'MAPS.BSA'), 'rb').read()
    n = struct.unpack_from('<h', b, 0)[0]
    d = len(b) - n * 18
    ents = []; off = 4
    for i in range(n):
        nm = b[d + i * 18:d + i * 18 + 12].split(b'\0')[0].decode('latin1')
        sz = struct.unpack_from('<i', b, d + i * 18 + 14)[0]
        ents.append((nm, off, sz)); off += sz
    by = {nm: (o, s) for nm, o, s in ents}
    mp = []; done = set(); long_ = 0
    for nm, o, s in ents:
        if not nm.startswith('MAPNAMES'): continue
        reg = nm.split('.')[1]
        cnt = struct.unpack_from('<I', b, o)[0]
        names = [b[o + 4 + i * 32:o + 4 + i * 32 + 32].split(b'\0')[0] for i in range(cnt)]
        enc = {}
        for i, en in enumerate(names):
            e = en.decode('latin1'); j = lj.get(e)
            if not j:
                missing.append(('loc', e)); continue
            g = to_game(j)
            if len(g) > 31:
                long_ += 1; continue
            enc[en] = g
            mp.append((o + 4 + i * 32, g.ljust(32, b'\0')))
        # 同じ地域の場所の記録の中の、同じ名前の欄（名前＋0 が 32 バイトの欄の頭にあるもの）
        for kind in ('MAPPITEM', 'MAPDITEM'):
            ro, rs = by['%s.%s' % (kind, reg)]
            rec = b[ro:ro + rs]
            for en, g in enc.items():
                for m in re.finditer(re.escape(en + b'\0'), rec):
                    p = m.start()
                    if p > 0 and 0x20 < rec[p - 1] < 0x7f: continue      # 別の文字列の途中
                    if (ro + p) in done: continue
                    done.add(ro + p)
                    mp.append((ro + p, g + b'\0'))
    res['ARENA2\\MAPS.BSA'] = mp
    return res, missing, long_

if __name__ == '__main__':
    import jpdata
    r, miss, lg = patches(jpdata.to_game)
    for k, v in r.items(): print(k, len(v))
    print('足りない', len(miss), miss[:10], '長すぎ', lg)
