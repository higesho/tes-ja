# Daggerfall Unity 用の日本語化ファイルを作る
#   DOS 版の日本語化（Daggerfall/jp_work）の build.py をそのまま動かし、出来た差し替えファイル（ゲームの 2 バイト字）を
#   Unicode に戻して、DFU の書き方（CSV・クエスト・本）に直す
#   python dfu_build.py     → out/StreamingAssets/...
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
DFJP = os.path.join(HERE, '..', '..', '..', 'Daggerfall', 'jp_work', 'tools')
sys.path.insert(0, HERE); sys.path.insert(0, DFJP)
import dfumark
OUT = os.path.join(HERE, '..', 'out', 'StreamingAssets')

def dos_files():
    """DOS 版の build.py を動かし、差し替えファイルと EXE の訳を受け取る"""
    import jpdata, build
    got = {}
    def cap(files, out, extra=()):
        got['files'] = files; got['extra'] = extra
    jpdata.build = cap
    build.jpdata.build = cap
    build.main()
    return got['files'], jpdata.CMAP

def decoder(cmap):
    chars = []
    for code in cmap:
        try: chars.append(bytes([code >> 8, code & 0xff]).decode('euc_jp'))
        except UnicodeDecodeError: chars.append('?')
    def dec(b):
        out = []; i = 0
        while i < len(b):
            c = b[i]
            if 0x80 <= c <= 0xAF and i + 1 < len(b) and 0xB0 <= b[i + 1] <= 0xEF:
                out.append(chars[(c - 0x80) * 64 + (b[i + 1] - 0xB0)]); i += 2; continue
            if c == 0x1F:
                i += 1; continue           # 折り返しの目印（幅 0）
            out.append(chr(c)); i += 1
        return ''.join(out)
    return dec

def build_rsc(files, dec, newja=None):
    import rsc, cmp_rsc
    data = files.get('ARENA2\\TEXT.RSC')
    recs = dict(rsc.load(data))
    d = cmp_rsc.keyed(recs, lambda b: dfumark.to_markup(b, dec))
    # DFU のコードが行の形を決めてかかっている記録などの上書き（translation/fix の 'RSC:キー'）
    for k, v in (newja or {}).items():
        if k.startswith('RSC:'): d[k[4:]] = v
    rows = []; n = 0
    for k, v in dfumark.read_csv('Internal_RSC.csv'):
        if k in d and d[k] != v.replace('\r', '') and any(ord(ch) > 0x2000 for ch in d[k]):
            rows.append((k, d[k])); n += 1
        else:
            rows.append((k, v))
    os.makedirs(os.path.join(OUT, 'Text'), exist_ok=True)
    dfumark.write_csv(os.path.join(OUT, 'Text', 'Internal_RSC.csv'), rows)
    print('RSC', n, '/', len(rows))

def book_text(b, dec):
    """本の頁（0x00 改行・0xF9 字体・0xFD 中寄せ・0xF6 頁の終わり）→ DFU の本文"""
    out = []; text = bytearray(); i = 0
    def flush():
        if text:
            out.append(dec(bytes(text))); text.clear()
    while i < len(b):
        c = b[i]
        if c == 0x00: flush(); out.append('\n'); i += 1
        elif c == 0xF9: flush(); out.append('[/font=%d]' % b[i + 1]); i += 2
        elif c == 0xFD: flush(); out.append('[/center]'); i += 1
        elif c == 0xF6: flush(); i += 1
        else: text.append(c); i += 1
    flush()
    return ''.join(out)

