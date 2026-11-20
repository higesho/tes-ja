/* 日本語の字を、DOSBox が拡大して窓へ送る直前に 16 ドットの字形で描き直す
   ・CB_Draw が 8 ドットの字を描くたびに、画面上の位置・字・色を記録する（Hires_Note）
   ・RENDER_EndUpdate が GFX_EndUpdate を呼ぶところで、拡大前の画面（scalerSourceCache）に
     その 8 ドットの字が本当にあるかを確かめ、あれば拡大後の出力に 16 ドットの字を描く
   ・ゲーム側の画面は 8 ドットのままなので、箱の大きさや折り返しは変わらない */
#include "arenajp.h"
#include <stdlib.h>

/* ---- DOSBox 0.74-2 の render（render.h の Render_t）と関数 ---- */
#define R_SRC_WIDTH     (*(volatile uint32_t *)0x1EF1670)
#define R_SRC_HEIGHT    (*(volatile uint32_t *)0x1EF1678)
#define R_OUTMODE       (*(volatile uint32_t *)0x1EF16BC)   /* 0=8 1=15 2=16 3=32 */
#define R_CACHEPITCH    (*(volatile uint32_t *)0x1EF16E4)
#define R_CACHEREAD     (*(uint8_t * volatile *)0x1EF16E8)
#define R_LUT16         ((volatile uint16_t *)0x1EF1AF8)
#define R_LUT32         ((volatile uint32_t *)0x1EF1AF8)
#define SCALER_ASPECT   ((volatile uint8_t *)0x23FC1C0)
#define GFX_STARTUPDATE 0x51FEE0
#define CALL_ENDUPDATE  0x5164C4                            /* call GFX_EndUpdate（RENDER_EndUpdate の中） */
#define GFX_ENDUPDATE   0x520390

typedef int (__cdecl *StartFn)(uint8_t **, uint32_t *);
typedef void (__cdecl *EndFn)(const uint16_t *);
static StartFn g_start;          /* GFX_StartUpdate の元（入口を写した踏み台） */
static uint8_t *g_out;           /* この画面の出力の先頭 */
static uint32_t g_outpitch;
static int g_xscale;             /* 横の倍率（出力と色表を突き合わせて決める） */
static uint8_t *g_font16;

/* ---- 字の記録 ---- */
typedef struct { int16_t x, y; uint8_t c1, c2, col, used; uint32_t last; uint16_t seg; uint8_t painted; } Glyph;
/* 描き先（セグメント）ごとの、画面に写されたときのずれ */
typedef struct { uint16_t seg; int16_t dx, dy; uint8_t ok; } Disp;
#define MAXD 8
static Disp g_disp[MAXD];
#define MAXG 2048
static Glyph g_gl[MAXG];
static int16_t *g_at;            /* 320x200 の位置 → 記録の番号+1 */
static int g_next;

void Hires_Note(int sx, int sy, uint8_t c1, uint8_t c2, uint8_t col, uint16_t seg)
{
    int i;
    if (!g_font16 || !g_at || sx < 0 || sy < 0 || sx + 8 > 320 || sy + 8 > 200) return;
    i = g_at[sy * 320 + sx] - 1;
    if (i < 0) {
        /* 古い記録を使い回す */
        i = g_next; g_next = (g_next + 1) % MAXG;
        if (g_gl[i].used) g_at[g_gl[i].y * 320 + g_gl[i].x] = 0;
        g_at[sy * 320 + sx] = (int16_t)(i + 1);
    }
    g_gl[i].x = (int16_t)sx; g_gl[i].y = (int16_t)sy;
    g_gl[i].c1 = c1; g_gl[i].c2 = c2; g_gl[i].col = col; g_gl[i].used = 1;
    g_gl[i].last = GetTickCount(); g_gl[i].seg = seg;
}

