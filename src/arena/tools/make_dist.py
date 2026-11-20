"""配布物を dist/ に組み立てる: python -I tools/make_dist.py
dist/アリーナ日本語化MOD/ と dist/Arena_JP.zip を作る（DLL は dll/out、訳は test/arenajp の物を使う）
zip の一番上は DOSBOX フォルダと説明書なので、ゲームのフォルダにそのまま展開すればよい"""
import os, shutil, zipfile, glob

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
os.chdir(ROOT)
NAME = 'アリーナ日本語化MOD'
README = '日本語化MOD_はじめにお読みください.txt'
OUT = os.path.join('dist', NAME)
SRC = 'test/arenajp'

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, 'DOSBOX', 'ARENAJP', 'data'))
shutil.copyfile('dll/out/winmm.dll', os.path.join(OUT, 'DOSBOX', 'winmm.dll'))
for f in ['exe_ja.bin', 'dict.bin', 'inf.bin', 'spells.bin', 'pics.bin', 'names.bin', 'jpfont8.bin', 'jpfont16.bin']:
    shutil.copyfile(os.path.join(SRC, f), os.path.join(OUT, 'DOSBOX', 'ARENAJP', f))
for p in sorted(glob.glob(os.path.join(SRC, 'data', '*'))):
    shutil.copyfile(p, os.path.join(OUT, 'DOSBOX', 'ARENAJP', 'data', os.path.basename(p)))
# 設定（配布用は Enable だけ）
with open(os.path.join(OUT, 'DOSBOX', 'ARENAJP', 'arenajp.ini'), 'wb') as f:
    f.write(b'[Main]\r\nEnable=1\r\n')
# 説明書（メモ帳で読めるよう BOM 付き UTF-8、改行は CRLF）
txt = open('dist_src/はじめにお読みください.txt', encoding='utf-8').read().replace('\r\n', '\n')
with open(os.path.join(OUT, README), 'wb') as f:
    f.write(b'\xef\xbb\xbf' + txt.replace('\n', '\r\n').encode('utf-8'))

zp = os.path.join('dist', 'Arena_JP.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(OUT):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(base, fn)
            z.write(p, os.path.relpath(p, OUT).replace(os.sep, '/'))
for i in zipfile.ZipFile(zp).infolist():
    print(f'{i.file_size:9d}  {i.filename}')
print(zp, os.path.getsize(zp), 'バイト')