def build_books(files, dec):
    import dftext
    src = os.path.join(dfumark.DFU, 'Text', 'Books')
    dst = os.path.join(OUT, 'Text', 'Books'); os.makedirs(dst, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('-LOC.txt'): continue
        key = 'ARENA2\\BOOKS\\%s.TXT' % fn[:-8]
        if key not in files: continue
        bb = files[key]
        # 組み立てた本は頁の数が 0xE8、位置の表が 0xEA から（book_save の書き方）
        np_ = struct.unpack_from('<H', bb, 0xE8)[0]
        offs = struct.unpack_from('<%dI' % np_, bb, 0xEA)
        title = bb[:64].split(b'\0')[0]; author = bb[64:128].split(b'\0')[0]
        pages = [bb[offs[i]:(offs[i + 1] if i + 1 < np_ else len(bb))] for i in range(np_)]
        head = open(os.path.join(src, fn), encoding='utf-8').read().split('Content:')[0]
        lines = []
        for l in head.split('\n'):
            if l.startswith('Title:'): l = 'Title: ' + dec(title)
            elif l.startswith('Author:'): l = 'Author: ' + dec(author)
            lines.append(l)
        body = ''.join(book_text(p, dec) for p in pages)
        open(os.path.join(dst, fn), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + 'Content:\n' + body)
        n += 1
    print('本', n)

def qrc_text(b, dec):
    """クエストの記録 → DFU のクエスト文（0xFD の行は <ce>、0xFC は左寄せ、0xFF は <--->）"""
    out = []; text = bytearray(); i = 0
    def line(ce):
        t = dec(bytes(text)); text.clear()
        out.append(('<ce>' + t) if ce else t)
    while i < len(b):
        c = b[i]
        if c == 0xFE: break
        if c == 0xFD: line(True)
        elif c == 0xFC: line(False)
        elif c == 0xFF:
            if text: line(False)
            out.append('                                     <--->')
        else: text.append(c)
        i += 1
    if text: line(False)
    return out

QNAMES = {}

def build_quests(files, dec):
    import rsc, re
    src = os.path.join(dfumark.DFU, 'Quests')
    dst = os.path.join(OUT, 'Text', 'Quests'); os.makedirs(dst, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(src)):
        q = fn[:-4]
        key = 'ARENA2\\%s.QRC' % q.upper()
        if key not in files: continue
        recs = dict(rsc.load(files[key]))
        s = open(os.path.join(src, fn), encoding='utf-8', errors='replace').read().replace('\r', '')
        dn = re.search(r'^DisplayName:\s*(.*)$', s, re.M)
        qrc = s.split('\nQRC:', 1)[1].split('\nQBN:', 1)[0]
        name = QNAMES.get(q) or (dn.group(1).strip() if dn else q)
        out = ['Quest: %s' % q, 'DisplayName: %s' % name, 'QRC:', '']
        for m in re.finditer(r'^(\w+):\s+\[?(\d+)\]?\s*$', qrc, re.M):
            mid = int(m.group(2))
            if mid not in recs: continue
            out.append(m.group(0).rstrip())
            out += qrc_text(recs[mid], dec)
            out.append('')
        open(os.path.join(dst, q + '-LOC.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
        n += 1
    print('クエスト', n)

def load_new_ja():
    """translation/out/*.tsv（訳）と fix/*.tsv（手直し、後勝ち）: '表:キー' → 日本語"""
    import glob
    d = {}
    T = os.path.join(HERE, '..', 'translation')
    for p in sorted(glob.glob(os.path.join(T, 'out', '*.tsv'))) + sorted(glob.glob(os.path.join(T, 'fix', '*.tsv'))):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if not l or l.startswith('#') or '\t' not in l: continue
            uid, j = l.split('\t', 1)
            j = j.strip().replace(chr(92) + 'n', '\n')
            if j: d[uid.strip()] = j
    return d

TABLES = ('Strings', 'Settings', 'Spells', 'MagicItems', 'Factions', 'Flats', 'Items')

def build_tables(newja):
    import dfu_dict
    d = dfu_dict.en_ja()
    for n in TABLES:
        extra = {k.split(':', 1)[1]: v for k, v in newja.items() if k.startswith(n + ':')}
        rows = []; hit = 0
        for k, j, v in dfu_dict.apply('Internal_%s.csv' % n, d, extra):
            if j and v.count('\n') != j.count('\n') and n == 'Settings':
                j = None                  # 選択肢の並びは行の数を合わせる
            rows.append((k, j or v)); hit += bool(j)
        dfumark.write_csv(os.path.join(OUT, 'Text', 'Internal_%s.csv' % n), rows)
        print(n, hit, '/', len(rows))
    return newja

def build_names(newja):
    """人名の部品（NameGen.txt）と地名（Internal_Locations.csv）"""
    import namegen, glob
    tr = {}
    for k, v in newja.items():
        if k.startswith('NG:'):
            _, race, si, part = k.split(':', 3)
            tr[(race, int(si), part)] = v
    namegen.write(os.path.join(OUT, 'Text', 'NameGen.txt'), tr)
    T = os.path.join(HERE, '..', 'translation', 'names')
    idx = dict(l.rstrip('\n').split('\t', 1) for l in open(os.path.join(T, 'index.tsv'), encoding='utf-8'))
    lj = {}
    for p in sorted(glob.glob(os.path.join(T, 'out', 'L*.tsv'))) + sorted(glob.glob(os.path.join(T, 'fix', '*.tsv'))):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if '\t' in l and not l.startswith('#'):
                u, j = l.split('\t', 1)
                if u in idx and j.strip(): lj[idx[u]] = j.strip()
    rows = []; hit = 0
    for k, v in dfumark.read_csv('Internal_Locations.csv'):
        j = lj.get(v)
        rows.append((k, j or v)); hit += bool(j)
    dfumark.write_csv(os.path.join(OUT, 'Text', 'Internal_Locations.csv'), rows)
    print('人名の部品', len(tr), '地名', hit, '/', len(rows))

def main():
    newja = load_new_ja()
    build_names(newja)
    build_tables(newja)
    QNAMES.update({k.split(':', 1)[1]: v for k, v in newja.items() if k.startswith('QuestNames:')})
    files, cmap = dos_files()
    dec = decoder(cmap)
    build_rsc(files, dec, newja)
    build_books(files, dec)
    build_quests(files, dec)

if __name__ == '__main__':
    main()