/* ---- 出力へ書く ---- */
static __inline uint32_t LutOf(uint8_t c) { return R_OUTMODE == 3 ? R_LUT32[c] : R_LUT16[c]; }
static __inline void PutOut(int x, int y, uint32_t v)
{
    uint8_t *p = g_out + y * g_outpitch;
    if (R_OUTMODE == 3) ((uint32_t *)p)[x] = v; else ((uint16_t *)p)[x] = (uint16_t)v;
}
static __inline uint32_t GetOut(int x, int y)
{
    uint8_t *p = g_out + y * g_outpitch;
    return R_OUTMODE == 3 ? ((uint32_t *)p)[x] : ((uint16_t *)p)[x];
}

/* 横の倍率を決める: 出力の 1 行と拡大前の 1 行を見比べて、いちばん合う倍率 */
static int GuessXScale(const uint8_t *src, uint32_t cpitch, const int *rowstart, int h, int w)
{
    int k, best = 0, bestn = -1000000, y;
    for (k = 1; k <= 4; k++) {
        int n = 0;
        for (y = 10; y < h; y += 37) {
            int x;
            if (rowstart[y] < 0) continue;
            for (x = 1; x + 1 < w; x++) {
                const uint8_t *s = src + y * cpitch;
                /* 色の境目だけを見る（平らな所はどの倍率でも合ってしまう） */
                if (s[x] == s[x - 1]) continue;
                if (GetOut(x * k, rowstart[y]) == LutOf(s[x])) n++; else n--;
            }
        }
        if (n > bestn) { bestn = n; best = k; }
    }
    /* 境目が少なすぎる（真っ黒な画面など）ときは決めずに次の画面で測る */
    return bestn >= 20 ? best : 0;
}

static const uint8_t *g_src;
static uint32_t g_cp;
static int g_sxm, g_sym, g_h;
static int g_rowstart[1024 + 1];

/* ---- マウスの矢印（ゲームが自分で描く） ----
   DGROUP の [8F7C],[8F7E] = 描いた左上、[8F8E],[8F90] = 切り取った大きさ、
   [8F88] = 切り取った絵（幅 w の詰めた行、色 0 は透明）。矢印の点を 320x200 の印にする */
#define D_CUR_SHOWN 0xA902
#define D_CUR_X     0x8F7C
#define D_CUR_Y     0x8F7E
#define D_CUR_W     0x8F8E
#define D_CUR_H     0x8F90
#define D_CUR_IMG   0x8F88
static uint8_t g_cur[320 * 200];          /* bit0/bit1 = 偶数・奇数の画面で付けた印（直前 2 画面ぶんを合わせて使う） */
static int g_cx0, g_cy0, g_cx1, g_cy1;     /* この画面の矢印の範囲（記録用） */
static int g_rc[2][4];                     /* 印ごとの範囲 */
static int g_frame;

/* [A902] bit0 は「作業用の画面に矢印を描いてある」印で、画面へ写した後は下ろされるため、
   矢印が見えていても 0 のことが多い。印は見ず、描いた位置を直前の画面の分と合わせて使う。
   （本当に隠れているときに印を付けても、Match・Paint は字の点が見えていればそのまま扱う） */
static void CursorMask(void)
{
    uint32_t dg = Game_DG(), img;
    int x, y, cx, cy, w, h, iw, s = g_frame & 1;
    uint8_t bit = (uint8_t)(1 << s);
    int *rc = g_rc[s];
    g_frame++;
    for (y = rc[1]; y < rc[3]; y++) for (x = rc[0]; x < rc[2]; x++) g_cur[y * 320 + x] &= (uint8_t)~bit;
    rc[0] = rc[1] = rc[2] = rc[3] = 0;
    g_cx0 = g_cy0 = g_cx1 = g_cy1 = 0;
    if (!dg) return;
    cx = rd16(dg + D_CUR_X); cy = rd16(dg + D_CUR_Y);
    w = iw = rd16(dg + D_CUR_W); h = rd16(dg + D_CUR_H);
    if (w <= 0 || h <= 0 || w > 16 || h > 16 || cx >= 320 || cy >= 200) return;
    if (cx + w > 320) w = 320 - cx;
    if (cy + h > 200) h = 200 - cy;
    img = farptr(dg + D_CUR_IMG);
    if (!img || img + 256 > 0xA0000) return;
    for (y = 0; y < h; y++)
        for (x = 0; x < w; x++)
            if (rd8(img + y * iw + x)) g_cur[(cy + y) * 320 + cx + x] |= bit;
    rc[0] = g_cx0 = cx; rc[1] = g_cy0 = cy; rc[2] = g_cx1 = cx + w; rc[3] = g_cy1 = cy + h;
}

