# 訳を集めて DLL のデータ（dll/dfjp.bin）を作る
#   python build.py        translation/out/*.tsv から
import os, sys, glob, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dftext, jpdata, extract

JP = os.path.join(HERE, '..')
T = os.path.join(JP, 'translation')
A2 = dftext.A2

def load_ja():
    """uid → 日本語"""
    d = {}
    for p in sorted(glob.glob(os.path.join(T, 'out', '*.tsv'))) + sorted(glob.glob(os.path.join(T, 'fix', '*.tsv'))):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if not l or l.startswith('#') or '\t' not in l:
                continue
            uid, j = l.split('\t', 1)
            j = j.strip()
            if j:
                d[uid.strip()] = j
    return d

MAC = re.compile(r'%[a-z][a-z0-9]*|[_=]{1,3}[A-Za-z][A-Za-z0-9]*_')

def _base(m):
    return m.strip('_=') if not m.startswith('%') else m

def fix_macros(en, j, allowed=()):
    """訳の中の記号のうち、原文（同じクエストのファイル全体 allowed）に無い名前のもの（綴りの書き換えなど）を
    原文の近い記号に直す。無ければ外す"""
    import difflib
    ems = MAC.findall(en)
    bases = {_base(m) for m in ems} | set(allowed)
    def rep(mo):
        m = mo.group()
        if m in ems or _base(m) in bases or re.fullmatch(r'%g(2self|[123])?', m):
            return m
        if m.startswith('%'):
            return m            # % の記号は全体共通なので残す
        cand = difflib.get_close_matches(_base(m), list(bases), n=1, cutoff=0.7)
        if cand:
            pre = re.match(r'[_=]+', m).group()
            return pre + cand[0] + '_'
        return ''
    return MAC.sub(rep, j)

def apply_fixes(uja):
    en = {}
    for l in open(os.path.join(T, 'en', 'uniq.tsv'), encoding='utf-8'):
        uid, src, kind, e = l.rstrip('\n').split('\t', 3)
        en[uid] = e
    # 番号 → 出てくるファイル、ファイル → そこに出てくる記号の名前
    files_of, bases_of = {}, {}
    for l in open(os.path.join(T, 'en', 'map.tsv'), encoding='utf-8'):
        k, uid = l.rstrip('\n').split('\t')
        f = k.split(':')[1] if k.startswith('q:') else k.split(':')[0]
        files_of.setdefault(uid, set()).add(f)
    for uid, fs in files_of.items():
        for f in fs:
            bases_of.setdefault(f, set()).update(_base(m) for m in MAC.findall(en.get(uid, '')))
    # 固有名詞の表記ゆれ（translation/unify.tsv）
    vari = []
    up = os.path.join(T, 'unify.tsv')
    if os.path.exists(up):
        for l in list(open(up, encoding='utf-8'))[1:]:
            f = l.rstrip('\n').split('\t')
            if len(f) >= 3:
                vari += [(v, f[1]) for v in f[2].split('｜') if v]
        vari.sort(key=lambda x: -len(x[0]))
    for uid, j in list(uja.items()):
        for v, c in vari:
            if v in j:
                j = j.replace(v, c)
        uja[uid] = j
    n = 0
    for uid, j in list(uja.items()):
        if uid in en:
            allowed = set()
            fs = files_of.get(uid, ())
            if fs and all(f not in ('rsc', 'b', 'g') for f in fs):
                allowed = set.intersection(*[bases_of[f] for f in fs])
            j2 = fix_macros(en[uid], j, allowed)
            if j2 != j:
                uja[uid] = j2; n += 1
    print('記号を直した訳', n)
    return uja

def key_ja(uja):
    """単位の番号 → 日本語"""
    d = {}
    for l in open(os.path.join(T, 'en', 'map.tsv'), encoding='utf-8'):
        k, uid = l.rstrip('\n').split('\t')
        if uid in uja:
            d[k] = uja[uid]
    # 単位ごとの上書き（同じ英語でも場所によって訳を変えたいもの。本の題の切れ端など）: translation/fix_keys.tsv
    p = os.path.join(T, 'fix_keys.tsv')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            l = l.rstrip('\n')
            if l and not l.startswith('#') and '\t' in l:
                k, j = l.split('\t', 1)
                d[k] = chr(0x3000) if j == '(空)' else j     # 空の行（全角の空白）
    return d

