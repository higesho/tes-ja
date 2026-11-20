# 綴りどおりに読む名前の表を作る（tools/romaji.py でカナにする）
#   translation/names/gen_monster.tsv  … 怪物・帝国領の名前（描画辞書に入る）
#   translation/names/gen_r1_head.tsv / gen_r1_tail.tsv … ハンマーフェルの名前の前半・後半（DLL が組み合わせて引く）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textutil import WORK
from names_combo import chunks
from romaji import kana
ND = os.path.join(WORK, 'translation', 'names')

def combos(ch, pat):
    """pat: [(部品の番号, 省けるか)]"""
    res = ['']
    for idx, opt in pat:
        nxt = []
        for r in res:
            if opt: nxt.append(r)
            for x in ch[idx]: nxt.append(r + x)
        res = nxt
    return res

def write(name, pairs):
    with open(os.path.join(ND, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# tools/names_gen.py が作る（手で直さない）\n')
        for e, j in pairs: f.write(e + '\t' + j + '\n')
    print(name, len(pairs))

if __name__ == '__main__':
    ch = chunks()
    seen = {}
    for pat in ([(47, 0), (48, 1), (49, 0)], [(50, 0), (51, 1), (52, 0)], [(50, 0), (52, 0), (53, 0)], [(55, 0), (56, 0), (57, 0)]):
        for w in combos(ch, pat):
            if w not in seen: seen[w] = kana(w)
    pairs = sorted(seen.items())
    pairs += [('Lord', 'ロード'), ('Count', '伯爵'), ('Baron', '男爵')]
    write('gen_monster.tsv', pairs)
    head = sorted(set(combos(ch, [(6, 0), (7, 0)])))
    tail = sorted(set(combos(ch, [(8, 0), (9, 1), (10, 1)])))
    write('gen_r1_head.tsv', [(w, kana(w)) for w in head])
    write('gen_r1_tail.tsv', [(w, kana(w)) for w in tail])
