# ダガーフォール 日本語化 ソース

GOG 版 The Elder Scrolls II: Daggerfall（DOS）用の `DOSBOX\winmm.dll`（DOSBox の中のゲームを書き換えて日本語を描く）と、そのデータを作る道具です。

- `dll/` … winmm.dll の本体。`build.bat`（Visual Studio の x86 の cl と rc）で組み立てます。先に `tools/build.py` で `dll/dfjp.bin` を作ってください。`build.bat test` で作る試験版（`build/test/winmm.dll`、試験用の操作口とログ入り）は配布しません
- `tools/rsc.py` / `tools/dftext.py` … ゲームの文章ファイルを読み、日本語の折り返しをする
- `tools/extract.py` / `tools/exe_strings.py` … 英文を `translation/en/` に抜き出す
- `tools/build.py` / `tools/jpdata.py` / `tools/mkdata.py` … 訳と字の形から `dll/dfjp.bin` を作る
- `tools/exe_patch.py` / `tools/dfdis.py` / `tools/le.py` … FALL.EXE の文字列の差し替えデータを作る
- `tools/imgpatch.py` / `tools/imgtext.py` / `tools/img.py` … 絵の中の文字の差し替えデータを作る
- `tools/names_dos.py` … 地名・人名の差し替えデータを作る
- `tools/check_ja.py` … 訳を検査する
- `tools/make_dist.py` … 配布用の zip を作る

必要なもの: Python 3（capstone・Pillow）、Visual Studio。
ゲーム本体（GOG 版）、訳のファイル、美咲フォント・東雲フォント（BDF、`font/` に置く）は各自で用意してください。