def main():
    uja = apply_fixes(load_ja())
    ja = key_ja(uja)
    en = {}
    for l in open(os.path.join(T, 'en', 'units.tsv'), encoding='utf-8'):
        k, e = l.rstrip('\n').split('\t', 1)
        en[k] = e
    files = {}
    # TEXT.RSC
    path = os.path.join(A2, 'TEXT.RSC')
    sk, us = dftext.rsc_file_units(path, 'rsc:')
    b = dftext.rsc_file_build(sk, 'rsc:', ja, en)
    if b != open(path, 'rb').read():
        files['ARENA2\\TEXT.RSC'] = b
    # クエスト
    for f in sorted(glob.glob(os.path.join(A2, '*.QRC'))):
        nm = os.path.basename(f)[:-4]
        sk, us = dftext.rsc_file_units(f, 'q:%s:' % nm)
        b = dftext.rsc_file_build(sk, 'q:%s:' % nm, ja, en)
        if b != open(f, 'rb').read():
            files['ARENA2\\%s.QRC' % nm] = b
    # 本
    for f in sorted(glob.glob(os.path.join(A2, 'books', '*.TXT'))):
        nm = os.path.basename(f)[:-4]
        if not any(k.startswith('b:%s:' % nm) for k in ja):
            continue
        sk, us = dftext.book_units(nm, open(f, 'rb').read())
        files['ARENA2\\BOOKS\\%s.TXT' % nm] = dftext.book_build(sk, ja, en, nm)
    # 経歴
    for f in sorted(glob.glob(os.path.join(A2, 'BIOG*.TXT'))):
        nm = os.path.basename(f)[:-4]
        fl, us = dftext.biog_units(nm, open(f, 'rb').read())
        b = dftext.biog_build(fl, ja, en)
        if b != open(f, 'rb').read():
            files['ARENA2\\%s.TXT' % nm] = b
    # 職業の設定（CLASSnn.CFG）の名前の欄（0x1C から 16 バイト）を、EXE の職業名の訳で書き換える
    exe_en = {}
    for l in open(os.path.join(T, 'en', 'exe.tsv'), encoding='utf-8'):
        eid, addr, k, s = l.rstrip('\n').split('\t', 3)
        if k == 'P' and eid in uja:
            exe_en.setdefault(s, uja[eid])
    # 原作のデータを丸ごと入れないよう、この 2 つは読み込むときの書き換え（PTCH）にする
    import struct
    patches = {}       # 名前 → [(位置, 中身)]
    for f in sorted(glob.glob(os.path.join(A2, 'CLASS*.CFG'))):
        b = open(f, 'rb').read()
        nm = b[0x1C:0x2C].split(b'\0')[0].decode('latin1')
        j = exe_en.get(nm)
        if j:
            g = dftext.to_game(j, hints=False)
            if len(g) <= 15:
                patches['ARENA2\\' + os.path.basename(f).upper()] = [(0x1C, g.ljust(16, b'\0'))]
    # 地名（MAPS.BSA）と人名の部品（NAMEGEN.DAT）。訳は Daggerfall Unity 側の translation/names と out/NG.tsv
    locn = bytearray()
    try:
        import names_dos
        tg = lambda j: dftext.to_game(j, hints=False)
        np_, miss, lg = names_dos.patches(tg)
        for k, v in np_.items():
            if v: patches[k] = v
        print('地名・人名の部品', {k: len(v) for k, v in np_.items()}, '訳なし', len(miss), '長すぎ', lg)
        # 旅の地図の「探す」で英語の地名を打ったときの置き換え表（LOCN: 英語\0 日本語\0 ...）
        for en, j in names_dos.location_ja().items():
            g = tg(j)
            if len(g) <= 31 and en.isascii():
                locn += en.encode('latin1') + b'\0' + g + b'\0'
        locn += b'\0'
    except FileNotFoundError as e:
        print('地名の訳なし', e)
    # 本文の字体（FONT0003）の高さを 7 → 8 にする（日本語の 8 ドットの字と影が次の行に重ならないよう、行の間を広げる）
    patches['ARENA2\\FONT0003.FNT'] = [(2, struct.pack('<H', 8))]
    ptch = bytearray()
    for name, ps in patches.items():
        body = bytearray()
        for off, data in ps:
            body += struct.pack('<II', off, len(data)) + data + b'\0' * ((-len(data)) % 4)
        ptch += name.encode().ljust(32, b'\0') + struct.pack('<I', len(body)) + body
    print('書き換えるファイル', len(patches))
    print('訳', len(uja), '単位', len(ja), '差し替えファイル', len(files))
    # EXE の文字列（e<番地> の訳）
    import exe_patch
    kinds = {}
    for l in open(os.path.join(T, 'en', 'exe.tsv'), encoding='utf-8'):
        eid, addr, k, s = l.rstrip('\n').split('\t', 3)
        kinds[eid] = (int(addr, 16), k)
    exe_ja = {}
    for eid, (a, k) in kinds.items():
        if eid in uja:
            exe_ja[a] = (k, uja[eid])
    extra = exe_patch.build(exe_ja) if exe_ja else []
    extra.append(('PTCH', bytes(ptch)))
    if len(locn) > 1:
        extra.append(('LOCN', bytes(locn)))
    # 絵の中の文字
    import imgpatch
    extra.append(('IMGP', imgpatch.build()))
    jpdata.build(files, os.path.join(JP, 'dll', 'dfjp.bin'), extra)

if __name__ == '__main__':
    main()
