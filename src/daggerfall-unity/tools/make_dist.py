# 配布物 dist/DaggerfallUnity_JP.zip を作る
#   中身は Daggerfall Unity のフォルダにそのまま展開する形（DaggerfallUnity_Data/StreamingAssets/...）
import os, zipfile, glob, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
JP = os.path.join(HERE, '..')
OUT = os.path.join(JP, 'out', 'StreamingAssets')
SA = 'DaggerfallUnity_Data/StreamingAssets/'

def main():
    os.makedirs(os.path.join(JP, 'dist'), exist_ok=True)
    p = os.path.join(JP, 'dist', 'DaggerfallUnity_JP.zip')
    n = 0
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(OUT, '**', '*.*'), recursive=True)):
            rel = os.path.relpath(f, OUT).replace(os.sep, '/')
            z.write(f, SA + rel); n += 1
        for i in range(5):
            z.write(os.path.join(JP, 'fonts', 'BIZUDPGothic-Bold.ttf'), SA + 'Fonts/FONT%04d-SDF.ttf' % i); n += 1
        for f in glob.glob(os.path.join(JP, 'dist_src', '*')):
            z.write(f, os.path.basename(f)); n += 1
    b = open(p, 'rb').read()
    print(os.path.basename(p), n, '個', len(b), hashlib.md5(b).hexdigest())

if __name__ == '__main__':
    main()
