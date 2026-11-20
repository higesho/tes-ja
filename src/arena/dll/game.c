/* ACD.EXE（PKLITE 展開後）を見つけて、文字列を差し替え、文字の幅と描画を日本語対応にする */
#include "arenajp.h"
#include <stdio.h>
#include <stdlib.h>

/* 展開した像（読み込みセグメント先頭からの線形）での番地 */
#define A_FONTNAME   0x3F47C   /* "font_a.dat" */
#define A_STRWIDTH   0x066F6   /* 文字列の幅 DS:SI → AX=DX=幅 */
#define A_DRAWLINE   0x09E0A   /* 1 行描く AX=x BX=y DS:SI */
#define A_WRAP       0x1633F   /* 折り返し DS:SI、1 行 [137E] バイト */
#define A_FILTER     0x1C008   /* テンプレートの字の選別: cmp [si],7A / jbe（→ jmp にして 0x7B 以上も通す） */
#define DG_SEG       0x3BA0    /* DGROUP の相対セグメント */
/* DGROUP 内の変数 */
#define V_COLOR      0x9288
#define V_ROWTBL     0xA6A0
#define V_DESTSEG    0xA900
#define V_CURX       0xADB6
#define V_CURY       0xADB8
#define V_FONT       0xB034    /* far ptr: [0]=高さ [1..95]=幅 [0x5F..]=字形 */

static uint32_t g_base;      /* 像の先頭の線形番地（0 なら未発見） */
static uint32_t g_dg;        /* DGROUP の線形番地 */
static int cbW, cbD, cbR;

/* DGROUP の線形番地（ACD を見つけていなければ 0） */
uint32_t Game_DG(void) { return g_base ? g_dg : 0; }

static uint8_t *g_exe;       /* exe_ja.bin */
static uint32_t g_exesize;

/* ---------- 文字列の差し替え ---------- */
static void PatchStrings(void)
{
    uint32_t n, i, p = 8, ok = 0, ng = 0;
    if (!g_exe || g_exesize < 8 || memcmp(g_exe, "ARJE", 4)) return;
    n = *(uint32_t *)(g_exe + 4);
    for (i = 0; i < n && p + 8 <= g_exesize; i++) {
        uint32_t off = *(uint32_t *)(g_exe + p);
        uint16_t el = *(uint16_t *)(g_exe + p + 4), jl = *(uint16_t *)(g_exe + p + 6);
        const uint8_t *en = g_exe + p + 8, *ja = en + el;
        p += 8 + el + jl;
        if (jl > el || off + el >= 0x4A970) { ng++; continue; }
        if (memcmp(lin(g_base + off), en, el)) { ng++; if (g_trace) LogF("不一致 %05X", off); continue; }
        memcpy(lin(g_base + off), ja, jl);
        /* 余りは NUL ではなく 0x80（幅 0・描かない）で埋める。NUL を数えて n 番目を探す表があるため */
        memset(lin(g_base + off + jl), 0x80, el - jl);
        ok++;
    }
    LogF("exe 文字列 %u 件差し替え（合わず %u）", ok, ng);
}

/* ---------- 描画辞書（英語の固有名詞を描く直前に日本語へ） ----------
   dict.bin: "ARJD" u32 件数, {u8 英長, u8 日長, 英, 日}*（英語の長い順） */
typedef struct { const uint8_t *en, *ja; uint8_t el, jl; } DictEnt;
static DictEnt *g_dict;
static int g_ndict;
static DictEnt g_exact[256];   /* 「=」付き: 切れ端全体が一致したら置き換える */
static int g_nexact;
static int g_dfirst[256][2];   /* 先頭の字ごとの [開始, 終わり)（長い順に並ぶ） */

static int CmpEnt(const void *a, const void *b)
{
    const DictEnt *x = (const DictEnt *)a, *y = (const DictEnt *)b;
    if (x->en[0] != y->en[0]) return x->en[0] - y->en[0];
    return y->el - x->el;
}

