# FALL.EXE の文字列の差し替えデータを作る（DLL の EXEF / EXEB / EXER）
#   EXEF: ファイルを読むときに当てる書き換え [u32 ファイル位置][u32 長さ][中身]...
#         （obj3 の大きさを広げる・品物の名前をその場で書き換える）
#   EXEB: 起動直後に obj3 の広げた所（NEWOFF から）へ書く日本語の文字列の塊
#   EXER: 張り替える参照 [u32 参照の番地（LE の既定番地）][u32 元の文字列の番地][u32 塊の中の位置]...
#   EXEK: obj3 のずれを読むための参照 [u32 参照の番地][u32 指す先]
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dfdis import L
import dftext

NEWOFF = 0x45600            # obj3 の中の、日本語の文字列を置く位置（元の大きさ 0x45520 の後ろ）
EXTRA = 0x30000             # obj3 を広げる量

def foff(a):
    for ob in L.objs:
        if ob['base'] <= a < ob['base'] + ob['pcnt'] * L.page_size:
            o = a - ob['base']
            return L.page_file_off(ob['pidx'] + o // L.page_size) + o % L.page_size
    return None

def sites_by_target():
    """文字列の番地 → [参照の番地]（32 ビットの番地の再配置だけ）"""
    d = {}
    for obj, at, st, tobj, toff in L.fixups:
        if st != 7 or at < 0:
            continue
        tgt = L.objs[tobj - 1]['base'] + toff
        d.setdefault(tgt, []).append(L.objs[obj - 1]['base'] + at)
    return d

def build(exe_ja):
    """exe_ja: {番地(int): (種類, 日本語)} → [(tag, bytes)]"""
    sites = sites_by_target()
    o3 = L.objs[2]
    assert o3['vsize'] <= NEWOFF
    fpatch = bytearray()
    # obj3 の大きさ
    vs_off = L.h + L.obj_tab + 2 * 24
    fpatch += struct.pack('<II', vs_off, 4) + struct.pack('<I', NEWOFF + EXTRA)
    blob = bytearray()
    rel = bytearray()
    n_p = n_i = 0
    for a, (k, j) in sorted(exe_ja.items()):
        if k == 'I':
            b = dftext.to_game(j, hints=False)
            if len(b) > 23:
                print('品物の名前が長い', hex(a), j); continue
            fo = foff(a)
            fpatch += struct.pack('<II', fo, 24) + b.ljust(24, b'\0')
            n_i += 1
        else:
            b = b'' if j == '#EMPTY' else dftext.to_game(j)
            ss = sites.get(a, [])
            if not ss:
                continue
            off = len(blob)
            blob += b + b'\0'
            while len(blob) % 4: blob += b'\0'
            for s in ss:
                rel += struct.pack('<III', s, a, off)
            n_p += 1
    if len(blob) > EXTRA - 0x100:
        raise SystemExit('文字列の塊が大きすぎる %d' % len(blob))
    # obj3 のずれを読むための参照（obj1 の中で obj3 を指すもの）
    key = None
    for t, ss in sites.items():
        if o3['base'] <= t < o3['base'] + o3['vsize']:
            for s in ss:
                if s < L.objs[1]['base']:
                    key = (s, t); break
        if key: break
    print('EXE 文字列', n_p, '品物', n_i, '塊', len(blob), '参照', len(rel) // 12)
    return [('EXEF', bytes(fpatch)), ('EXEB', bytes(blob)), ('EXER', bytes(rel)),
            ('EXEK', struct.pack('<III', key[0], key[1], o3['base'] + NEWOFF))]