/* 拡大前の画面の (x,y) に、この字の 8 ドットの形がそのままあるか（矢印の点は数えない） */
static int Match(const Glyph *g, const uint8_t *m, int x, int y)
{
    int r, k, on = 0, hid = 0;
    if (x < 0 || y < 0 || x + 8 > 320 || y + 8 > 200) return 0;
    for (r = 0; r < 8; r++) {
        const uint8_t *row = g_src + (y + r) * g_sym * g_cp + x * g_sxm;
        const uint8_t *cur = g_cur + (y + r) * 320 + x;
        for (k = 0; k < 8; k++)
            if (m[r] & (0x80 >> k)) {
                if (row[k * g_sxm] == g->col) on++;
                else if (cur[k]) hid++;
                else return 0;
            }
    }
    /* 1 = ある、2 = 点が全部矢印の下で分からない（記録は残す）、0 = ない */
    return on > 0 ? 1 : hid > 0 ? 2 : 0;
}

static Disp *DispOf(uint16_t seg, int make)
{
    int i;
    for (i = 0; i < MAXD; i++) if (g_disp[i].seg == seg) return &g_disp[i];
    if (!make) return NULL;
    for (i = 0; i < MAXD; i++) if (!g_disp[i].seg) { g_disp[i].seg = seg; g_disp[i].ok = 0; return &g_disp[i]; }
    g_disp[0].seg = seg; g_disp[0].ok = 0; return &g_disp[0];
}

/* 画面全体からこの字を探す。見つかった位置のずれが、同じ描き先のほかの字にも当てはまるときだけ採る */
static int Search(const Glyph *g, const uint8_t *m, int *dx, int *dy)
{
    int x, y, i, r0 = -1, k0 = 0;
    for (i = 0; i < 8 && r0 < 0; i++) for (k0 = 0; k0 < 8; k0++) if (m[i] & (0x80 >> k0)) { r0 = i; break; }
    if (r0 < 0) return 0;
    for (y = 0; y + 8 <= 200; y++) {
        const uint8_t *row = g_src + (y + r0) * g_sym * g_cp;
        for (x = 0; x + 8 <= 320; x++) {
            int ddx, ddy, n = 0, bad = 0;
            if (row[(x + k0) * g_sxm] != g->col) continue;
            if (Match(g, m, x, y) != 1) continue;
            ddx = x - g->x; ddy = y - g->y;
            if (!ddx && !ddy) continue;
            for (i = 0; i < MAXG && n + bad < 4; i++) {
                const Glyph *o = &g_gl[i];
                const uint8_t *om;
                if (!o->used || o == g || o->seg != g->seg) continue;
                om = Font_Glyph(o->c1, o->c2);
                if (om && Match(o, om, o->x + ddx, o->y + ddy) == 1) n++; else bad++;
            }
            if (!bad) { *dx = ddx; *dy = ddy; return 1; }
        }
    }
    return 0;
}

