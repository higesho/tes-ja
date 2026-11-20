# 元の Daggerfall の文の記録（制御バイトつき）→ Daggerfall Unity の CSV の書き方（[/center] など）
#   dec: 1 字を文字列にする関数（英語は latin1、日本語は字の表で戻す）
import csv, io, os

DFU = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'game', 'DaggerfallUnity_Data', 'StreamingAssets')
MASTER = os.path.join(DFU, 'Text', 'Master Localization CSV Files')

def to_markup(b, dec=None):
    """記録のバイト列（0xFE で終わる／終わらない）→ DFU の書き方"""
    out = []
    i = 0
    text = bytearray()
    def flush():
        if text:
            t = dec(bytes(text)) if dec else bytes(text).decode('latin1')
            if out and out[-1].endswith('\n') and t.startswith(' '):
                t = t[1:]          # 行の頭の空白 1 つは DFU が落とす
            out.append(t)
            text.clear()
    while i < len(b):
        c = b[i]
        if c == 0xFE:
            flush(); out.append('[/end]'); i += 1; break
        if c == 0xFC:
            flush(); out.append('[/left]\n'); i += 1
        elif c == 0xFD:
            flush(); out.append('[/center]\n'); i += 1
        elif c == 0xFB:
            flush(); out.append('[/pos:x=%d,y=0]' % b[i + 1]); i += 2
        elif c == 0xF9:
            flush(); out.append('[/font=%d]' % b[i + 1]); i += 2
        elif c == 0xFF:
            flush(); out.append('[/record]\n'); i += 1
        elif c == 0xF6:
            flush(); out.append('[/endpage]\n'); i += 1
        elif c == 0xF8:
            flush(); out.append('[/input]'); i += 1
        elif c == 0x00:
            flush(); out.append('[/newline]\n'); i += 1
        else:
            text.append(c); i += 1
    flush()
    return ''.join(out)

def read_csv(name):
    s = open(os.path.join(MASTER, name), encoding='utf-8-sig').read()
    return [(r[0], r[1]) for r in csv.reader(io.StringIO(s)) if r][1:]

def write_csv(path, rows):
    f = io.StringIO()
    w = csv.writer(f, lineterminator='\r\n')
    w.writerow(['Key', 'Value'])
    for k, v in rows:
        w.writerow([k, v])
    open(path, 'w', encoding='utf-8-sig', newline='').write(f.getvalue())
