# exe の文字列の訳（TSV: 番地 \t 英文 \t 訳）から ARENAJP\exe_ja.bin を作る
# 英文・訳の中の \r は改行（CR）、\n は LF、\t はタブ、\\ は逆斜線
# 使い方: python build_exe.py 出力.bin 訳.tsv [訳.tsv ...]
import sys, struct

def unesc(s):
    out = []; i = 0
    while i < len(s):
        if s[i] == chr(92) and i + 1 < len(s):
            c = s[i + 1]
            out.append({'r': '\r', 'n': '\n', 't': '\t', '0': '\0'}.get(c, c)); i += 2
        else:
            out.append(s[i]); i += 1
    return ''.join(out)

def load(paths):
    ents = []
    for p in paths:
        for ln in open(p, encoding='utf-8', newline=''):
            ln = ln.rstrip('\r\n')
            if not ln or ln.startswith('#'): continue
            f = ln.split('\t')
            if len(f) < 3 or not f[2]: continue
            ents.append((int(f[0], 16), unesc(f[1]).encode('latin1'), unesc(f[2]).encode('euc_jp')))
    return ents

if __name__ == '__main__':
    d = open(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'orig', 'acd_unpacked.bin'), 'rb').read()
    ents = load(sys.argv[2:])
    out = bytearray(b'ARJE' + struct.pack('<I', len(ents)))
    bad = 0
    for off, en, ja in ents:
        if d[off:off + len(en)] != en:
            print('英文が合わない', hex(off), en[:40]); bad += 1
        if len(ja) > len(en):
            print('長すぎ', hex(off), len(ja), '>', len(en), ja.decode('euc_jp')[:30]); bad += 1
        out += struct.pack('<IHH', off, len(en), len(ja)) + en + ja
    open(sys.argv[1], 'wb').write(out)
    print(len(ents), '件', '問題', bad)
