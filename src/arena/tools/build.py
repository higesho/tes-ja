# 訳から ARENAJP 一式を組み立てる → test/arenajp/（DLL が読む形）
#   exe_ja.bin, dict.bin, data/（TEMPLATE.DAT POINTER1.DAT ARTFACT1.DAT … SPELLSG.65 SPELLS.LST）, inf/*.INF
import os, sys, re, glob, struct, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import *
import bsa

TR = os.path.join(WORK, 'translation')
CR, LF = chr(13), chr(10)
OUT = os.path.join(WORK, 'test', 'arenajp')

def load_ja():
    """translation/ja/*.tsv と translation/fix/*.tsv（手直し、後勝ち）を読む"""
    m = {}
    for d in ('ja', 'fix'):
        for p in sorted(glob.glob(os.path.join(TR, d, '*.tsv'))):
            for ln in open(p, encoding='utf-8', newline=''):
                ln = ln.rstrip('\r\n')
                if not ln or ln.startswith('#'): continue
                f = ln.split('\t')
                if len(f) >= 2 and f[1] != '': m[f[0]] = unesc(f[1])
    return m

def load_en(name):
    rows = []
    for ln in open(os.path.join(TR, 'en', name), encoding='utf-8', newline=''):
        f = ln.rstrip('\r\n').split('\t')
        rows.append(f)
    return rows

def euc(s):
    return enc(s)

# ---------- 折り返し（バイト数で、禁則つき） ----------
NOHEAD = set('、。，．・：；？！ー」』）】〉》…‥ぁぃぅぇぉっゃゅょァィゥェォッャュョ〜')
NOTAIL = set('「『（【〈《')

def tokens(s):
    """日本語は 1 字ずつ、英数字の語と空白はまとめて"""
    out = []
    for m in re.finditer(r'[ ]+|[\x21-\x7e]+|.', s):
        out.append(m.group())
    return out

def wrap(s, lim):
    lines, cur, w = [], '', 0
    toks = tokens(s)
    i = 0
    while i < len(toks):
        t = toks[i]
        tw = len(t.encode('euc_jp'))
        if t.isspace():
            if w == 0: i += 1; continue
            cur += t; w += tw; i += 1; continue
        need = tw
        if t in NOTAIL and i + 1 < len(toks): need += len(toks[i + 1].encode('euc_jp'))
        if w > 0 and w + need > lim and t not in NOHEAD:
            lines.append(cur.rstrip()); cur, w = '', 0
            continue
        cur += t; w += tw; i += 1
    if cur.strip(): lines.append(cur.rstrip())
    return lines

# ---------- exe ----------
def build_exe(ja):
    ents = []
    over = []
    for r in load_en('exe.tsv'):
        id_, en, lim = r[0], unesc(r[1]), int(r[2])
        if id_ not in ja: continue
        j = ja[id_]
        if j == en: continue
        try: b = euc(j)
        except UnicodeEncodeError: over.append((id_, 'EUC')); continue
        if len(b) > lim: over.append((id_, len(b), lim)); continue
        ents.append((int(id_[1:], 16), en.encode('latin1'), b))
    out = bytearray(b'ARJE' + struct.pack('<I', len(ents)))
    for off, e, j in ents:
        out += struct.pack('<IHH', off, len(e), len(j)) + e + j
    open(os.path.join(OUT, 'exe_ja.bin'), 'wb').write(out)
    return len(ents), over

