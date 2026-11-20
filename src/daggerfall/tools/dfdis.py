# FALL.EXE の逆アセンブルと参照探し
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import le as lemod
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

GAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'FALL.EXE')
L = lemod.LE(GAME)
md = Cs(CS_ARCH_X86, CS_MODE_32)
XREF = {}
for obj, at, stype, tobj, toff in L.fixups:
    if stype in (7, 8):
        tgt = (L.objs[tobj - 1]['base'] + toff) & 0xffffffff
        XREF.setdefault(tgt, []).append(L.objs[obj - 1]['base'] + at)

def dis(addr, n=40, stop_ret=False):
    code = L.read(addr, n * 8)
    out = []
    for ins in md.disasm(code, addr):
        out.append('%08x: %-20s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
        if len(out) >= n or (stop_ret and ins.mnemonic in ('ret', 'retf')):
            break
    return '\n'.join(out)

def find_str(s):
    res = []
    for i, ob in enumerate(L.objs):
        buf = L.img[i + 1]
        for m in re.finditer(re.escape(s), buf):
            res.append(ob['base'] + m.start())
    return res

def cstr(addr, n=200):
    b = L.read(addr, n)
    return b.split(b'\x00')[0]

def func_start(addr):
    """呼び出し先の頭を探す: 手前の直近の関数の頭（XREF に call 先として出る番地）"""
    best = None
    for t in CALLS:
        if t <= addr and (best is None or t > best):
            best = t
    return best

CALLS = set()
def scan_calls():
    ob = L.objs[0]
    buf = L.img[1]
    for i in range(len(buf) - 5):
        if buf[i] == 0xE8:
            rel = struct.unpack_from('<i', buf, i + 1)[0]
            t = ob['base'] + i + 5 + rel
            if ob['base'] <= t < ob['base'] + ob['vsize']:
                CALLS.add(t)
scan_calls()

def callers(t):
    ob = L.objs[0]
    buf = L.img[1]
    res = []
    for i in range(len(buf) - 5):
        if buf[i] == 0xE8:
            rel = struct.unpack_from('<i', buf, i + 1)[0]
            if ob['base'] + i + 5 + rel == t:
                res.append(ob['base'] + i)
    return res

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'dis':
        print(dis(int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 40))
    elif cmd == 'str':
        for a in find_str(sys.argv[2].encode()):
            print(hex(a), [hex(x) for x in XREF.get(a, [])])
    elif cmd == 'xref':
        print([hex(x) for x in XREF.get(int(sys.argv[2], 16), [])])
    elif cmd == 'callers':
        print([hex(x) for x in callers(int(sys.argv[2], 16))])
