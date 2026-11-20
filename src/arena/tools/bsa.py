# GLOBAL.BSA を読む・書く
#   python bsa.py list            一覧
#   python bsa.py get 名前 出力    取り出す（INF は復号する）
import sys, struct, os

BSA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'GLOBAL.BSA')
KEYS = [0xEA, 0x7B, 0x4E, 0xBD, 0x19, 0xC9, 0x38, 0x99]

def read(path=BSA):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<H', d, 0)[0]
    idx = len(d) - n * 18
    ents = []
    pos = 2
    for i in range(n):
        name = d[idx + i * 18: idx + i * 18 + 12].split(b'\0')[0].decode('latin1')
        comp, size = struct.unpack_from('<HI', d, idx + i * 18 + 12)
        ents.append((name, pos, size, comp, d[idx + i * 18: idx + i * 18 + 14]))
        pos += size
    return d, ents

def crypt(b):
    out = bytearray(b)
    for i in range(len(out)):
        out[i] ^= ((i & 0xFF) + KEYS[i % 8]) & 0xFF
    return bytes(out)

def get(d, e):
    name, pos, size, comp, raw = e
    b = d[pos:pos + size]
    if name.upper().endswith('.INF'):
        b = crypt(b)
    return b

def write(path, d, ents, repl):
    """repl: 名前 -> 新しい中身（INF は平文で渡す）"""
    out = bytearray(d[:2])
    tail = bytearray()
    for name, pos, size, comp, raw in ents:
        if name in repl:
            b = repl[name]
            if name.upper().endswith('.INF'): b = crypt(b)
        else:
            b = d[pos:pos + size]
        out += b
        tail += raw[:14] + struct.pack('<I', len(b))
    open(path, 'wb').write(out + tail)

if __name__ == '__main__':
    d, ents = read()
    if sys.argv[1] == 'list':
        for e in ents: print(e[0], e[2], e[3])
    elif sys.argv[1] == 'get':
        for e in ents:
            if e[0].upper() == sys.argv[2].upper():
                open(sys.argv[3], 'wb').write(get(d, e))