# ---------- 描画辞書 ----------
def build_dict():
    ents = {}
    for ln in open(os.path.join(TR, 'glossary.tsv'), encoding='utf-8'):
        if ln.startswith('#') or not ln.strip(): continue
        f = ln.rstrip('\n').split('\t')
        if len(f) >= 3 and f[2] == 'dict': ents[f[0]] = f[1]
    # 町と村の名前、部品から作られる人の名前（translation/names/）
    import glob
    for f in [os.path.join(TR, 'names', 'towns.tsv')] + sorted(glob.glob(os.path.join(TR, 'names', 'ja_*.tsv'))) + \
             [os.path.join(TR, 'names', 'gen_monster.tsv')]:
        for ln in open(f, encoding='utf-8'):
            if ln.startswith('#') or '\t' not in ln: continue
            a = ln.rstrip('\r\n').split('\t')
            if a[0] and a[1] and a[0] not in ents: ents[a[0]] = a[1]
    extra = os.path.join(TR, 'dict_extra.tsv')
    if os.path.exists(extra):
        for ln in open(extra, encoding='utf-8'):
            if ln.startswith('#') or not ln.strip(): continue
            f = ln.rstrip('\n').split('\t')
            if len(f) >= 2: ents[f[0]] = f[1]
    items = sorted(ents.items(), key=lambda kv: -len(kv[0]))
    out = bytearray(b'ARJD' + struct.pack('<I', len(items)))
    for en, j in items:
        e, b = en.encode('latin1'), euc(j)
        out += bytes([len(e), len(b)]) + e + b
    open(os.path.join(OUT, 'dict.bin'), 'wb').write(out)
    return len(items)

def build_names():
    """names.bin: "ARJN" u32 前半の数, u32 後半の数, {u8 英長, u8 日長, 英, 日}*（前半、後半の順）
    ハンマーフェルの名前は前半（子音＋母音）と後半の組み合わせが多すぎるので、DLL が 2 つの表を組み合わせて引く"""
    tabs = []
    for nm in ('gen_r1_head.tsv', 'gen_r1_tail.tsv'):
        t = []
        for ln in open(os.path.join(TR, 'names', nm), encoding='utf-8'):
            if ln.startswith('#') or '\t' not in ln: continue
            a = ln.rstrip('\r\n').split('\t'); t.append((a[0], a[1]))
        tabs.append(t)
    out = bytearray(b'ARJN' + struct.pack('<II', len(tabs[0]), len(tabs[1])))
    for t in tabs:
        for en, j in t:
            e, b = en.encode('latin1'), euc(j)
            out += bytes([len(e), len(b)]) + e + b
    open(os.path.join(OUT, 'names.bin'), 'wb').write(out)
    return sum(len(t) for t in tabs)

# ---------- TEMPLATE.DAT と POINTER1.DAT ----------
def build_template(ja):
    ents = template_parse(read_game('TEMPLATE.DAT'))
    out = []
    n = 0
    for i, (keyline, vars_, amp) in enumerate(ents):
        out.append(keyline + '\r\n')
        for j, v in enumerate(vars_):
            s = ja.get(f't{i:03d}:{j}')
            if s is None: s = v
            else: n += 1
            out.append(s + ('&\r\n\r\n' if amp else '\r\n\r\n'))
    data = ''.join(out).encode('euc_jp')
    open(os.path.join(OUT, 'data', 'TEMPLATE.DAT'), 'wb').write(data)
    # POINTER1.DAT は DLL が起動時に作り直す（見出しの数が合うことだけ確かめる）
    heads = [m.start() for m in re.finditer(rb'(?m)^#', data)]
    assert len(heads) == len(ents)
    return n, len(data), len(read_game('TEMPLATE.DAT'))

# ---------- NUL 区切りの DAT ----------
def build_nul(ja):
    res = []
    for name, pre in [('ARTFACT1.DAT', 'a1_'), ('ARTFACT2.DAT', 'a2_'), ('EQUIP.DAT', 'eq_'),
                      ('MUGUILD.DAT', 'mg_'), ('SELLING.DAT', 'se_'), ('TAVERN.DAT', 'tv_')]:
        items = nul_parse(read_game(name))
        outs = []
        n = 0
        for i, s in enumerate(items):
            j = ja.get(f'{pre}{i:03d}')
            if j is None: outs.append(s); continue
            maxl = max((len(x) for x in s.split('\n')), default=40)
            lim = max(30, min(58, maxl))
            outs.append('\n'.join(wrap(j.replace('\n', ''), lim))); n += 1
        data = '\0'.join(outs).encode('euc_jp')
        open(os.path.join(OUT, 'data', name), 'wb').write(data)
        res.append((name, n, len(data), len(read_game(name))))
    return res

