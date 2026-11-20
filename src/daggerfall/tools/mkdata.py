# DLL に埋め込むデータ（dll/lol2jp.bin）を作る
#   フォント FN08/FN12/FN14/FN16、差し替えるファイル LOOS/MIXP、字幕 SUBF/SUBE/SUBS/SUBT
import os, sys, struct, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
JP = os.path.join(HERE, '..')
FONT = os.path.join(JP, 'font')
GAME = os.path.join(JP, '..')

def load_bdf(path):
    """{encoding: (bbx, rows[int])}, fbb"""
    g = {}
    lines = open(path, encoding='latin1').read().split('\n')
    fbb = None
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith('FONTBOUNDINGBOX'):
            fbb = list(map(int, l.split()[1:]))
        if l.startswith('STARTCHAR'):
            enc = None; bbx = None; bm = []; dw = None
            while not lines[i].startswith('ENDCHAR'):
                t = lines[i]
                if t.startswith('ENCODING'): enc = int(t.split()[1])
                elif t.startswith('DWIDTH'): dw = int(t.split()[1])
                elif t.startswith('BBX'): bbx = list(map(int, t.split()[1:]))
                elif t.startswith('BITMAP'):
                    i += 1
                    while not lines[i].startswith('ENDCHAR'):
                        bm.append(lines[i].strip()); i += 1
                    break
                i += 1
            g[enc] = (bbx, bm, dw)
        i += 1
    return g, fbb

def to_rows(entry, fbb, size, bits):
    """字形を 上から size 行、左詰め bits ビット の整数列に"""
    bbx, bm, dw = entry
    w, h, ox, oy = bbx
    rows = [0] * size
    top = (fbb[1] + fbb[3]) - (h + oy)
    for r, hx in enumerate(bm):
        v = int(hx, 16)
        nb = len(hx) * 4
        y = top + r
        if 0 <= y < size:
            v = (v << bits) >> nb          # 左詰め bits ビットへ
            rows[y] = (v >> max(ox, 0)) & ((1 << bits) - 1)   # 字の枠の x のずれ
    return rows

def font_sec(full_bdf, half_bdf, size, fw, hw, full_enc):
    """full_enc: 'jis' か 'unicode'"""
    gf, ff = load_bdf(os.path.join(FONT, full_bdf))
    gh, fh = load_bdf(os.path.join(FONT, half_bdf)) if half_bdf else (gf, ff)
    out = bytearray([size, fw, hw, 0])
    n = 0
    for ku in range(94):
        for ten in range(94):
            if full_enc == 'jis':
                code = ((ku + 0x21) << 8) | (ten + 0x21)
                e = gf.get(code)
            else:
                try:
                    ch = bytes([ku + 0xA1, ten + 0xA1]).decode('euc_jp')
                    e = gf.get(ord(ch))
                except Exception:
                    e = None
            rows = to_rows(e, ff, size, 16) if e else [0] * size
            if e: n += 1
            out += struct.pack('<%dH' % size, *rows)
    for c in range(0x20, 0x80):
        e = gh.get(c)
        rows = to_rows(e, fh, size, 8) if e else [0] * size
        out += bytes(rows)
    print(full_bdf, size, n, 'glyphs')
    return bytes(out)

def trr_build(strings):
    """strings: [(id, bytes)] → TRR"""
    n = len(strings)
    ids = [i for i, s in strings]
    data = bytearray()
    offs = []
    base = 4 + n * 8 + 4
    for i, s in strings:
        offs.append(base + len(data) - 4)
        data += s + b'\x00'
    total = 4 + n * 8 + 4 + len(data)
    out = struct.pack('<I', n) + struct.pack('<%dI' % n, *ids) + struct.pack('<%dI' % n, *offs) + struct.pack('<I', total - 4) + bytes(data)
    return out

def sec(tag, data):
    data = bytes(data)
    pad = (-len(data)) % 4
    return tag.encode() + struct.pack('<I', len(data)) + data + b'\x00' * pad

def build(files_loose, files_mix, subs, out, extra=()):
    """files_loose: {name: bytes}; files_mix: [(mixname, id, bytes)];
    subs: {filename: [(off, size, [(start_ms, end_ms, euc_text_bytes)])]}"""
    parts = [b'L2JP', b'\x00' * 4]
    parts.append(sec('FN08', font_sec('misaki_gothic_2nd.bdf', None, 8, 8, 4, 'unicode')))
    parts.append(sec('FN12', font_sec('shnmk12.bdf', 'shnm6x12a.bdf', 12, 12, 6, 'jis')))
    parts.append(sec('FN14', font_sec('shnmk14b.bdf', 'shnm7x14ab.bdf', 14, 14, 7, 'jis')))
    parts.append(sec('FN16', font_sec('shnmk16.bdf', 'shnm8x16a.bdf', 16, 16, 8, 'jis')))
    loos = bytearray()
    for name, data in files_loose.items():
        loos += name.encode().ljust(24, b'\x00') + struct.pack('<I', len(data)) + data + b'\x00' * ((-len(data)) % 4)
    parts.append(sec('LOOS', loos))
    mixp = bytearray()
    for name, wid, data in files_mix:
        mixp += name.encode().ljust(24, b'\x00') + struct.pack('<II', wid, len(data)) + data + b'\x00' * ((-len(data)) % 4)
    parts.append(sec('MIXP', mixp))
    if subs:
        subf = bytearray(); sube = bytearray(); subs_ = bytearray(); subt = bytearray()
        ent_i = 0; seg_i = 0
        for fi, (fname, ents) in enumerate(sorted(subs.items())):
            ents = sorted(ents)
            subf += fname.encode().ljust(24, b'\x00') + struct.pack('<II', ent_i, len(ents))
            for off, size, segs in ents:
                sube += struct.pack('<5I', fi, off, size, len(segs), seg_i)
                for s, e, t in segs:
                    subs_ += struct.pack('<3I', s, e, len(subt))
                    subt += t + b'\x00'
                    seg_i += 1
                ent_i += 1
        parts += [sec('SUBF', subf), sec('SUBE', sube), sec('SUBS', subs_), sec('SUBT', subt)]
    for tag, data in extra:
        parts.append(sec(tag, data))
    blob = b''.join(parts)
    open(out, 'wb').write(blob)
    print('blob', len(blob))

if __name__ == '__main__':
    import mix
    # 試験: OPTTEXT.TRR の頭だけ日本語に
    b = open(os.path.join(GAME, 'OPTTEXT.TRR'), 'rb').read()
    ss = mix.trr_strings(b)
    test = {0: 'メインメニュー', 1: 'ゲームを保存', 2: 'ゲームを読み込む', 3: '新しいゲーム', 4: '設定', 5: 'ヘルプ', 6: '終了'}
    ss2 = [(i, test[i].encode('euc_jp') if i in test else s) for i, s in ss]
    t = trr_build(ss2)
    assert mix.trr_strings(trr_build(ss)) == ss
    build({'OPTTEXT.TRR': t}, [('LOCALLNG.MIX', 0xae4c441b, t)], {}, os.path.join(JP, 'dll', 'lol2jp.bin'))
