# アリーナ 日本語化 ソース

GOG 版 The Elder Scrolls: Arena（DOS）用の `DOSBOX\winmm.dll`（DOSBox の中のゲームを書き換えて日本語を描く）と、そのデータ（ARENAJP フォルダ）を作る道具です。

- `dll/` … winmm.dll の本体。`build.bat`（Visual Studio の x86 の cl）で `dll/out/winmm.dll` ができます。`build.bat test` で作る試験版（`build/test/winmm.dll`、試験用の操作口 `testctl.c` とログ入り）は配布しません
- `tools/unpklite.py` … ACD.EXE（PKLITE 圧縮）を展開する
- `tools/bsa.py` / `tools/img.py` … ゲームの書庫 BSA と絵を読む
- `tools/extract.py` / `tools/exe_strings.py` … 英文を `translation/en/` に抜き出す
- `tools/build.py` / `tools/build_exe.py` … 訳から ARENAJP 一式（`test/arenajp/`）を作る
- `tools/names_combo.py` / `tools/names_gen.py` / `tools/romaji.py` … 町や人の名前を片仮名にする表を作る
- `tools/make_pics.py` / `tools/picfont.py` / `tools/formwords.py` … 絵の中の文字の差し替えデータを作る（絵ごとの訳の指定は含みません）
- `tools/make_font16.py` … 14 ドットの字の形の表を作る
- `tools/make_dist.py` … 配布用の zip を作る

必要なもの: Python 3（Pillow）、Visual Studio。
ゲーム本体（GOG 版）、訳のファイル、美咲フォント・東雲フォント（BDF、`font/` に置く）は各自で用意してください。
