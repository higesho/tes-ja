# 配布物 dist/Daggerfall_JP.zip を作る（DOSBOX/winmm.dll と説明書）
import os, zipfile, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
JP = os.path.join(HERE, '..')
out = os.path.join(JP, 'dist', 'Daggerfall_JP.zip')
os.makedirs(os.path.dirname(out), exist_ok=True)
dll = os.path.join(JP, 'dll', 'winmm.dll')
readme = os.path.join(JP, 'dist_src', '日本語化MOD_はじめにお読みください.txt')
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(readme, '日本語化MOD_はじめにお読みください.txt')
    z.write(dll, 'DOSBOX/winmm.dll')
for p in (dll, out):
    print(os.path.basename(p), os.path.getsize(p), hashlib.md5(open(p, 'rb').read()).hexdigest())