# ---------- DUNGEON / SPELLMKR / QUESTION ----------
def build_misc(ja):
    # DUNGEON.TXT
    ents = dungeon_parse(read_game('DUNGEON.TXT'))
    parts = []
    for i, e in enumerate(ents):
        if not e: parts.append(''); continue
        name = ja.get(f'dn{i}', e[0]); desc = ja.get(f'dd{i}', e[1])
        lines = wrap(desc, 58) if f'dd{i}' in ja else wrap(desc, 72)
        parts.append(name + '\r\n' + '\r\n'.join(lines) + '\r\n')
    open(os.path.join(OUT, 'data', 'DUNGEON.TXT'), 'wb').write('#\r\n'.join(parts).encode('euc_jp'))
    # SPELLMKR.TXT
    out = []
    for k, s in spellmkr_parse(read_game('SPELLMKR.TXT')):
        j = ja.get(f'sm{k}', s)
        out.append('#' + k + '\r\n' + '\r\n'.join(wrap(j, 56)) + '\r\n')
    open(os.path.join(OUT, 'data', 'SPELLMKR.TXT'), 'wb').write(''.join(out).encode('euc_jp'))
    # QUESTION.TXT
    out = []
    for num, q, ans in question_parse(read_game('QUESTION.TXT')):
        n = int(num)
        qj = ja.get(f'q{n:02d}', q)
        ql = wrap(qj, 56)
        out.append(f'{num}.   ' + ql[0] + ' \n' + ''.join('   ' + x + ' \n' for x in ql[1:]))
        for k, s, mark in ans:
            aj = ja.get(f'q{n:02d}{k}', s)
            al = wrap(aj + (f' ({mark})' if mark else ''), 56)
            out.append(f'{k}) ' + al[0] + ' \n' + ''.join('   ' + x + ' \n' for x in al[1:]))
    open(os.path.join(OUT, 'data', 'QUESTION.TXT'), 'wb').write(''.join(out).encode('euc_jp'))

# ---------- SPELLSG.65 / SPELLS.LST ----------
def build_spells(ja):
    """spells.bin: "ARJS" u32 件数, {u16 番号, u8 長さ, 名前}*（DLL が原作の SPELLSG.65 に当てる）"""
    d = read_game('SPELLSG.65')
    ents = []
    for i in range(len(d) // 85):
        j = ja.get(f'sg_{i:03d}')
        if j: ents.append((i, euc(j)[:32]))
    out = bytearray(b'ARJS' + struct.pack('<I', len(ents)))
    for i, b in ents: out += struct.pack('<HB', i, len(b)) + b
    open(os.path.join(OUT, 'spells.bin'), 'wb').write(out)
    return len(ents)

# ---------- INF（GLOBAL.BSA の中） ----------
def build_inf(ja):
    """inf.bin: "ARJI" u32 件数, {名前[13], u16 番号, u16 長さ, 文}*（DLL が GLOBAL.BSA の INF の *TEXT に当てる）"""
    ents = []
    for k, v in ja.items():
        if not k.startswith('i_'): continue
        name, num = k[2:].split('#')
        body = v.replace(CR + LF, LF).replace(LF, CR + LF)
        ents.append((name, int(num), euc(body)))
    ents.sort()
    out = bytearray(b'ARJI' + struct.pack('<I', len(ents)))
    for name, num, b in ents:
        out += name.encode('ascii').ljust(13, bytes(1)) + struct.pack('<HH', num, len(b)) + b
    open(os.path.join(OUT, 'inf.bin'), 'wb').write(out)
    return len(ents)

if __name__ == '__main__':
    if os.path.exists(OUT + '/data'): shutil.rmtree(OUT + '/data')
    if os.path.exists(OUT + '/inf'): shutil.rmtree(OUT + '/inf')
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    ja = load_ja()
    print('訳', len(ja))
    ne, over = build_exe(ja)
    print('exe', ne, '枠超え', len(over))
    for o in over[:20]: print('  ', o)
    print('辞書', build_dict())
    print('名前の表', build_names())
    print('template', build_template(ja))
    for r in build_nul(ja): print('dat', r)
    build_misc(ja)
    print('spells', build_spells(ja))
    print('inf', build_inf(ja))