/* (x,y) の 8 ドットの字を、拡大後の出力に 16 ドットの字で描く */
static void Paint(const Glyph *g, const uint8_t *m, int x, int y)
{
    int cx, cy, cw, ch, oy0, oy1, k, t;
    const uint8_t *f16;
    cx = x * g_sxm * g_xscale; cw = 8 * g_sxm * g_xscale;
    t = y * g_sym; while (t < g_h && g_rowstart[t] < 0) t++; oy0 = g_rowstart[t];
    t = (y + 8) * g_sym; while (t < g_h && g_rowstart[t] < 0) t++; oy1 = g_rowstart[t];
    ch = oy1 - oy0;
    if (ch <= 0 || cw <= 0) return;
    f16 = g_font16 + (((g->c1 - 0xA1) * 94) + (g->c2 - 0xA1)) * 32;
    for (cy = 0; cy < ch; cy++) {
        int fr = cy * 16 / ch;                   /* 16 ドットの行 */
        int lr = cy * 8 / ch;                    /* 8 ドットの行 */
        uint16_t bits = (uint16_t)((f16[fr * 2] << 8) | f16[fr * 2 + 1]);
        const uint8_t *srow = g_src + (y + lr) * g_sym * g_cp + x * g_sxm;
        const uint8_t *cur = g_cur + (y + lr) * 320 + x;
        for (k = 0; k < cw; k++) {
            int fc = k * 16 / cw, lc = k * 8 / cw;
            uint32_t v;
            if (cur[lc]) {                       /* 矢印かもしれない点は、字の点が見えているときだけ描く */
                if (!(m[lr] & (0x80 >> lc)) || srow[lc * g_sxm] != g->col) continue;
            }
            if (bits & (0x8000 >> fc)) v = LutOf(g->col);
            else if (m[lr] & (0x80 >> lc)) {
                /* 8 ドットの字の点だった所は、同じ行の字でない隣の色で埋める */
                int d, c = -1;
                for (d = 1; d < 8 && c < 0; d++) {
                    if (lc - d >= 0 && !(m[lr] & (0x80 >> (lc - d)))) c = srow[(lc - d) * g_sxm];
                    else if (lc + d < 8 && !(m[lr] & (0x80 >> (lc + d)))) c = srow[(lc + d) * g_sxm];
                }
                if (c < 0) c = srow[7 * g_sxm];
                v = LutOf((uint8_t)c);
            } else v = LutOf(srow[lc * g_sxm]);
            PutOut(cx + k, oy0 + cy, v);
        }
    }
}

static void DrawAll(void)
{
    uint32_t h = R_SRC_HEIGHT, w = R_SRC_WIDTH, cp = R_CACHEPITCH;
    int y, oy = 0, i, searched = 0;
    DWORD now = GetTickCount();
    if (!g_out || h == 0 || h > 1024 || w < 320 || R_OUTMODE == 0) return;
    g_src = R_CACHEREAD - cp * h; g_cp = cp; g_h = (int)h;
    for (y = 0; y < (int)h; y++) { int n = SCALER_ASPECT[y]; g_rowstart[y] = n ? oy : -1; oy += n; }
    g_rowstart[h] = oy;
    {   static uint32_t lw, lh, lp;
        if (w != lw || h != lh || g_outpitch != lp) { g_xscale = 0; lw = w; lh = h; lp = g_outpitch; }
    }
    if (!g_xscale) { g_xscale = GuessXScale(g_src, cp, g_rowstart, h, w); if (g_xscale) LogF("倍率 %d src %ux%u 出力の行数 %d", g_xscale, w, h, oy); }
    if (g_xscale <= 0) return;
    g_sxm = w / 320; if (g_sxm < 1) g_sxm = 1;
    g_sym = h / 200; if (g_sym < 1) g_sym = 1;
    CursorMask();
    for (i = 0; i < MAXG; i++) {
        Glyph *g = &g_gl[i];
        const uint8_t *m;
        Disp *d;
        int r;
        if (!g->used) continue;
        m = Font_Glyph(g->c1, g->c2);
        if (!m) { g->used = 0; continue; }
        r = Match(g, m, g->x, g->y);
        if (g_trace && r == 0 && g->painted) {
            int rr, kk, bad = 0, badin = 0, ok = 0;
            for (rr = 0; rr < 8; rr++) for (kk = 0; kk < 8; kk++) if (m[rr] & (0x80 >> kk)) {
                int px = g->x + kk, py = g->y + rr;
                if (g_src[py * g_sym * g_cp + px * g_sxm] == g->col) ok++;
                else if (px >= g_cx0 - 16 && px < g_cx1 + 16 && py >= g_cy0 - 16 && py < g_cy1 + 16) badin++; else bad++;
            }
            { uint32_t dg = Game_DG();
              LogF("消えた %d,%d ok %d 近く %d 遠く %d 矢印 %d,%d-%d,%d dg %X 表示 %X 位置 %d,%d 大きさ %d,%d 絵 %X", g->x, g->y, ok, badin, bad, g_cx0, g_cy0, g_cx1, g_cy1,
                   dg, dg ? rd16(dg + D_CUR_SHOWN) : 0, dg ? rd16(dg + D_CUR_X) : 0, dg ? rd16(dg + D_CUR_Y) : 0,
                   dg ? rd16(dg + D_CUR_W) : 0, dg ? rd16(dg + D_CUR_H) : 0, dg ? farptr(dg + D_CUR_IMG) : 0); }
        }
        g->painted = (uint8_t)(r == 1);
        if (r == 1) { g->last = now; Paint(g, m, g->x, g->y); continue; }
        if (r == 2) { g->last = now; continue; }
        /* 別の所へ写されているかもしれない */
        d = DispOf(g->seg, 0);
        if (d && d->ok) {
            r = Match(g, m, g->x + d->dx, g->y + d->dy);
            if (r == 1) { g->last = now; Paint(g, m, g->x + d->dx, g->y + d->dy); continue; }
            if (r == 2) { g->last = now; continue; }
        }
        if (!searched && now - g->last < 10000) {
            int dx, dy;
            searched = 1;
            if (Search(g, m, &dx, &dy)) {
                d = DispOf(g->seg, 1); d->dx = (int16_t)dx; d->dy = (int16_t)dy; d->ok = 1;
                if (g_trace) LogF("ずれ seg %04X: %d,%d", g->seg, dx, dy);
                g->last = now; Paint(g, m, g->x + dx, g->y + dy);
                continue;
            }
        }
        if (now - g->last > 10000) { g_at[g->y * 320 + g->x] = 0; g->used = 0; }
    }
}

