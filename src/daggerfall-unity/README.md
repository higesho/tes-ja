# ダガーフォール（Daggerfall Unity）日本語化 ソース

DOS 版の日本語化のデータを、Daggerfall Unity の StreamingAssets（文の CSV・本・クエスト・画像）に変換する道具です。

- `tools/dfu_build.py` … DOS 版の `build.py`（`src/daggerfall/tools`）を動かし、出来たデータを Daggerfall Unity の形に直す → `out/StreamingAssets/`
- `tools/dfumark.py` / `tools/dfu_dict.py` / `tools/cmp_rsc.py` … 書式の印の変換と、英文と訳の対応表
- `tools/namegen.py` … 名前の生成表を作る
- `tools/dfu_images.py` … 絵の中の文字を日本語にした画像を作る
- `tools/make_dist.py` … 配布用の zip を作る

DOS 版の道具の場所は各スクリプトの頭の `DFJP` で指定します。
必要なもの: Python 3（Pillow）。
ゲーム本体（GOG 版）、訳のファイル、BIZ UDP ゴシック（TTF、`fonts/` に置く）は各自で用意してください。