static void Dict_Load(const char *path)
{
    uint32_t size, n, i, p = 8;
    uint8_t *d = ReadAll(path, &size);
    if (!d || size < 8 || memcmp(d, "ARJD", 4)) return;
    n = *(uint32_t *)(d + 4);
    g_dict = (DictEnt *)calloc(n, sizeof(DictEnt));
    for (i = 0; i < n && p + 2 <= size; i++) {
        DictEnt *e = &g_dict[g_ndict];
        e->el = d[p]; e->jl = d[p + 1];
        e->en = d + p + 2; e->ja = e->en + e->el;
        p += 2 + e->el + e->jl;
        if (e->el > 1 && e->en[0] == '=') {
            if (g_nexact < 256) { g_exact[g_nexact] = *e; g_exact[g_nexact].en++; g_exact[g_nexact].el--; g_nexact++; }
            continue;
        }
        if (e->el) g_ndict++;
    }
    qsort(g_dict, g_ndict, sizeof(DictEnt), CmpEnt);
    for (i = 0; i < 256; i++) g_dfirst[i][0] = g_dfirst[i][1] = 0;
    for (i = 0; i < (uint32_t)g_ndict; i++) {
        uint8_t c = g_dict[i].en[0];
        if (g_dfirst[c][1] == 0) g_dfirst[c][0] = i;
        g_dfirst[c][1] = i + 1;
    }
    LogF("描画辞書 %d 件、切れ端一致 %d 件", g_ndict, g_nexact);
}

