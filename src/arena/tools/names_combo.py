# NAMECHNK.DAT の部品から、2 つの部品でできる名前（人間・エルフ系）を全部並べる
#   出力: translation/names/combos_<組>.txt（1 行 1 名）
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import WORK, read_game
def chunks():
    d = read_game('NAMECHNK.DAT'); o = 0; ch = []
    while o < len(d):
        L = struct.unpack('<H', d[o:o + 2])[0]; n = d[o + 2]
        ch.append([x.decode('latin1') for x in d[o + 3:o + L].split(b'\0')[:n]]); o += L
    return ch
# 組: (種族の説明, [(前の部品, 後ろの部品, 付け足し)])
GROUPS = {
    'r0_highrock': [(0, 1, ''), (2, 3, ''), (4, 5, '')],
    'r2_skyrim': [(11, 12, ''), (13, 14, ''), (15, 16, 'sen')],
    'r3_morrowind': [(17, 18, ''), (19, 20, ''), (21, 22, '')],
    'r4_summerset': [(23, 24, ''), (25, 26, ''), (27, 28, '')],
    'r5_valenwood': [(29, 30, ''), (31, 32, ''), (33, 34, '')],
    'r6_elsweyr': [(35, 36, ''), (37, 38, ''), (39, 40, '')],
    'r7_blackmarsh': [(41, 42, ''), (43, 44, ''), (45, 46, '')],
}
if __name__ == '__main__':
    ch = chunks(); tot = 0; seen = set()
    for g, parts in GROUPS.items():
        out = []
        for a, b, tail in parts:
            for x in ch[a]:
                for y in ch[b]:
                    w = x + y + tail
                    if w not in seen: seen.add(w); out.append(w)
        open(os.path.join(WORK, 'translation', 'names', 'combos_' + g + '.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
        print(g, len(out)); tot += len(out)
    print('計', tot)