/* ---- 横取り ---- */
static int __cdecl MyStart(uint8_t **pix, uint32_t *pitch)
{
    int r = g_start(pix, pitch);
    if (r & 0xFF) { g_out = *pix; g_outpitch = *pitch; }
    return r;
}

static void __cdecl MyEnd(const uint16_t *changed)
{
    if (changed && g_out) {
        __try { DrawAll(); } __except (EXCEPTION_EXECUTE_HANDLER) { g_xscale = -1; }
    }
    g_out = NULL;
    ((EndFn)GFX_ENDUPDATE)(changed);
}

int Hires_Install(const char *fontpath)
{
    static const uint8_t s0[] = { 0x83, 0xEC, 0x1C, 0x80, 0x3D, 0x31, 0x23, 0xEF, 0x01, 0x00 };
    uint8_t *p = (uint8_t *)GFX_STARTUPDATE, *q = (uint8_t *)CALL_ENDUPDATE, *t;
    uint32_t size;
    DWORD old;
    if (memcmp(p, s0, sizeof s0) || q[0] != 0xE8 ||
        (uint32_t)(q + 5 + *(int32_t *)(q + 1)) != GFX_ENDUPDATE) return 0;
    g_font16 = ReadAll(fontpath, &size);
    if (!g_font16 || size < 94 * 94 * 32) { free(g_font16); g_font16 = NULL; return 0; }
    g_at = (int16_t *)calloc(320 * 200, sizeof(int16_t));
    /* GFX_StartUpdate の入口 10 バイトを踏み台に写して、入口を MyStart への jmp にする */
    t = (uint8_t *)VirtualAlloc(NULL, 32, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    memcpy(t, s0, 10);
    t[10] = 0xE9; *(int32_t *)(t + 11) = (int32_t)((p + 10) - (t + 15));
    g_start = (StartFn)t;
    VirtualProtect(p, 10, PAGE_EXECUTE_READWRITE, &old);
    p[0] = 0xE9; *(int32_t *)(p + 1) = (int32_t)((uint8_t *)MyStart - (p + 5));
    memset(p + 5, 0x90, 5);
    VirtualProtect(p, 10, old, &old);
    /* RENDER_EndUpdate の call GFX_EndUpdate を MyEnd へ */
    VirtualProtect(q, 5, PAGE_EXECUTE_READWRITE, &old);
    *(int32_t *)(q + 1) = (int32_t)((uint8_t *)MyEnd - (q + 5));
    VirtualProtect(q, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), NULL, 0);
    LogF("16 ドットの描き直しを差し込んだ");
    return 1;
}
