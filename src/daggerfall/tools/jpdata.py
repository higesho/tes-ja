# DLL に埋め込むデータ（dll/dfjp.bin）: 字体 FN08/FN12/FN14、字の表 CMAP、差し替えファイル FILE
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mkdata import font_sec, sec
JP = os.path.join(HERE, '..')

# 画面の日本語: 前 0x80-0xAF、後 0xB0-0xEF（字の番号 = (前-0x80)*64 + (後-0xB0)）
NLEAD, NTRAIL = 48, 64
CMAP = []
CIDX = {}
# 字の番号の並びは translation/cmap.tsv に固定する（セーブの中の品物名などが、更新で別の字に化けないよう）。
# 新しい字は後ろに足すだけ
CMAP_FILE = os.path.join(JP, 'translation', 'cmap.tsv')
if os.path.exists(CMAP_FILE):
    for _l in open(CMAP_FILE, encoding='utf-8'):
        _l = _l.strip()
        if _l:
            _c = int(_l.split('\t')[0], 16)
            CIDX[_c] = len(CMAP); CMAP.append(_c)
REP = {'～': '〜', '―': '—', '－': '−', '･': '・', '“': '「', '”': '」'}

def to_game(s):
    """日本語まじりの文 → ゲームに渡すバイト列（ASCII と 0xF0 以上の制御符号はそのまま）"""
    out = bytearray()
    for ch in s:
        ch = REP.get(ch, ch)
        o = ord(ch)
        if o < 0x80:
            out.append(o); continue
        if 0xF0 <= o <= 0xFF:           # Daggerfall の制御符号（文の中では '\xfd' などで書く）
            out.append(o); continue
        try:
            e = ch.encode('euc_jp')
        except UnicodeEncodeError:
            out.append(ord('?')); continue
        if len(e) != 2:
            out.append(ord('?')); continue
        code = e[0] << 8 | e[1]
        if code not in CIDX:
            CIDX[code] = len(CMAP); CMAP.append(code)
        i = CIDX[code]
        if i >= NLEAD * NTRAIL:
            raise SystemExit('字の種類が多すぎる (%d)' % len(CMAP))
        out += bytes([0x80 + i // NTRAIL, 0xB0 + i % NTRAIL])
    return bytes(out)

def jwidth(s, jw=8):
    """日本語の字の幅（半角は字体ごとに違うので、目安として 4）"""
    return sum(jw if ord(c) >= 0x80 else 4 for c in s)

def build(files, out, extra=()):
    """files: {"ARENA2\\TEXT.RSC": bytes}、extra: [(tag, bytes)]（字の表より前に to_game を済ませておく）"""
    parts = [b'DFJP', b'\x00' * 4]
    parts.append(sec('FN08', font_sec('misaki_gothic_2nd.bdf', None, 8, 8, 4, 'unicode')))
    parts.append(sec('FN12', font_sec('shnmk12.bdf', 'shnm6x12a.bdf', 12, 12, 6, 'jis')))
    parts.append(sec('FN14', font_sec('shnmk14b.bdf', 'shnm7x14ab.bdf', 14, 14, 7, 'jis')))
    parts.append(sec('FN16', font_sec('shnmk16.bdf', 'shnm8x16a.bdf', 16, 16, 8, 'jis')))   # 拡大後の画面に重ねる細かい字
    parts.append(sec('CMAP', struct.pack('<%dH' % len(CMAP), *CMAP)))
    fl = bytearray()
    for name, data in files.items():
        fl += name.upper().encode().ljust(32, b'\x00') + struct.pack('<I', len(data)) + data + b'\x00' * ((-len(data)) % 4)
    parts.append(sec('FILE', fl))
    for tag, data in extra:
        parts.append(sec(tag, data))
    blob = b''.join(parts)
    open(out, 'wb').write(blob)
    with open(CMAP_FILE, 'w', encoding='utf-8') as f:
        for c in CMAP:
            f.write('%04x\t%s\n' % (c, bytes([c >> 8, c & 255]).decode('euc_jp', 'replace')))
    print('blob', len(blob), '字', len(CMAP), 'ファイル', len(files))
