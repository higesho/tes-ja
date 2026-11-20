# ACD.EXE（PKLITE 圧縮）を展開して、読み込み像（コード＋データ、再配置なし）を書き出す
# 使い方: python unpklite.py ACD.EXE out.bin
import sys

def B(s): return tuple(c == '1' for c in s)

D1 = ['10', '11', '000', '0010', '0011', '0100', '01010', '01011', '01100', '011010', '011011',
      '011100', '0111010', '0111011', '0111100', '01111010', '01111011', '01111100', '011111010',
      '011111011', '011111100', '011111101', '011111110', '011111111']
T1 = {}
for i, s in enumerate(D1):
    T1[B(s)] = i + 2 if i < 11 else (13 if i == 11 else i + 1)
SPECIAL = B('011100')
D2 = ['1', '0000', '0001', '00100', '00101', '00110', '00111', '010000', '010001', '010010', '010011',
      '010100', '010101', '010110', '0101110', '0101111', '0110000', '0110001', '0110010', '0110011',
      '0110100', '0110101', '0110110', '0110111', '0111000', '0111001', '0111010', '0111011', '0111100',
      '0111101', '0111110', '0111111']
T2 = {B(s): i for i, s in enumerate(D2)}

def unpack(src):
    start = 752
    end = len(src) - 8
    assert src[end - 2:end] == b'\xff\xff'
    seg = src[end] | src[end + 1] << 8
    off = src[end + 2] | src[end + 3] << 8
    out = bytearray(seg * 16 + off)
    st = {'arr': src[start] | src[start + 1] << 8, 'bi': 2, 'br': 0}
    def nb():
        b = src[start + st['bi']]; st['bi'] += 1; return b
    def bit():
        v = (st['arr'] >> st['br']) & 1
        st['br'] += 1
        if st['br'] == 16:
            st['br'] = 0
            a = nb(); b = nb(); st['arr'] = a | b << 8
        return v == 1
    di = 0
    while True:
        if bit():
            k = ()
            while k not in T1: k += (bit(),)
            if k == SPECIAL:
                e = nb()
                if e == 0xFE: continue
                if e == 0xFF: break
                cnt = e + 25
            else:
                cnt = T1[k]
            hi = 0
            if cnt != 2:
                k = ()
                while k not in T2: k += (bit(),)
                hi = T2[k]
            o = nb() | hi << 8
            b0 = di - o
            for i in range(cnt):
                out[di] = out[b0 + i]; di += 1
        else:
            e = nb()
            out[di] = e ^ (16 - st['br']); di += 1
    return bytes(out)

if __name__ == '__main__':
    d = unpack(open(sys.argv[1], 'rb').read())
    open(sys.argv[2], 'wb').write(d)
    print(len(d))
