# DFU の NameGen.txt（名前の部品。厳密な JSON ではない）を読む・部品を差し替えて書く
import re, os
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'game', 'DaggerfallUnity_Data', 'StreamingAssets', 'Text',
                   'Master Localization CSV Files', 'NameGen.txt')

def read():
    """[(種族, 組の番号, 部品)]"""
    s = open(SRC, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'^\s{4}"(\w+)":\s*\{(.*?)(?=^\s{4}"\w+":|\Z)', s, re.M | re.S):
        race, body = m.group(1), m.group(2)
        for sm in re.finditer(r'"setIndex":\s*(\d+),\s*"parts":\s*\[(.*?)\]', body, re.S):
            for p in re.findall(r'"([^"]*)"', sm.group(2)):
                out.append((race, int(sm.group(1)), p))
    return out

def write(path, tr):
    """tr: (種族, 組, 部品) → 日本語。元の書き方のまま、部品の文字列だけを置き換える"""
    s = open(SRC, encoding='utf-8').read()
    out = []; pos = 0
    for m in re.finditer(r'^\s{4}"(\w+)":\s*\{(.*?)(?=^\s{4}"\w+":|\Z)', s, re.M | re.S):
        race = m.group(1)
        bstart = m.start(2)
        body = m.group(2)
        def setrep(sm):
            idx = int(sm.group(1))
            def prep(pm):
                p = pm.group(1)
                return '"%s"' % tr.get((race, idx, p), p)
            return sm.group(0)[:sm.start(2) - sm.start(0)] + re.sub(r'"([^"]*)"', prep, sm.group(2)) + sm.group(0)[sm.end(2) - sm.start(0):]
        nb = re.sub(r'"setIndex":\s*(\d+),\s*"parts":\s*\[(.*?)\]', setrep, body, flags=re.S)
        out.append(s[pos:bstart]); out.append(nb); pos = m.end(2)
    out.append(s[pos:])
    open(path, 'w', encoding='utf-8', newline='').write(''.join(out))

if __name__ == '__main__':
    import collections
    ps = read()
    c = collections.Counter((r, i) for r, i, p in ps)
    print(len(ps), len(set(p for r, i, p in ps)))
    for k, n in sorted(c.items()): print(k, n)
