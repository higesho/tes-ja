# 訳の検査: python tools/check_ja.py [組の名前 ...]（省略で全部）
# 見ること: id のそろい、変数（%xx）の数と順、EUC-JP で表せるか、exe の枠、変数の直後の英数字、使えない字
import os, sys, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import WORK, unesc

BD = os.path.join(WORK, 'translation', 'batches')
JA = os.path.join(WORK, 'translation', 'ja')
VAR = re.compile(r'%(?:%|[-0-9.]*l?[sducxX]|[a-z]{1,4}[0-9]?|[0-9])')
PRINTF = re.compile(r'%(?:%|[-0-9.]*l?[sducxX])')

def load(path, ncol=None):
    rows = []
    for ln in open(path, encoding='utf-8', newline=''):
        ln = ln.rstrip('\r\n')
        if not ln: continue
        rows.append(ln.split('\t'))
    return rows

def vars_of(s):
    return VAR.findall(s)

def check(name):
    src = load(os.path.join(BD, name))
    outp = os.path.join(JA, name)
    if not os.path.exists(outp):
        return [f'{name}: 訳のファイルがない']
    out = load(outp)
    errs = []
    om = {}
    for r in out:
        if len(r) < 2: errs.append(f'{name}: 列が足りない: {r[0][:40]}'); continue
        om[r[0]] = r[1]
    for r in src:
        id_, en = r[0], unesc(r[1])
        if id_ not in om: errs.append(f'{id_}: 訳がない'); continue
        ja = unesc(om[id_])
        try:
            b = ja.encode('euc_jp')
        except UnicodeEncodeError as e:
            errs.append(f'{id_}: EUC-JP にない字 {ja[e.start:e.end]!r}'); continue
        ev, jv = vars_of(en), vars_of(ja)
        if sorted(ev) != sorted(jv):
            errs.append(f'{id_}: 変数が違う 英{ev} 訳{jv}')
        elif PRINTF.findall(en) != PRINTF.findall(ja):
            errs.append(f'{id_}: 書式（%s %d など）の順が違う 英{PRINTF.findall(en)} 訳{PRINTF.findall(ja)}')
        if re.search(r'%[a-z]{1,4}[0-9]?[A-Za-z0-9]', ja.replace('%%', '')) and not re.search(r'%[a-z]{1,4}[0-9]?[A-Za-z0-9]', en.replace('%%', '')):
            m = re.search(r'%[a-z]{1,4}[0-9]?[A-Za-z0-9]', ja)
            errs.append(f'{id_}: 変数の直後に英数字 {m.group()!r}')
        if len(r) >= 3 and r[2].isdigit():
            lim = int(r[2])
            if len(b) > lim: errs.append(f'{id_}: 枠 {lim} バイトを超える（{len(b)} バイト）: {ja}')
        if re.search(r'[ぁ-んァ-ン一-龥] [ぁ-んァ-ン一-龥]', ja):
            errs.append(f'{id_}: 日本語の間に空白')
        if en.startswith('\t') and not ja.startswith(en[:2] if en[1:2] != '2' and en[1:2] != '0' and en[1:2] != '1' else en[:4]):
            errs.append(f'{id_}: 行頭の \\t 指定が変わった')
    for id_ in om:
        if id_ not in {r[0] for r in src}: errs.append(f'{id_}: 元にない id')
    return errs

if __name__ == '__main__':
    names = sys.argv[1:] or sorted(os.path.basename(p) for p in glob.glob(os.path.join(BD, '*.tsv')))
    total = 0
    for n in names:
        if not n.endswith('.tsv'): n += '.tsv'
        e = check(n)
        total += len(e)
        for x in e: print(x)
    print('問題', total)
