# 東雲（JIS 順の BDF）から EUC 区点順の 16x16 字形表 font/jpfont16.bin（94*94*32 バイト）を作る
# 使い方: python make_font16.py [bdf] [上の余白] [左の余白]（14 ドットの字は 16 の枠に上 1・左 1 で置く）
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'font', 'shnmk14b.bdf')
top = int(sys.argv[2]) if len(sys.argv) > 2 else 1
left = int(sys.argv[3]) if len(sys.argv) > 3 else 1
out = bytearray(94 * 94 * 32)
code = None; bits = None; n = 0
for ln in open(src, encoding='latin1'):
    f = ln.split()
    if not f: continue
    if f[0] == 'ENCODING': code = int(f[1])
    elif f[0] == 'BITMAP': bits = []
    elif f[0] == 'ENDCHAR':
        if code is not None and bits is not None:
            ku, ten = (code >> 8) - 0x21, (code & 0xFF) - 0x21
            if 0 <= ku < 94 and 0 <= ten < 94:
                o = (ku * 94 + ten) * 32
                for r, v in enumerate(bits[:16 - top]):
                    v = (v >> left) & 0xFFFF
                    out[o + (r + top) * 2] = v >> 8; out[o + (r + top) * 2 + 1] = v & 0xFF
                n += 1
        code = bits = None
    elif bits is not None:
        bits.append(int(f[0], 16) << (16 - 4 * len(f[0])) if len(f[0]) < 4 else int(f[0][:4], 16))
open(os.path.join(HERE, '..', 'font', 'jpfont16.bin'), 'wb').write(out)
print(n, '字')
