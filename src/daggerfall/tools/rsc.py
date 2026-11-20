# TEXT.RSC の読み書き: 頭に [u16 表の大きさ] [id u16, 位置 u32]... 、本文は 0xFE で終わる記録
import struct

def load(b):
    hs = struct.unpack_from('<H', b, 0)[0]
    n = hs // 6
    ents = [struct.unpack_from('<HI', b, 2 + i * 6) for i in range(n)]
    recs = []
    for i, (rid, off) in enumerate(ents):
        if rid == 0xFFFF:
            break
        end = ents[i + 1][1] if i + 1 < n else len(b)
        recs.append((rid, bytes(b[off:end])))
    return recs

def save(recs):
    n = len(recs) + 1
    hs = n * 6
    head = bytearray(struct.pack('<H', hs))
    body = bytearray()
    base = 2 + hs
    for rid, data in recs:
        head += struct.pack('<HI', rid, base + len(body))
        body += data
    head += struct.pack('<HI', 0xFFFF, base + len(body))
    return bytes(head + body)

if __name__ == '__main__':
    import sys
    b = open(sys.argv[1], 'rb').read()
    r = load(b)
    print(len(r), save(r) == b)
