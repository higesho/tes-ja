# 訳（translation/out/*.tsv）の検査
#   行の抜け・差し込み記号の食い違い・EUC-JP に無い字・用語集の訳語・短いものの長さ
#   python check_ja.py [組の名前...]
import os, re, sys, glob, csv
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
T = os.path.join(HERE, '..', 'translation')
import dftext

PRON = re.compile(r'%g(?:2self|[123])?(?![a-z0-9])')
MAC = re.compile(r'%[a-z][a-z0-9]*|[_=]{1,3}[A-Za-z][A-Za-z0-9]*_')

def macros(s):
    return sorted(m for m in MAC.findall(s) if not PRON.fullmatch(m))

def load_gloss():
    g = []
    for r in csv.DictReader(open(os.path.join(T, 'glossary.tsv'), encoding='utf-8'), delimiter='\t'):
        if r['en'] and r['ja'] and r['種別'] not in ('素材',) and r['en'] not in ('Imperial', 'Septim', 'Daedra', 'Health', 'Emperor', 'Battlemage', 'Orc'):
            g.append((r['en'], r['ja']))
    return g

def check(name, gloss, verbose=True):
    src = os.path.join(T, 'work', name + '.tsv')
    out = os.path.join(T, 'out', name + '.tsv')
    rows = list(csv.reader(open(src, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))[1:]
    if not os.path.exists(out):
        return ['出力が無い']
    ja = {}
    probs = []
    for l in open(out, encoding='utf-8'):
        l = l.rstrip('\n')
        if not l or l.startswith('#'):
            continue
        if '\t' not in l:
            probs.append('形が変: ' + l[:60]); continue
        uid, j = l.split('\t', 1)
        uid = uid.strip()
        if '\t' in j:
            probs.append('%s: タブが入っている' % uid)
        ja[uid] = j.strip()
    for uid, srcn, kind, en in rows:
        j = ja.get(uid)
        if j is None:
            probs.append('%s: 訳が無い' % uid); continue
        if macros(en) != macros(j):
            probs.append('%s: 記号 %s → %s' % (uid, macros(en), macros(j)))
        if PRON.search(j):
            probs.append('%s: 代名詞の記号が残っている' % uid)
        bad = []
        for ch in j:
            if ord(ch) >= 0x80 and ch not in dftext.jpdata.REP:
                try:
                    if len(ch.encode('euc_jp')) != 2: bad.append(ch)
                except UnicodeEncodeError:
                    bad.append(ch)
        if bad:
            probs.append('%s: EUC に無い字 %s' % (uid, ''.join(sorted(set(bad)))))
        rest = re.sub(MAC, '', j)
        if not re.search(r'[぀-ヿ一-鿿]', rest) and re.search(r'[a-z]{3}', rest):
            probs.append('%s: 英語のまま? %s' % (uid, j[:60]))
        if kind == '1' and dftext.ja_width(j) > max(dftext.en_width(en.encode('latin1', 'replace')) * 1.3, 40):
            probs.append('%s: 短いものが長い（%s → %s）' % (uid, en[:40], j[:30]))
        for ge, gj in gloss:
            if re.search(r'\b%s\b' % re.escape(ge), en) and gj not in j and len(ge) > 3:
                probs.append('%s: 用語 %s → %s が無い' % (uid, ge, gj))
                break
    extra = set(ja) - {r[0] for r in rows}
    if extra:
        probs.append('余分な番号 %d 件' % len(extra))
    return probs

if __name__ == '__main__':
    gloss = load_gloss()
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(T, 'out', '*.tsv')))
    for n in names:
        p = check(n, gloss)
        kinds = {}
        for x in p:
            k = re.sub(r'^u\d+: ', '', x).split(' ')[0]
            kinds[k] = kinds.get(k, 0) + 1
        print('%s: %d 件 %s' % (n, len(p), kinds))
        if '-v' in os.environ.get('CHK', ''):
            for x in p[:40]: print('   ', x)