static __inline int IsWordCh(uint8_t c)
{
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

/* ---------- 部品の組み合わせの名前（names.bin: 前半と後半の表） ---------- */
static DictEnt *g_nhead, *g_ntail;
static int g_nnhead, g_nntail;

static void Names_Load(const char *path)
{
    uint32_t size, p = 12, k;
    uint8_t *d = ReadAll(path, &size);
    if (!d || size < 12 || memcmp(d, "ARJN", 4)) return;
    g_nnhead = *(uint32_t *)(d + 4); g_nntail = *(uint32_t *)(d + 8);
    g_nhead = (DictEnt *)calloc(g_nnhead + g_nntail, sizeof(DictEnt));
    g_ntail = g_nhead + g_nnhead;
    for (k = 0; k < (uint32_t)(g_nnhead + g_nntail) && p + 2 <= size; k++) {
        DictEnt *e = &g_nhead[k];
        e->el = d[p]; e->jl = d[p + 1]; e->en = d + p + 2; e->ja = e->en + e->el;
        p += 2 + e->el + e->jl;
    }
    LogF("名前の表 前半 %d、後半 %d", g_nnhead, g_nntail);
}

static __inline int IsNameCh(uint8_t c)
{
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '\'' || c == '-';
}

/* in+i から始まる 1 語を辞書（なければ前半＋後半の表）で引き、日本語を out に書く。
   戻り値は読んだ英語の長さ（引けなければ 0）。*w に書いた長さ */
static int NameAt(const uint8_t *in, int i, uint8_t *out, int room, int *w)
{
    uint8_t c = in[i];
    int k;
    if (g_ndict && g_dfirst[c][1]) {
        for (k = g_dfirst[c][0]; k < g_dfirst[c][1]; k++) {
            const DictEnt *e = &g_dict[k];
            if (!memcmp(in + i, e->en, e->el) && !IsWordCh(in[i + e->el])) {
                if (e->jl > room) return 0;
                memcpy(out, e->ja, e->jl); *w = e->jl;
                return e->el;
            }
        }
    }
    if (g_nnhead && c >= 'A' && c <= 'Z') {
        int e = i, h, t;
        while (IsNameCh(in[e])) e++;
        while (e > i && (in[e - 1] == '-' || in[e - 1] == '\'')) e--;
        if (IsWordCh(in[e])) return 0;
        for (h = 0; h < g_nnhead; h++) {
            const DictEnt *a = &g_nhead[h];
            int rest = e - i - a->el;
            if (rest <= 0 || a->en[0] != c || memcmp(in + i, a->en, a->el)) continue;
            for (t = 0; t < g_nntail; t++) {
                const DictEnt *b = &g_ntail[t];
                if (b->el == rest && !memcmp(in + i + a->el, b->en, rest)) {
                    if (a->jl + b->jl > room) return 0;
                    memcpy(out, a->ja, a->jl); memcpy(out + a->jl, b->ja, b->jl);
                    *w = a->jl + b->jl;
                    return e - i;
                }
            }
        }
    }
    return 0;
}

/* in を辞書で置き換えて out へ（out は outmax まで）。戻り値は長さ */
static int Dict_Apply(const uint8_t *in, uint8_t *out, int outmax)
{
    int i = 0, o = 0, segstart = 1;
    while (in[i] && o < outmax - 1) {
        uint8_t c = in[i];
        /* 色などの指定（	 と 1 バイト）と改行は写して、切れ端の始まりとする */
        if (c == 0x09 && in[i + 1]) { if (o + 2 >= outmax) break; out[o++] = c; out[o++] = in[i + 1]; i += 2; segstart = 1; continue; }
        if (c == 0x0D || c == 0x0A) { out[o++] = c; i++; segstart = 1; continue; }
        if (segstart && g_nexact) {
            int e = i, k, hit = -1;
            segstart = 0;
            while (in[e] && in[e] != 0x09 && in[e] != 0x0D && in[e] != 0x0A) e++;
            for (k = 0; k < g_nexact; k++)
                if (g_exact[k].el == e - i && !memcmp(in + i, g_exact[k].en, e - i)) { hit = k; break; }
            if (hit >= 0) {
                if (o + g_exact[hit].jl + 1 >= outmax) break;
                memcpy(out + o, g_exact[hit].ja, g_exact[hit].jl); o += g_exact[hit].jl;
                i = e;
                continue;
            }
        }
        segstart = 0;
        if ((g_ndict || g_nnhead) && IsWordCh(c) && (i == 0 || !IsWordCh(in[i - 1]))) {
            int w = 0, n = NameAt(in, i, out + o, outmax - o - 3, &w);
            if (n) {
                int j = i + n;
                o += w;
                /* 名前が空白をはさんで続くときは「・」でつなぐ（名と姓、称号と名） */
                while (in[j] == ' ' && in[j + 1] >= 'A' && in[j + 1] <= 'Z' && o + 4 < outmax) {
                    int w2 = 0, n2 = NameAt(in, j + 1, out + o + 2, outmax - o - 5, &w2);
                    if (!n2) break;
                    out[o] = 0xA1; out[o + 1] = 0xA6;   /* ・ */
                    o += 2 + w2; j += 1 + n2;
                }
                /* 所有の 's は「の」にする */
                if (in[j] == '\'' && in[j + 1] == 's' && !IsWordCh(in[j + 2]) && o + 2 < outmax) { out[o++] = 0xA4; out[o++] = 0xCE; j += 2; }
                i = j;
                continue;
            }
        }
        /* 2 バイト文字は分けずに写す */
        if (c >= 0xA1 && in[i + 1] >= 0xA1) { if (o + 2 >= outmax) break; out[o++] = c; out[o++] = in[i + 1]; i += 2; continue; }
        out[o++] = c; i++;
    }
    out[o] = 0;
    return o;
}

/* ---------- 幅 ---------- */
static int CharW(uint32_t font, const uint8_t *s, int *adv)
{
    uint8_t c = s[0];
    *adv = 1;
    if (c == 0x20) return rd8(font + 1) + 1;
    if (c >= 0xA1 && s[1] >= 0xA1) { *adv = 2; return 8; }
    if (c & 0x80) return 0;
    if (c < 0x20) return 0;
    return rd8(font + (c - 0x20));
}

#define MAXS 1024
static int CopyStr(uint32_t seg, uint16_t off, uint8_t *buf)
{
    int n = 0;
    while (n < MAXS - 1) {
        uint8_t c = rd8(seg + (uint16_t)(off + n));
        buf[n++] = c;
        if (!c) break;
    }
    buf[n] = 0;
    return n;
}

static uint32_t CB_Width(void)
{
    uint8_t raw[MAXS + 2], buf[MAXS * 2 + 2];
    uint32_t font = farptr(g_dg + V_FONT);
    int i = 0, w = 0, adv;
    CopyStr(segbase(S_DS), reg16(R_SI), raw);
    raw[MAXS] = raw[MAXS + 1] = 0;
    Dict_Apply(raw, buf, MAXS * 2);
    buf[MAXS * 2] = buf[MAXS * 2 + 1] = 0;
    while (buf[i]) { w += CharW(font, buf + i, &adv); i += adv; }
    set16(R_AX, (uint16_t)w);
    set16(R_DX, (uint16_t)w);
    if (g_trace) LogF("幅 %d [%s] ds %X si %X 呼び元 %X", w, buf, DBX_SEGVAL(S_DS), reg16(R_SI), rd16(segbase(S_SS) + reg16(R_SP)));
    return 0;
}

/* ---------- 描画 ---------- */
static __inline void Put(uint32_t a, uint8_t v)
{
    wr8(a, v);
}

static uint32_t CB_Draw(void)
{
    uint8_t raw[MAXS + 2], buf[MAXS * 2 + 2];
    uint32_t font = farptr(g_dg + V_FONT);
    int x = (int16_t)reg16(R_AX), y = (int16_t)reg16(R_BX);
    int h = rd8(font), n, i = 0;
    uint8_t col = rd8(g_dg + V_COLOR);
    uint32_t dseg = (uint32_t)rd16(g_dg + V_DESTSEG) << 4;
    n = CopyStr(segbase(S_DS), reg16(R_SI), raw);
    raw[MAXS] = raw[MAXS + 1] = 0;
    Dict_Apply(raw, buf, MAXS * 2);
    buf[MAXS * 2] = buf[MAXS * 2 + 1] = 0;
    wr16(g_dg + V_CURX, (uint16_t)x);
    wr16(g_dg + V_CURY, (uint16_t)y);
    if (g_trace) LogF("描く %d,%d h%d [%s] seg %X %X %X %X si %X font %08X dg %X", x, y, h, buf,
                      DBX_SEGVAL(0), DBX_SEGVAL(1), DBX_SEGVAL(2), DBX_SEGVAL(3), reg16(R_SI), font, g_dg);
    if (y >= 0 && y < 200) {
        uint32_t row = dseg + rd16(g_dg + V_ROWTBL + y * 2);
        while (buf[i]) {
            uint8_t c = buf[i];
            if (c >= 0xA1 && buf[i + 1] >= 0xA1) {
                const uint8_t *g = Font_Glyph(c, buf[i + 1]);
                int off = h >= 10 ? (h - 8) / 2 : 0, r, k;
                {   /* 16 ドットで描き直すための記録（描き先の 320 幅の中の位置） */
                    uint32_t o = rd16(g_dg + V_ROWTBL + y * 2) + off * 320 + x;
                    Hires_Note((int)(o % 320), (int)(o / 320), c, buf[i + 1], col, (uint16_t)(dseg >> 4));
                }
                if (g) for (r = 0; r < 8; r++) {
                    if (y + off + r >= 200) break;
                    for (k = 0; k < 8; k++)
                        if ((g[r] & (0x80 >> k)) && x + k < 320)
                            Put(row + (off + r) * 320 + x + k, col);
                }
                x += 8; i += 2; continue;
            }
            i++;
            if (c == 0x20) { x += rd8(font + 1) + 1; continue; }
            if (c < 0x20 || (c & 0x80)) continue;
            {
                int cw = rd8(font + (c - 0x20)), r, k;
                uint32_t gp = font + 0x5F + (uint32_t)(c - 0x21) * h * 2;
                for (r = 0; r < h; r++) {
                    uint16_t bits = rd16(gp + r * 2);
                    if (y + r >= 200) break;
                    for (k = 0; k < cw && k < 16; k++)
                        if ((bits & (0x8000 >> k)) && x + k < 320) Put(row + r * 320 + x + k, col);
                }
                x += cw;
            }
        }
    }
    wr16(g_dg + V_CURX, (uint16_t)x);
    set16(R_SI, (uint16_t)(reg16(R_SI) + n));
    set16(R_AX, 0);
    return 0;
}

/* ---------- 折り返し（1633F の置き換え） ----------
   DS:SI の文を、1 行 [137E] バイト（0 なら 60）以内に収まるよう LF を入れる。
   原作は空白を LF に置き換えるだけなので、空白のない日本語は字の間に LF を差し込む。 */
static int IsEuc(const uint8_t *s) { return s[0] >= 0xA1 && s[1] >= 0xA1; }

/* 行頭に来てはいけない字（。、」など） */
static int NoHead(const uint8_t *s)
{
    static const char *list = "\xA1\xA2\xA1\xA3\xA1\xA4\xA1\xA5\xA1\xA6\xA1\xA7\xA1\xA8\xA1\xA9\xA1\xAA\xA1\xBC\xA1\xD7\xA1\xD9\xA1\xCB\xA1\xDB\xA1\xD3\xA1\xD5\xA1\xC4\xA1\xC5\xA4\xA1\xA4\xA3\xA4\xA5\xA4\xA7\xA4\xA9\xA4\xC3\xA4\xE3\xA4\xE5\xA4\xE7\xA5\xA1\xA5\xA3\xA5\xA5\xA5\xA7\xA5\xA9\xA5\xC3\xA5\xE3\xA5\xE5\xA5\xE7\xA1\xC1";  /* EUC: 、。，．・：；？！ー」』）】〉》…‥ぁぃぅぇぉっゃゅょァィゥェォッャュョ〜 */
    const uint8_t *p = (const uint8_t *)list;
    for (; *p; p += 2) if (p[0] == s[0] && p[1] == s[1]) return 1;
    return 0;
}
static int NoTail(const uint8_t *s)
{
    static const char *list = "\xA1\xD6\xA1\xD8\xA1\xCA\xA1\xDA\xA1\xD2\xA1\xD4";  /* EUC: 「『（【〈《 */
    const uint8_t *p = (const uint8_t *)list;
    for (; *p; p += 2) if (p[0] == s[0] && p[1] == s[1]) return 1;
    return 0;
}

#define WRAPMAX 4900
static uint32_t CB_Wrap(void)
{
    static uint8_t raw[WRAPMAX + 4], in[WRAPMAX * 2 + 4], out[WRAPMAX * 3];
    uint32_t seg = segbase(S_DS);
    uint16_t si = reg16(R_SI);
    int lim = rd8(g_dg + 0x137E), n = 0, o = 0, line = 0, i;
    if (!lim) { lim = 60; wr8(g_dg + 0x137E, 60); }
    while (n < WRAPMAX && (raw[n] = rd8(seg + (uint16_t)(si + n))) != 0) n++;
    raw[n] = raw[n + 1] = 0;
    n = Dict_Apply(raw, in, WRAPMAX * 2);
    in[n] = in[n + 1] = 0;
    for (i = 0; i < n; ) {
        uint8_t c = in[i];
        if (c == 0x0A || c == 0x0D) { out[o++] = c; line = 0; i++; continue; }
        if (c == ' ') {
            /* 次の語の長さ */
            int j = i + 1, w = 0;
            if (line == 0) { i++; continue; }
            if (IsEuc(in + j)) w = 2;
            else while (in[j + w] && in[j + w] != ' ' && in[j + w] != 0x0A && !(in[j + w] >= 0xA1)) w++;
            if (line + 1 + w > lim) { out[o++] = 0x0A; line = 0; }
            else { out[o++] = ' '; line++; }
            i++; continue;
        }
        if (IsEuc(in + i)) {
            int need = 2;
            /* 行末に置けない字はその次と一緒に送る */
            if (NoTail(in + i) && IsEuc(in + i + 2)) need = 4;
            if (line > 0 && line + need > lim && !NoHead(in + i)) { out[o++] = 0x0A; line = 0; }
            out[o++] = in[i]; out[o++] = in[i + 1]; line += 2; i += 2;
            continue;
        }
        {   /* 英数字の語（空白・日本語の手前まで） */
            int w = 0;
            while (in[i + w] && in[i + w] != ' ' && in[i + w] != 0x0A && in[i + w] != 0x0D && !IsEuc(in + i + w)) w++;
            if (w == 0) { out[o++] = in[i++]; line++; continue; }
            if (line > 0 && line + w > lim) { out[o++] = 0x0A; line = 0; }
            memcpy(out + o, in + i, w); o += w; line += w; i += w;
        }
    }
    if (o > WRAPMAX) o = WRAPMAX;
    for (i = 0; i < o; i++) wr8(seg + (uint16_t)(si + i), out[i]);
    wr8(seg + (uint16_t)(si + o), 0);
    if (g_trace) LogF("折り返し lim %d %d→%d バイト", lim, n, o);
    return 0;
}

/* ---------- 発見と書き換え ---------- */
static void PutCB(uint32_t a, int cb)
{
    wr8(a, 0xFE); wr8(a + 1, 0x38); wr16(a + 2, (uint16_t)cb); wr8(a + 4, 0xC3);
}

void Game_Init(void)
{
    char p[MAX_PATH];
    cbW = AllocCallback(CB_Width);
    cbD = AllocCallback(CB_Draw);
    cbR = AllocCallback(CB_Wrap);
    wsprintfA(p, "%s\\dict.bin", g_dir);
    Dict_Load(p);
    wsprintfA(p, "%s\\names.bin", g_dir);
    Names_Load(p);
    /* 試験: ARENAJP\\dicttest.txt があれば、各行を辞書に通して記録に書く */
    wsprintfA(p, "%s\\dicttest.txt", g_dir);
    {
        uint32_t sz; uint8_t *t = ReadAll(p, &sz);
        if (t) {
            uint32_t a = 0, b;
            static uint8_t ln[512], ob[1100];
            while (a < sz) {
                b = a;
                while (b < sz && t[b] != '\r' && t[b] != '\n') b++;
                if (b > a && b - a < sizeof ln) {
                    memcpy(ln, t + a, b - a); ln[b - a] = 0;
                    Dict_Apply(ln, ob, sizeof ob);
                    LogF("DT %s => %s", ln, ob);
                }
                a = b + 1;
            }
        }
    }
    wsprintfA(p, "%s\\exe_ja.bin", g_dir);
    g_exe = ReadAll(p, &g_exesize);
    LogF("コールバック %d %d、exe_ja %s", cbW, cbD, g_exe ? "あり" : "なし");
}

void Game_Tick(void)
{
    static const uint8_t w0[] = { 0x1E, 0x06, 0x57, 0x56, 0x1E, 0x07, 0x8B, 0xFE };
    static const uint8_t d0[] = { 0x55, 0x06, 0x57, 0x1E, 0x50 };
    static const uint8_t r0[] = { 0x56, 0x56, 0x8B, 0xFE, 0x9A };
    static const uint8_t f0[] = { 0x80, 0x3C, 0x7A, 0x76, 0x04 };
    uint16_t psp = rd16(0xB30);
    uint16_t ls = (uint16_t)(psp + 0x10);
    uint32_t base = (uint32_t)ls << 4;
    if (g_base) {
        if (base == g_base && (g_nohook || rd8(g_base + A_DRAWLINE) == 0xFE)) return;
        g_base = 0;
    }
    if (cbW < 0 || cbD < 0) return;
    if (base + 0x4A970 > 0xA0000) return;
    if (memcmp(lin(base + A_FONTNAME), "font_a.dat", 10)) return;
    if (rd16(base + A_DRAWLINE + 6) != (uint16_t)(DG_SEG + ls)) return;
    if (memcmp(lin(base + A_STRWIDTH), w0, sizeof w0) || memcmp(lin(base + A_DRAWLINE), d0, sizeof d0)) return;
    if (memcmp(lin(base + A_WRAP), r0, sizeof r0) || memcmp(lin(base + A_FILTER), f0, sizeof f0)) return;
    if (g_nopatch) return;
    g_base = base;
    g_dg = (uint32_t)(DG_SEG + ls) << 4;
    if (!g_nostr) PatchStrings();
    if (!g_nohook) {
        PutCB(base + A_STRWIDTH, cbW);
        PutCB(base + A_DRAWLINE, cbD);
        PutCB(base + A_WRAP, cbR);
        wr8(base + A_FILTER + 3, 0xEB);
    }
    LogF("ACD を発見 PSP=%04X 先頭=%05X", psp, base);
}
