/*
 * The Elder Scrolls II: Daggerfall 日本語化（GOG 版 DOSBox 0.74-2.1 用）
 * DOSBOX\winmm.dll として置く（足すだけ、消せば英語に戻る）。winmm の関数は全部 System の winmm.dll へ回す。
 *
 * - DOSBox の fopen/fread/fseek/ftell/fclose を横取りし、文章のファイル（TEXT.RSC・本・クエストなど）を
 *   DLL に埋め込んだ日本語版に差し替える
 * - FALL.EXE を読むときに、文字列描画（0x12dbcc）・1 字の幅（0x5a442）・文字列の幅（0x5a4a9）の頭を
 *   DOSBox のコールバック命令（FE 38 xx xx ; C3）に書き換え、ここで日本語を描く
 * - 画面の日本語は独自の 2 バイト: 前 0x80-0xAF、後 0xB0-0xEF（字の番号 = (前-0x80)*64 + (後-0xB0)）。
 *   0xF0 以上は Daggerfall の文章の制御符号なので使わない
 */
#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32; typedef int16_t s16;

/* ===================== DOSBox 0.74-2.1（GOG, md5 2318a446）の番地 ===================== */
#define DB_LOOPCALL       0x004017eau  /* Normal_Loop: call [eax*4+CallBack_Handlers] */
#define DB_CB_HANDLERS    0x0075b460u  /* CallBack_Handlers[128] */
#define DB_CB_ILLEGAL     0x00415e30u  /* illegal_handler */
#define DB_REGS           0x0075b1e0u  /* cpu_regs: eax ecx edx ebx esp ebp esi edi, eip, flags */
#define DB_SEGPHYS        0x0075b110u  /* Segs.phys[es cs ss ds fs gs] */
#define DB_MEMBASE        0x01d4a380u  /* HostPt MemBase */
#define DB_MEMPAGES       0x01d4a3c8u  /* memory.pages */
#define DB_PAGING_CR3     0x0075b6ccu  /* paging.base.addr */
#define DB_TLB_READ       0x0075b6d0u  /* paging.tlb.read[1M] */
#define DB_TLB_WRITE      0x00b5b6d0u
#define DB_PAGING_ON      0x01b7bb14u  /* paging.enabled */
#define IAT_FOPEN  0x0243198cu
#define IAT_FREAD  0x0243199cu
#define IAT_FSEEK  0x024319a8u
#define IAT_FTELL  0x024319acu
#define IAT_FCLOSE 0x02431974u

/* ===================== FALL.EXE（LE）の既定番地 ===================== */
#define G_DRAWSTR   0x0012dbccu   /* eax=x edx=y ebx=文字列 */
#define G_CHW       0x0005a442u   /* al=字 → eax=送り幅 */
#define G_STRW      0x0005a4a9u   /* eax=文字列 → eax=幅 */
#define G_CHW_FONTREF 0x0005a47eu /* mov eax,[0x12da74] の番地部分（データのずれを読む） */
#define G_ENTRY     0x0009deb4u   /* 入口: jmp 0x9df2c ＋ Watcom の署名 */
#define F_ENTRY     0x000e94b4u
static const u8 orig_entry[6] = {0xeb, 0x76, 0x57, 0x41, 0x54, 0x43};
#define D_FONT      0x0012da74u   /* 今の字体の先頭 */
#define D_SPACEW    0x0012da40u   /* 空白の幅 */
#define D_HEIGHT    0x0012da44u   /* 字の高さ */
#define D_XSP       0x0012da48u   /* 字の間 */
#define D_YSP       0x0012da4cu   /* 行の間 */
#define D_COLOR     0x0012b508u   /* 字の色（1 バイト） */
#define D_CLIP      0x00142940u   /* 左 上 右 下 */
#define D_ROWTAB    0x00142950u   /* 行の先頭 [y] */
#define D_SCRBASE   0x00143550u
/* ファイル上の位置と元の 5 バイト */
/* 旅の地図の「探す」: 入力を受け取った直後（mov ebx,4）。英語の地名を打ったら日本語の地名に置き換える */
#define G_FINDIN    0x0009c80cu
#define F_FINDIN    0x000e7e0cu
#define G_FINDBUF   0x00190fe4u
static const u8 orig_findin[5] = {0xbb, 0x04, 0x00, 0x00, 0x00};
/* 会話の記録欄: プレイヤーの行は先頭バイトに 0x80 を足して印にする（0x16cca）、描くときに見て消す（0x16ee7）。
 * 日本語の 1 字目は 0x80 以上なので取り違えて 1 字目が消える → 日本語の行は 2 バイト目の 0x80 を落として印にする */
#define G_TLMARK    0x00016ccau   /* or byte [eax],0x80 ; mov edx,[ebp-0x18] */
#define F_TLMARK    0x000622cau
static const u8 orig_tlmark[6] = {0x80, 0x08, 0x80, 0x8b, 0x55, 0xe8};
/* mov al,[0x190fe4] の次（番地の再配置を避ける）から and byte [0x190fe4],0x7f の後（0x16f0e）までを飛ばす */
#define G_TLTEST    0x00016eecu   /* and al,0x80 ; and eax,0xff ... */
#define F_TLTEST    0x000624ecu
static const u8 orig_tltest[6] = {0x24, 0x80, 0x25, 0xff, 0x00, 0x00};
#define G_TLBUF     0x00190fe4u
#define F_DRAWSTR   0x001751ccu
#define F_CHW       0x000a5a42u
#define F_STRW      0x000a5aa9u
static const u8 orig_ds[5] = {0x51, 0x55, 0x56, 0x57, 0xa3};
static const u8 orig_cw[5] = {0x55, 0x89, 0xe5, 0x53, 0x51};

/* ===================== ログ ===================== */
static FILE *logfp;
static char dump_path[MAX_PATH];
static void LOG(const char *fmt, ...)
{
    va_list ap;
    if (!logfp) return;
    va_start(ap, fmt); vfprintf(logfp, fmt, ap); va_end(ap);
    fputc('\n', logfp); fflush(logfp);
}

/* ===================== データ（リソースに埋め込み） ===================== */
static const u8 *blob; static u32 blobsize;
static const u8 *find_sec(const char *tag, u32 *size)
{
    u32 p = 8;
    if (!blob) return 0;
    while (p + 8 <= blobsize) {
        u32 sz = *(const u32 *)(blob + p + 4);
        if (memcmp(blob + p, tag, 4) == 0) { if (size) *size = sz; return blob + p + 8; }
        p += 8 + ((sz + 3) & ~3u);
    }
    return 0;
}

/* フォント: [h][fw][hw][0] full[94*94][h] u16, half[96][h] u8 */
typedef struct { int h, fw, hw; const u16 *full; const u8 *half; } JFont;
static JFont jf8, jf12, jf14;
static void load_font(JFont *f, const char *tag)
{
    const u8 *p = find_sec(tag, 0);
    if (!p) { memset(f, 0, sizeof *f); return; }
    f->h = p[0]; f->fw = p[1]; f->hw = p[2];
    f->full = (const u16 *)(p + 4);
    f->half = p + 4 + 94 * 94 * f->h * 2;
}
static const u16 *cmap; static u32 ncmap;   /* 字の番号 → EUC（上位が 1 バイト目） */
static int is_jl(u8 c) { return c >= 0x80 && c <= 0xAF; }
static int is_jt(u8 c) { return c >= 0xB0 && c <= 0xEF; }
static const u16 *jglyph(const JFont *f, u8 a, u8 b)
{
    u32 idx = (u32)(a - 0x80) * 64 + (b - 0xB0);
    u16 e; int ku, ten;
    if (!cmap || idx >= ncmap || !f->full) return 0;
    e = cmap[idx];
    ku = (e >> 8) - 0xA1; ten = (e & 0xff) - 0xA1;
    if (ku < 0 || ku >= 94 || ten < 0 || ten >= 94) return 0;
    return f->full + (ku * 94 + ten) * f->h;
}

/* 差し替えるファイル: [名前 32][大きさ u32][中身] の並び（名前は "ARENA2\TEXT.RSC" の形、大文字） */
typedef struct { const char *name; const u8 *data; u32 size; } RFile;
static RFile rfiles[1024]; static int nrfiles;
static void load_files(void)
{
    u32 n, p = 0;
    const u8 *s = find_sec("FILE", &n);
    if (!s) return;
    while (p + 36 <= n && nrfiles < 1024) {
        u32 sz = *(const u32 *)(s + p + 32);
        rfiles[nrfiles].name = (const char *)(s + p);
        rfiles[nrfiles].size = sz;
        rfiles[nrfiles].data = s + p + 36;
        nrfiles++;
        p += 36 + ((sz + 3) & ~3u);
    }
}

/* ===================== ゲームのメモリ ===================== */
/* CauseWay の仮想記憶でページングが有効なことがある。論理番地は DOSBox の TLB か、ページ表をたどって引く */
static u8 *MB(void) { return *(u8 **)DB_MEMBASE; }
static u32 MSIZE(void) { return (*(u32 *)DB_MEMPAGES) * 4096u; }
static u32 phys32(u32 a) { return (MB() && a + 4 <= MSIZE()) ? *(u32 *)(MB() + a) : 0; }
static u32 lp_page = 0xffffffff; static u8 *lp_host;
static u8 *Lw(u32 lin, int write)
{
    u32 page = lin >> 12;
    u8 *r;
    if (!MB()) return 0;
    if (page == lp_page && !write) return lp_host + (lin & 0xfff);
    r = (write ? (u8 **)DB_TLB_WRITE : (u8 **)DB_TLB_READ)[page];
    if (r) r += (lin & ~0xfffu);
    else if (!*(u8 *)DB_PAGING_ON) r = (lin < MSIZE()) ? MB() + (lin & ~0xfffu) : 0;
    else {
        u32 cr3 = *(u32 *)DB_PAGING_CR3;
        u32 pde = phys32(cr3 + ((lin >> 22) << 2)), pte;
        if (!(pde & 1)) return 0;
        pte = phys32((pde & ~0xfffu) + (((lin >> 12) & 0x3ff) << 2));
        if (!(pte & 1)) return 0;
        if ((pte & ~0xfffu) >= MSIZE()) return 0;
        r = MB() + (pte & ~0xfffu);
    }
    if (!write) { lp_page = page; lp_host = r; }
    return r + (lin & 0xfff);
}
static void L_flush(void) { lp_page = 0xffffffff; }
static u32 *R(void) { return (u32 *)DB_REGS; }
static u32 dsbase(void) { return ((u32 *)DB_SEGPHYS)[3]; }
static u32 csbase(void) { return ((u32 *)DB_SEGPHYS)[1]; }
/* ゲームの番地（DS からの位置） */
static u8 rd8(u32 a) { u8 *p = Lw(dsbase() + a, 0); return p ? *p : 0; }
static u16 rd16(u32 a) { return (u16)(rd8(a) | rd8(a + 1) << 8); }
static u32 rd32(u32 a) { return (u32)rd16(a) | (u32)rd16(a + 2) << 16; }
static void wr8(u32 a, u8 v) { u8 *p = Lw(dsbase() + a, 1); if (p) *p = v; }
static u8 crd8(u32 a) { u8 *p = Lw(csbase() + a, 0); return p ? *p : 0; }

/* ===================== ゲームのコードの位置 ===================== */
static int cb_drawstr, cb_chw, cb_strw;
static int located;
static u32 dcode, ddata;   /* 実行時の番地 - 既定の番地（コード=obj1、データ=obj2） */
static u32 D(u32 x) { return x + ddata; }
static int locate(void)
{
    u32 eip = R()[8], at = eip - 4;
    int cb = crd8(eip - 2) | crd8(eip - 1) << 8;
    if (crd8(at) != 0xFE || crd8(at + 1) != 0x38) return 0;
    /* obj1（コード）と obj2（描画とデータ）は別々にずれて置かれる */
    if (cb == cb_drawstr) {
        ddata = at - G_DRAWSTR;
    } else {
        u32 v, a;
        if (cb == cb_chw) dcode = at - G_CHW;
        else if (cb == cb_strw) dcode = at - G_STRW;
        else return 0;
        a = G_CHW_FONTREF + dcode;
        v = crd8(a) | crd8(a + 1) << 8 | crd8(a + 2) << 16 | (u32)crd8(a + 3) << 24;
        ddata = v - D_FONT;
    }
    located = 1;
    LOG("ゲームの位置 code+%08x data+%08x cs=%08x ds=%08x", dcode, ddata, csbase(), dsbase());
    return 1;
}

/* ===================== 起動直後: EXE の文字列の差し替え ===================== */
/* 入口（jmp と Watcom の署名）を FE 38 cb ; EB 72（元の飛び先へ）に書き換えてある */
static int cb_entry;
static u32 d3;                 /* obj3 のずれ */
static void wr32(u32 a, u32 v) { wr8(a, (u8)v); wr8(a + 1, (u8)(v >> 8)); wr8(a + 2, (u8)(v >> 16)); wr8(a + 3, (u8)(v >> 24)); }
static u32 delta_of(u32 a) { return a < 0xc0000u ? dcode : a < 0x170000u ? ddata : d3; }
static u32 cb_entry_fn(void)
{
    u32 eip = R()[8], at = eip - 4, n, i, ok = 0, bad = 0;
    const u32 *k, *rel;
    const u8 *blob3;
    L_flush();
    if (crd8(at) != 0xFE || crd8(at + 1) != 0x38) { LOG("入口の位置が変"); return 0; }
    dcode = at - G_ENTRY;
    ddata = rd32(G_CHW_FONTREF + dcode) - D_FONT;
    located = 1;
    k = (const u32 *)find_sec("EXEK", 0);
    blob3 = find_sec("EXEB", &n);
    if (!k || !blob3) { LOG("EXE の文字列なし code+%08x data+%08x", dcode, ddata); return 0; }
    d3 = rd32(k[0] + dcode) - k[1];
    LOG("入口 code+%08x data+%08x obj3+%08x", dcode, ddata, d3);
    for (i = 0; i < n; i++) wr8(k[2] + d3 + i, blob3[i]);
    rel = (const u32 *)find_sec("EXER", &n);
    for (i = 0; rel && i + 3 <= n / 4; i += 3) {
        u32 site = rel[i] + delta_of(rel[i]);
        if (rd32(site) != rel[i + 1] + d3) { bad++; continue; }
        wr32(site, k[2] + rel[i + 2] + d3);
        ok++;
    }
    L_flush();
    LOG("EXE の文字列: 張り替え %u、合わない %u", ok, bad);
    return 0;
}

/* ===================== 字の描き方 ===================== */
static const JFont *pick_jf(int h)
{
    if (h >= 13 && jf14.full) return &jf14;
    if (h >= 10 && jf12.full) return &jf12;
    return &jf8;
}
static int jadv(const JFont *f) { return f == &jf8 ? 8 : f->fw; }

typedef struct { s32 cl, ct, cr, cb; u32 scr; u8 color; } Ctx;
static void getctx(Ctx *c)
{
    c->cl = (s32)rd32(D(D_CLIP)); c->ct = (s32)rd32(D(D_CLIP + 4));
    c->cr = (s32)rd32(D(D_CLIP + 8)); c->cb = (s32)rd32(D(D_CLIP + 12));
    c->scr = rd32(D(D_SCRBASE));
    c->color = rd8(D(D_COLOR));
}
static void putpx(const Ctx *c, s32 x, s32 y)
{
    if (x < c->cl || x >= c->cr || y < c->ct || y >= c->cb) return;
    wr8(rd32(D(D_ROWTAB) + (u32)y * 4) + c->scr + (u32)x, c->color);
}
/* 元の字体の 1 字（16bit 行、高さ h） */
static void blit_orig(const Ctx *c, u32 gl, int w, int h, s32 x, s32 y)
{
    int i, j;
    for (j = 0; j < h; j++) {
        u16 row = rd16(gl + j * 2);
        if (!row) continue;
        for (i = 0; i < w && i < 16; i++) if ((row << i) & 0x8000) putpx(c, x + i, y + j);
    }
}
/* ===================== 細かい字（拡大後の画面に 16 ドットの字を重ねる） ===================== */
/* 8 ドットの日本語を描いた位置・字・色を覚えておき、DOSBox が 1 行を拡大したあと、
   元の画面にまだその字があれば（点と色が一致すれば）、拡大後の 2 行に 16 ドットの字の行を描き直す */
#define HI_MAX 6000
typedef struct { s16 x, y; u8 a, b, color, used, ok, perm; u32 seen, seq; u8 vm[8]; u16 owner; u8 drawn, badrows, behind; } HiEnt;   /* behind: 先に描いた字の下に回っている（後から「空いた所だけ」に描かれた影） */   /* badrows: 合わなかった行（8 行ぶんの印）。どれかの行が合わない間は字全体を描かない */   /* vm: 字の点のうち確かめる点（絵の字は、出来上がった絵で字の色のまま残る点だけ） */
static u32 hi_seq;
static HiEnt hi_ent[HI_MAX];
static int hi_head[200];          /* y ごとのつながり（hi_next） */
static int hi_next[HI_MAX];
static int hi_free = -1, hi_inited, hi_n;
static u32 hi_frame;
static JFont jf16;
/* 重ねる字: 東雲 14 ドットを 16x16 の枠の上 1・左 1 ずらして置く（16 ドットは詰まって見えるため） */
#define HIF (&jf14)
#define HIF_TOP 1
#define HIF_LEFT 1
static void hi_init(void)
{
    int i;
    for (i = 0; i < 200; i++) hi_head[i] = -1;
    for (i = 0; i < HI_MAX; i++) { hi_next[i] = i + 1 < HI_MAX ? i + 1 : -1; hi_ent[i].used = 0; }
    hi_free = 0; hi_inited = 1;
}
/* 14 ドットの字は 8 ドットより縦横に広く、8 ドットの字に点の無い行・列にも点を描く。字をやめたとき元の画面のその行が
   変わらないと DOSBox は描き直さず、14 ドットの点が残る。そこで、やめた字の 8 行ぶんの DOSBox の写し
   （render.scale.cacheRead）を崩して、次にその行を送るとき描き直させる */
#define DB_CACHE_READ  0x01ef16e8u   /* render.scale.cacheRead（今の行の写し） */
static s16 rd_x0[200], rd_x1[200];   /* 行ごとの描き直させる範囲 [x0, x1) */
static void mark_redraw(const HiEnt *e)
{
    int r;
    for (r = 0; r < 8; r++) {
        int y = e->y + r;
        if (y < 0 || y >= 200) continue;
        if (rd_x1[y] <= rd_x0[y]) { rd_x0[y] = e->x; rd_x1[y] = (s16)(e->x + 8); }
        else { if (e->x < rd_x0[y]) rd_x0[y] = e->x; if (e->x + 8 > rd_x1[y]) rd_x1[y] = (s16)(e->x + 8); }
    }
}
static void apply_redraw(int L)
{
    u8 *cache;
    int x, x0, x1;
    if (L < 0 || L >= 200 || rd_x1[L] <= rd_x0[L]) return;
    x0 = rd_x0[L] & ~3; x1 = (rd_x1[L] + 3) & ~3;
    if (x0 < 0) x0 = 0;
    if (x1 > 320) x1 = 320;
    rd_x0[L] = rd_x1[L] = 0;
    cache = *(u8 **)DB_CACHE_READ;
    if (!cache) return;
    for (x = x0; x < x1; x++) cache[x] ^= 0xFF;
}
static void hi_remove(int y, int i, int prev)
{
    if (hi_ent[i].drawn) mark_redraw(&hi_ent[i]);
    if (prev < 0) hi_head[y] = hi_next[i]; else hi_next[prev] = hi_next[i];
    hi_ent[i].used = 0; hi_next[i] = hi_free; hi_free = i; hi_n--;
}
/* 表が満杯のとき: もう画面に無いと分かった字（ok=0）を消す。それでも空かなければ、いちばん古い字を消す
   （人物作成のように長い文が続くと、古い字が約 10 秒消えずに残って表が埋まり、新しい知らせの字が途中から 8 ドットのままになった） */
static void hi_reclaim(void)
{
    int y, by = -1, bi = -1, bp = -1;
    u32 bseq = 0xffffffffu;
    for (y = 0; y < 200; y++) {
        int i = hi_head[y], prev = -1;
        while (i >= 0) {
            int nx = hi_next[i];
            if (!hi_ent[i].perm && !hi_ent[i].ok) hi_remove(y, i, prev); else prev = i;
            i = nx;
        }
    }
    LOG("細かい字の表が満杯 → 画面から消えた字を消して %d 字に", hi_n);
    if (hi_free >= 0) return;
    for (y = 0; y < 200; y++) {
        int i, prev = -1;
        for (i = hi_head[y]; i >= 0; prev = i, i = hi_next[i])
            if (!hi_ent[i].perm && hi_ent[i].seq < bseq) { bseq = hi_ent[i].seq; by = y; bi = i; bp = prev; }
    }
    if (bi >= 0) hi_remove(by, bi, bp);
}

static void hi_add(s32 x, s32 y, u8 a, u8 b, u8 color)
{
    int i, prev = -1;
    if (!HIF->full || y < 0 || y >= 200 || x < 0 || x > 312) return;
    if (!hi_inited) hi_init();
    /* 同じ位置の古いものは置き換える */
    for (i = hi_head[y]; i >= 0; prev = i, i = hi_next[i]) {
        if (hi_ent[i].x == x && hi_ent[i].color == color) { if (hi_ent[i].drawn && (hi_ent[i].a != a || hi_ent[i].b != b)) mark_redraw(&hi_ent[i]); /* 同じ字を同じ所に描き直しただけなら描いた順は変えない（経歴の文・記録は文を描き直し続け、
           フレームの途中で本文だけ新しい順になると、影との重なりの点が入れ替わってちらついた） */
            if (hi_ent[i].a != a || hi_ent[i].b != b || !hi_ent[i].ok) { hi_ent[i].seq = ++hi_seq; hi_ent[i].behind = 0; }
            hi_ent[i].a = a; hi_ent[i].b = b; hi_ent[i].seen = hi_frame; memset(hi_ent[i].vm, 0xff, 8); hi_ent[i].owner = 0; hi_ent[i].badrows = 0; if (!hi_ent[i].ok) { hi_ent[i].ok = 1; mark_redraw(&hi_ent[i]); } return; }
    }
    if (hi_free < 0) hi_reclaim();
#ifdef TESTCTL
    { extern int dbg_draw_ext(void); if (dbg_draw_ext() && y >= 70 && y < 130) LOG("ADD x=%d y=%d col=%d free=%d n=%d", x, y, color, hi_free, hi_n); }
#endif
    if (hi_free < 0) return;
    i = hi_free; hi_free = hi_next[i];
    hi_ent[i].x = (s16)x; hi_ent[i].y = (s16)y; hi_ent[i].a = a; hi_ent[i].b = b; hi_ent[i].color = color;
    hi_ent[i].used = 1; hi_ent[i].seen = hi_frame; hi_ent[i].ok = 1; hi_ent[i].seq = ++hi_seq; hi_ent[i].perm = 0; memset(hi_ent[i].vm, 0xff, 8); hi_ent[i].owner = 0; hi_ent[i].drawn = 0; hi_ent[i].badrows = 0; hi_ent[i].behind = 0;
    hi_next[i] = hi_head[y]; hi_head[y] = i; hi_n++;
}

/* ---- DOSBox の拡大処理への割り込み ---- */
#define DB_RENDER_LINE    0x01ef1650u  /* RENDER_DrawLine（関数ポインタ） */
#define DB_DRAWLINE_CALL1 0x0051182bu  /* VGA_DrawPart の call [RENDER_DrawLine] */
#define DB_DRAWLINE_CALL2 0x00511939u
#define DB_LINES_DONE     0x01d15504u  /* vga.draw.lines_done（今の行） */
#define DB_OUT_PITCH      0x01ef16dcu  /* render.scale.outPitch */
#define DB_LINE_HANDLER   0x01ef16c8u  /* render.scale.lineHandler（次が linePalHandler） */
#define DB_OUT_WRITE      0x01ef16e0u  /* render.scale.outWrite */
#define DB_PAL_LUT        0x01ef1af8u  /* render.pal.lut（色番号 → 出力の色） */
typedef void (__cdecl *DrawLine_t)(const void *);
static int out_unit;          /* 出力 1 点のバイト数（4 か 2）。0=まだ、-1=使えない */
static int detect_tries;

static void detect_unit(const u8 *src, const u8 *out)
{
    const u32 *l32 = (const u32 *)DB_PAL_LUT; const u16 *l16 = (const u16 *)DB_PAL_LUT;
    int x, m32 = 0, m16 = 0, tot = 0, nz = 0;
    u8 c0 = src[0];
    int vary = 0;
    for (x = 0; x < 320; x += 3) {
        u8 c = src[x];
        if (c != c0) vary = 1;
        if (l32[c]) nz++;
        tot++;
        if (((const u32 *)out)[x * 2] == l32[c] && ((const u32 *)out)[x * 2 + 1] == l32[c]) m32++;
        if (((const u16 *)out)[x * 2] == l16[c] && ((const u16 *)out)[x * 2 + 1] == l16[c]) m16++;
    }
    if (!vary || nz < tot / 2) return;           /* 判定に向かない行 */
    if (m32 * 100 >= tot * 95) out_unit = 4;
    else if (m16 * 100 >= tot * 95) out_unit = 2;
    else if (++detect_tries > 3000) out_unit = -1;
    if (out_unit) LOG("拡大後の画面: 1 点 %d バイト（32bit 一致 %d/%d、16bit %d/%d）", out_unit, m32, tot, m16, tot);
}

static u32 out_get(u8 *line, int px) { return out_unit == 4 ? ((u32 *)line)[px] : ((u16 *)line)[px]; }
static void out_put(u8 *line, int px, u32 v) { if (out_unit == 4) ((u32 *)line)[px] = v; else ((u16 *)line)[px] = (u16)v; }

static u32 dbg_until;      /* 試験用: この frame まで、行ごとの様子をログに書く */
static int dbg_draw;       /* 試験用: 文字列を描く様子をログに書く回数 */
static int dbg_line = -1;  /* 試験用: この行の矢印の印・字の色を一度だけログに書く（dfjp_dump.txt の 3 つ目の数） */
int dbg_draw_ext(void) { return dbg_draw > 0; }
/* マウスの矢印（ゲームが自分で描く。描いてあれば 0x147964 の bit0、切り取った絵 0x12ad10（幅 w の詰めた行）、
   位置 0x12af1c・0x12af20、大きさ 0x12af14・0x12af16、色 0 は透明）の、行 L の点を cur[x]=1 にする */
#define D_CUR_SHOWN 0x00147964u
static int nocur;
static int curhook;
#define D_CUR_IMG   0x0012ad10u
#define D_CUR_X     0x0012af1cu
#define D_CUR_Y     0x0012af20u
#define D_CUR_W     0x0012af14u
#define D_CUR_H     0x0012af16u
/* 町や持ち物などゲームの中では、矢印は 0x12af1c の位置でなく別の所（マウスの座標から換算した位置）に描かれ、
   0x12af1c は古いまま（10,10 など）のことがある。そこで、元の画面の行を上から見て、矢印の絵の 1 行目と
   同じ並びの所を探し、次の行からも絵と合っているか確かめながら、その位置の矢印の点を印にする */
static s32 f_cx = -1000, f_cy = -1000;      /* この画面で見つけた矢印の左上 */
static s32 p_cx = -1000, p_cy = -1000;      /* 直前の画面で見つけた位置 */
static int dbg_c0hits, dbg_maxline;
static void cursor_frame(void)
{
#ifdef TESTCTL
    { static u32 k; if ((k++ & 63) == 0) LOG("矢印さがし: 見つけた %d,%d 一色目の当たり %d 最後の行 %d 絵の1行目 %02X%02X%02X", f_cx, f_cy, dbg_c0hits, dbg_maxline,
        rd8(D(D_CUR_IMG)), rd8(D(D_CUR_IMG) + 1), rd8(D(D_CUR_IMG) + 2)); }
#endif
    dbg_c0hits = 0; dbg_maxline = 0;
    p_cx = f_cx; p_cy = f_cy;
    f_cx = f_cy = -1000;
}
static int cursor_rowmatch(const u8 *src, s32 cx, s32 r, s32 cw)
{
    s32 i, n = 0;
    for (i = 0; i < cw; i++) {
        u8 c = rd8(D(D_CUR_IMG) + (u32)(r * cw + i));
        if (!c) continue;
        if (cx + i < 0 || cx + i >= 320) continue;
        if (src[cx + i] != c) return 0;
        n++;
    }
    return n > 0;
}
static void cursor_scan(int L, const u8 *src)
{
    s32 cw, chh, x;
    if (L > dbg_maxline) dbg_maxline = L;
    if (!located || !hi_n || (curhook && !nocur)) return;           /* 字が無ければ探さない */
    cw = (s16)rd16(D(D_CUR_W)); chh = (s16)rd16(D(D_CUR_H));
    if (cw <= 0 || chh <= 0 || cw > 16 || chh > 16) return;
    if (L > f_cy && L < f_cy + chh) {
        if (cursor_rowmatch(src, f_cx, L - f_cy, cw)) return;
        /* 絵と合わない（透明な行なら続ける）: 見つけ直す */
        {
            s32 i, any = 0;
            for (i = 0; i < cw; i++) if (rd8(D(D_CUR_IMG) + (u32)((L - f_cy) * cw + i))) any = 1;
            if (!any) return;
        }
        f_cx = f_cy = -1000;
    }
    if (f_cy > -100 && L < f_cy + chh) return;
    /* 絵のどの行とも合わせてみる（画面を送る途中で矢印が描き直されると、上の行が欠けた形で写るため）。
       点が 3 つ以上ある行だけ使う */
    {
        s32 r;
        for (r = 0; r < chh && r <= L; r++) {
            s32 i0 = -1, i, n = 0;
            u8 c0 = 0;
            for (i = 0; i < cw; i++) { u8 c = rd8(D(D_CUR_IMG) + (u32)(r * cw + i)); if (c) { n++; if (i0 < 0) { i0 = i; c0 = c; } } }
            if (n < 3) continue;
            for (x = -i0; x + i0 < 320; x++) {
                if (src[x + i0] != c0) continue;
                dbg_c0hits++;
                if (cursor_rowmatch(src, x, r, cw)) { f_cx = x; f_cy = L - r; return; }
            }
        }
    }
}
static void cursor_put(int L, u8 *cur, s32 cx, s32 cy, s32 cw, s32 chh)
{
    s32 i;
    if (L < cy || L >= cy + chh) return;
    for (i = 0; i < cw; i++) {
        s32 X = cx + i;
        if (X < 0 || X >= 320) continue;
        if (rd8(D(D_CUR_IMG) + (u32)((L - cy) * cw + i))) cur[X] = 1;
    }
}
/* ===== 矢印の記録 =====
   ゲームの矢印の描き方はそのまま（英語版と同じ）。矢印を描く呼び出しを横で見て、描いた位置と絵を写しておく。
   字の判定では、記録の位置で、画面の点が矢印の絵の色と同じ点だけを「矢印に隠れている」とする。
   見る所（どれも obj2 の call を差し込みに替え、差し込みの中で元の call をする）:
     0x12b454 メニューの矢印を描く call 0x144fc8（eax=x edx=y ebx=幅 ecx=高さ esi=絵）
     0x12b31f メニューの矢印を消す call 0x144ef0
     0x144fbc 絵を描く関数 0x144fb4 の中の call 0x144fc8。呼んだ所（[ebp+4]）が
       0x80609（ゲーム中の矢印）・0x7b42d（窓の中の矢印）・0x80591（形の一覧の矢印）なら記録する */
typedef struct { s32 x, y, w, h; u8 img[32 * 32]; LARGE_INTEGER t; } CurRec;
#define NREC 8
static CurRec rec_asm, rec[NREC];
static int asm_on, rec_n;
static LARGE_INTEGER qpf;
static int cb_cdraw, cb_chide, cb_cblit;
static double since(const LARGE_INTEGER *t)
{
    LARGE_INTEGER n;
    if (!t->QuadPart) return 1e9;
    if (!qpf.QuadPart) QueryPerformanceFrequency(&qpf);
    QueryPerformanceCounter(&n);
    return (double)(n.QuadPart - t->QuadPart) / qpf.QuadPart;
}
static void wr32g(u32 a, u32 v) { wr8(a, (u8)v); wr8(a + 1, (u8)(v >> 8)); wr8(a + 2, (u8)(v >> 16)); wr8(a + 3, (u8)(v >> 24)); }
/* 差し込み（FE 38 cb cb 90）の中で元の call rel32 をする: 戻り先を積んで飛ぶ */
static void do_call(u32 rel)
{
    u32 *r = R(), at = r[8] - 4;
    r[4] -= 4; wr32g(r[4], at + 5);
    r[8] = at + 5 + rel;
}
/* 記録を足す（同じ位置・大きさなら時刻だけ新しくする） */
static void rec_add(s32 x, s32 y, s32 w, s32 h, u32 img, CurRec *out)
{
    CurRec *c;
    s32 i;
    if (w <= 0 || h <= 0 || w > 32 || h > 32) return;
    c = &rec[(rec_n + NREC - 1) % NREC];
    if (!(rec_n && c->x == x && c->y == y && c->w == w && c->h == h)) c = &rec[rec_n++ % NREC];
    c->x = x; c->y = y; c->w = w; c->h = h;
    for (i = 0; i < w * h; i++) c->img[i] = rd8(img + (u32)i);
    QueryPerformanceCounter(&c->t);
    if (out) *out = *c;
}
static u32 cb_cdraw_fn(void)
{
    u32 *r = R();
    rec_add((s32)r[0], (s32)r[2], (s32)r[3], (s32)r[1], r[6], &rec_asm);
    asm_on = 1;
    do_call(0x00019b6fu);
    return 0;
}
static u32 cb_chide_fn(void)
{
    asm_on = 0;
    do_call(0x00019bccu);
    return 0;
}
/* 呼んだ所が矢印か。戻り先 ret から、その所の前の決まった並びを確かめる */
static int is_cursor_caller(u32 ret)
{
    static const struct { u32 g_ret, g_sig; u8 sig[8]; } K[3] = {
        {0x00080609u, 0x000805a3u, {0x81, 0xec, 0x00, 0x00, 0x00, 0x00, 0x6a, 0x00}},
        {0x0007b42du, 0x0007b410u, {0xb9, 0x0a, 0x00, 0x00, 0x00, 0xbb, 0x0a, 0x00}},
        {0x00080591u, 0x00080565u, {0x8b, 0x45, 0xd0, 0x83, 0xc0, 0x0c, 0x50, 0x8b}}};
    static u32 known[3];
    int k, i;
    for (k = 0; k < 3; k++) {
        u32 d;
        if (known[k]) { if (ret == known[k]) return 1; continue; }
        d = ret - K[k].g_ret;
        for (i = 0; i < 8; i++) if (crd8(K[k].g_sig + d + (u32)i) != K[k].sig[i]) break;
        if (i == 8) { known[k] = ret; return 1; }
    }
    return 0;
}
static u32 cb_cblit_fn(void)
{
    u32 *r = R();
    if (is_cursor_caller(rd32(r[5] + 4))) rec_add((s32)r[0], (s32)r[2], (s32)r[3], (s32)r[1], r[6], 0);
    do_call(0x00000007u);
    return 0;
}
/* curhook: 3 か所とも差し込めた（上で宣言） */
static void rec_put(int L, const u8 *src, u8 *cur, const CurRec *c, int strict)
{
    s32 i;
    if (L < c->y || L >= c->y + c->h) return;
    if (strict) {
        /* 古い位置の記録: この行に矢印の絵がほぼそろって残っているときだけ使う
           （もう消えた位置で、たまたま矢印と同じ色だった字の影の点を 8 ドットのまま見せていた） */
        int op = 0, hit = 0;
        for (i = 0; i < c->w; i++) {
            s32 X = c->x + i;
            u8 v = c->img[(L - c->y) * c->w + i];
            if (!v || X < 0 || X >= 320) continue;
            op++; if (src[X] == v) hit++;
        }
        if (!op || hit * 4 < op * 3) return;
    }
    for (i = 0; i < c->w; i++) {
        s32 X = c->x + i;
        u8 v = c->img[(L - c->y) * c->w + i];
        if (v && X >= 0 && X < 320 && src[X] == v) cur[X] = 1;
    }
}

/* 行 L の、矢印に隠れている点を cur[x]=1 にする */
static void cursor_row(int L, const u8 *src, u8 *cur)
{
    s32 cw, chh;
    memset(cur, 0, 320);
    if (!located) return;
    if (curhook && !nocur) {
        int k;
        if (asm_on) rec_put(L, src, cur, &rec_asm, 0);
        /* 一番新しい記録は、止まっていて描き直されなくても有効（今の矢印）。古いものは 0.5 秒、絵がそろっている行だけ */
        for (k = 0; k < NREC && k < rec_n; k++) {
            if (k == (rec_n - 1) % NREC) rec_put(L, src, cur, &rec[k], 0);
            else if (since(&rec[k].t) < 0.5) rec_put(L, src, cur, &rec[k], 1);
        }
        return;
    }
    cw = (s16)rd16(D(D_CUR_W)); chh = (s16)rd16(D(D_CUR_H));
    if (cw <= 0 || chh <= 0 || cw > 16 || chh > 16) return;
    if (rd16(D(D_CUR_SHOWN)) & 1) cursor_put(L, cur, (s32)rd32(D(D_CUR_X)), (s32)rd32(D(D_CUR_Y)), cw, chh);
    if (f_cy > -100) cursor_put(L, cur, f_cx, f_cy, cw, chh);
    if (p_cy > -100) cursor_put(L, cur, p_cx, p_cy, cw, chh);
}
/* 絵の字: 後から読んだ別の絵の字（今そこに見えている）と重なる古い絵の字は描かない
   （ロード画面の見出しの登録が残っていて、人物の画面の見出しと偶然合った行で描かれた） */
static int hi_hidden_by_newer(const HiEnt *e, const int *idx, int ni)
{
    int u;
    if (!e->perm) return 0;
    for (u = 0; u < ni; u++) {
        const HiEnt *f = &hi_ent[idx[u]];
        if (f == e || !f->perm || f->owner == e->owner || f->seq < e->seq || !f->ok) continue;
        if (f->x - e->x < 8 && e->x - f->x < 8 && f->y - e->y < 8 && e->y - f->y < 8) return 1;
    }
    return 0;
}
static int hi_cmp_seq(const void *a, const void *b)
{
    const HiEnt *p = &hi_ent[*(const int *)a], *q = &hi_ent[*(const int *)b];
    u32 x = p->seq, y = q->seq;
    if (p->behind != q->behind) return p->behind ? -1 : 1;   /* 下に回る字を先に */
    return x < y ? -1 : x > y;
}
static void hi_line(int L, const u8 *src, u8 *out, s32 pitch, int n)
{
    /* 近くの 8 行の字を全部集める（128 で打ち切ると、裏の画面の字の記録で埋まって、上に重なった知らせの字が拾われなかった） */
    static int idx[HI_MAX];
    static u8 cur[320];          /* この行の、マウスの矢印の点（1=矢印） */
    int ni = 0, yy, k, t, lastbg = -1;
    u8 cols[32]; int ncol = 0;
    s32 wpx = pitch / out_unit;
    for (yy = L; yy >= 0 && yy > L - 8; yy--) {
        int i;
        for (i = hi_head[yy]; i >= 0 && ni < HI_MAX; i = hi_next[i]) idx[ni++] = i;
    }
    if (!ni) return;
    cursor_row(L, src, cur);
    /* 下に回る字を見分ける: 字の点に、自分より先に描いた別の字の色が見えていれば、自分は「空いた所だけ」に描かれた
       （経歴の文の影は本文の後に描かれるが、本文の点は消さない。後から描いた方を上として判定すると、影の字が
       ふだんは消えた扱いになり、矢印が食い違う点を隠したときだけ 14 ドットで描かれて点が出た） */
    {
        static u32 topseq[320];
        int c;
        for (c = 0; c < 320; c++) topseq[c] = 0xFFFFFFFFu;
        for (t = 0; t < ni; t++) {
            const HiEnt *e = &hi_ent[idx[t]];
            const u16 *g8 = jglyph(&jf8, e->a, e->b);
            u8 m;
            if (!g8) continue;
            m = (u8)(g8[L - e->y] >> 8);
            for (c = 0; c < 8; c++) if ((m & (0x80 >> c)) && e->x + c < 320 && src[e->x + c] == e->color && e->seq < topseq[e->x + c]) topseq[e->x + c] = e->seq;
        }
        for (t = 0; t < ni; t++) {
            HiEnt *e = &hi_ent[idx[t]];
            const u16 *g8;
            u8 m;
            if (e->behind || e->perm) continue;
            g8 = jglyph(&jf8, e->a, e->b);
            if (!g8) continue;
            m = (u8)((g8[L - e->y] >> 8) & e->vm[L - e->y]);
            for (c = 0; c < 8; c++) {
                int X = e->x + c;
                if (!(m & (0x80 >> c)) || X >= 320 || src[X] == e->color || cur[X]) continue;
                if (topseq[X] < e->seq) { e->behind = 1; break; }
            }
        }
    }
    /* ゲームが描いた順（影と本文の重なり）に並べる */
    if (ni > 1) qsort(idx, (size_t)ni, sizeof idx[0], hi_cmp_seq);
    /* まだ画面にあるか: 字の点が、この字の色か、後から描いた字（影の上の本文など）がその点を覆っているなら、まだある。
       ほかの字の色でも、覆う字が無ければ消えている（上に別の文の窓が重なった・色を変えて描き直した）。
       字の色（下地を拾うときに避ける色）は、この行に自分の色の点が残っている字の色だけにする
       （消えた字の色を入れると、それが下地と同じ色のとき下地が拾えず、8 ドットの字が残った） */
    for (t = 0; t < ni; t++) {
        HiEnt *e = &hi_ent[idx[t]];
        int r = L - e->y, c, good = 0, bad = 0;
        const u16 *g8 = jglyph(&jf8, e->a, e->b);
        u8 m;
        if (!g8) continue;
        m = (u8)((g8[r] >> 8) & e->vm[r]);   /* 確かめる点だけ */
        for (c = 0; c < 8; c++) if (m & (0x80 >> c)) {
            u8 v = src[e->x + c];
            int X = e->x + c, u, cov = 0;
            if (v == e->color) { good++; continue; }
            if (cur[X]) continue;                 /* 矢印に隠れている点は数えない */
            for (u = t + 1; u < ni && !cov; u++) {
                const HiEnt *f = &hi_ent[idx[u]];
                const u16 *gf;
                if (f->color != v || X < f->x || X >= f->x + 8 || L < f->y || L >= f->y + 8) continue;
                gf = jglyph(&jf8, f->a, f->b);
                if (gf && ((gf[L - f->y] >> 8) & (0x80 >> (X - f->x)))) cov = 1;
            }
            if (!cov) bad++;
        }
#ifdef TESTCTL
        if (e->ok && bad && good && located) {
            /* 試験用: 字の一部だけ合わなくなった（8 ドットに戻る）。矢印の記録が重なっていたか */
            int nearc = 0, q;
            for (q = -1; q < NREC && q < rec_n; q++) {
                const CurRec *c = q < 0 ? &rec_asm : &rec[q];
                if (q < 0 && !asm_on) continue;
                if (q >= 0 && q != (rec_n - 1) % NREC && since(&c->t) >= 0.5) continue;
                if (c->x - 1 < e->x + 8 && e->x < c->x + c->w + 1 && c->y - 1 < e->y + 8 && e->y < c->y + c->h + 1) nearc = 1;
            }
            {
                char bx[120]; int bn = 0, c2;
                const CurRec *lr = rec_n ? &rec[(rec_n - 1) % NREC] : 0;
                for (c2 = 0; c2 < 8; c2++) if ((m & (0x80 >> c2)) && src[e->x + c2] != e->color && !cur[e->x + c2]) bn += sprintf(bx + bn, "%d:%d ", e->x + c2, src[e->x + c2]);
                LOG("部分%s near=%d F=%u L=%d x=%d y=%d good=%d bad=%d 色 %d 点 %s 最新の矢印 %d,%d %dx%d 前 %.2fs メニュー %d %d,%d マウス %d,%d", e->perm ? "P" : "", nearc, hi_frame, L, e->x, e->y, good, bad, e->color, bx,
                    lr ? lr->x : -1, lr ? lr->y : -1, lr ? lr->w : 0, lr ? lr->h : 0, lr ? since(&lr->t) : -1.0, asm_on, rec_asm.x, rec_asm.y,
                    (s16)rd16(D(0x0012ac04u)), (s16)rd16(D(0x0012ac06u)));
            }
        }
        if (e->ok && bad && !e->perm && located) {
            static u32 nlog;
            if (nlog < 3) {
                char ib[1200]; int ibn = 0, yy2, xx2; s32 cw2 = (s16)rd16(D(D_CUR_W)), ch2 = (s16)rd16(D(D_CUR_H));
                for (yy2 = 0; yy2 < ch2 && yy2 < 16; yy2++) {
                    for (xx2 = 0; xx2 < cw2 && xx2 < 16; xx2++) ibn += sprintf(ib + ibn, "%02X", rd8(D(D_CUR_IMG) + (u32)(yy2 * cw2 + xx2)));
                    ibn += sprintf(ib + ibn, "|");
                }
                LOG("  絵 %dx%d %s", cw2, ch2, ib);
                ibn = 0;
                for (xx2 = 70; xx2 < 110; xx2++) ibn += sprintf(ib + ibn, "%d,", src[xx2]);
                LOG("  行 %d: %s", L, ib);
            }
            if (nlog++ < 400) {
                char bx[80]; int bn = 0, c2;
                for (c2 = 0; c2 < 8; c2++) if ((m & (0x80 >> c2)) && src[e->x + c2] != e->color && !cur[e->x + c2]) bn += sprintf(bx + bn, "%d:%d ", e->x + c2, src[e->x + c2]);
                LOG("消えた F=%u L=%d x=%d y=%d good=%d bad=%d 色 %d 矢印 %d,%d 見つけた %d,%d 点 %s", hi_frame, L, e->x, e->y, good, bad, e->color,
                    (s32)rd32(D(D_CUR_X)), (s32)rd32(D(D_CUR_Y)), f_cx, f_cy, bx);
            }
        }
#endif
#ifdef TESTCTL
        if (e->perm && e->ok && bad && !good) { static u32 np; if (np++ < 3000) LOG("絵の字が消えた F=%u L=%d x=%d y=%d bad=%d", hi_frame, L, e->x, e->y, bad); }
        if (e->perm && !e->ok && good && !bad) { static u32 nq; if (nq++ < 3000) LOG("絵の字が戻った F=%u L=%d x=%d y=%d", hi_frame, L, e->x, e->y); }
#endif
        /* 行ごとに ok を決めると、合う行と合わない行が混ざった字で毎フレーム「描く・やめる」が入れ替わり、
           描き直しを頼み続けた。合わない行を覚え、全部の行が合ってから描く。描けるようになったら字の全部の行を描き直させる */
        if (good + bad) {
            u8 was = e->ok;
            if (bad) e->badrows |= (u8)(1 << r); else e->badrows &= (u8)~(1 << r);
            e->ok = (u8)(e->badrows == 0);
            if (e->ok && !was) mark_redraw(e);
        }
#ifdef TESTCTL
        if (dbg_until && hi_frame <= dbg_until && L >= 76 && L <= 84 && !e->perm && bad) {
            char pix[64]; int pc, pn = 0;
            for (pc = 0; pc < 8; pc++) pn += sprintf(pix + pn, "%d%s,", src[e->x + pc], (m & (0x80 >> pc)) ? "*" : "");
            LOG("  F=%u L=%d x=%d y=%d col=%d good=%d bad=%d ok=%d pix=%s", hi_frame, L, e->x, e->y, e->color, good, bad, e->ok, pix);
        }
#endif
        if (e->ok && good && ncol < 32) {
            int q, f = 0;
            for (q = 0; q < ncol; q++) if (cols[q] == e->color) f = 1;
            if (!f) cols[ncol++] = e->color;
        }
    }
#ifdef TESTCTL
    if (dbg_line == L && hi_frame <= dbg_until) {
        char b[1400]; int bn = 0, q;
        bn += sprintf(b + bn, "F=%u 行 %d 矢印の印:", hi_frame, L);
        for (q = 0; q < 320 && bn < 600; q++) if (cur[q]) bn += sprintf(b + bn, " %d", q);
        bn += sprintf(b + bn, " 字の色:");
        for (q = 0; q < ncol; q++) bn += sprintf(b + bn, " %d", cols[q]);
        bn += sprintf(b + bn, " 元の点 160-185:");
        for (q = 160; q < 186; q++) bn += sprintf(b + bn, " %d", src[q]);
        LOG("%s", b);
        for (q = 0; q < ni; q++) {
            const HiEnt *e = &hi_ent[idx[q]];
            if (e->x >= 150 && e->x <= 190) LOG("  字 x=%d y=%d 色 %d ok=%d bad=%02x behind=%d perm=%d seq=%u", e->x, e->y, e->color, e->ok, e->badrows, e->behind, e->perm, e->seq);
        }
    }
#endif
    /* ゲームが描いた順に描く */
    for (t = 0; t < ni; t++) {
        HiEnt *e = &hi_ent[idx[t]];
        int r = L - e->y, c;
        const u16 *g8 = jglyph(&jf8, e->a, e->b), *g16 = jglyph(HIF, e->a, e->b);
        u8 m;
        u32 fg;
        if (!g8 || !g16) continue;
        m = (u8)(g8[r] >> 8);
        if (!e->ok || hi_hidden_by_newer(e, idx, ni)) {
            if (e->drawn) { mark_redraw(e); e->drawn = 0; }
            continue;
        }
        e->drawn = 1;
        e->seen = hi_frame;
        fg = out_unit == 4 ? ((const u32 *)DB_PAL_LUT)[e->color] : ((const u16 *)DB_PAL_LUT)[e->color];
        for (k = 0; k < n; k++) {
            u8 *line = out + k * pitch;
            /* 16x16 の枠に、細かい字（HIF の高さ）を上と左に余白を付けて置く */
            int R = r * 2 + (k ? 1 : 0) - HIF_TOP;
            u16 row = (R >= 0 && R < HIF->h) ? (u16)(g16[R] >> HIF_LEFT) : 0;
            int s;
            for (c = 0; c < 8; c++) {
                int x = e->x + c, lowset = (m & (0x80 >> c)) != 0 && src[e->x + c] == e->color;
                if (x < 320 && cur[x] && !lowset) continue;  /* 矢印かもしれない点はそのまま見せる（字の点が見えている所は描く） */
                for (s = 0; s < 2; s++) {
                    int px = x * 2 + s, bit = (row << (c * 2 + s)) & 0x8000;
                    if (px >= wpx) continue;
                    if (bit) out_put(line, px, fg);
                    else if (lowset) {
                        /* 下地の色: 近くの、字でない点から取る */
                        int d, q, got = -1;
                        /* 字が詰まった行で矢印の点を除くと、9 点以内に下地が無いことがある（塗れずに影の点が残った）。
                           遠くまで探し、それでも無ければこの行で前に拾った下地を使う */
                        for (d = 1; d < 40 && got < 0; d++) {
                            int cand[2], z;
                            cand[0] = x - d; cand[1] = x + d;
                            for (z = 0; z < 2 && got < 0; z++) {
                                int cx = cand[z], txt = 0;
                                if (cx < 0 || cx >= 320) continue;
                                for (q = 0; q < ncol; q++) if (src[cx] == cols[q]) txt = 1;
                                if (!txt && !cur[cx]) got = cx;   /* 矢印の点は下地にしない（青い点が残った） */
                            }
                        }
                        /* 色は元の画面の点の色から（拡大後の出力から拾うと、変わった所だけ描き直した行で、
                           前に重ねた 14 ドットの字の線の色を拾って塗り広げ、字が二重のようになった） */
                        if (got >= 0) lastbg = src[got];
                        if (lastbg >= 0) out_put(line, px, out_unit == 4 ? ((const u32 *)DB_PAL_LUT)[lastbg] : ((const u16 *)DB_PAL_LUT)[lastbg]);
                    }
                }
            }
        }
    }
}

static void hi_prune(void)
{
    int y;
    for (y = 0; y < 200; y++) {
        int i = hi_head[y], prev = -1;
        while (i >= 0) {
            int nx = hi_next[i];
            /* 消すのは、もう画面に無いと分かった字だけ。動かない画面（知らせの窓を読んでいる間など）は描き直されないので
               「見かけない」だけで消すと、後でマウスの矢印が通って描き直された行が 8 ドットのままになった */
            if (!hi_ent[i].perm && !hi_ent[i].ok && hi_frame - hi_ent[i].seen > 600) hi_remove(y, i, prev); else prev = i;
            i = nx;
        }
    }
}

static void __cdecl my_drawline(const u8 *src)
{
    u8 *before = *(u8 **)DB_OUT_WRITE, *after;
    u32 line = *(u32 *)DB_LINES_DONE;
    s32 pitch;
    int n;
    DrawLine_t fp0 = *(DrawLine_t *)DB_RENDER_LINE, fp1;
    if (hi_inited && src && line < 200) __try { apply_redraw((int)line); } __except (EXCEPTION_EXECUTE_HANDLER) { }
    (*(DrawLine_t *)DB_RENDER_LINE)(src);
    fp1 = *(DrawLine_t *)DB_RENDER_LINE;
    if (line == 0) {
        cursor_frame();
        hi_frame++; if (hi_inited && (hi_frame & 63) == 0) hi_prune();
#ifdef TESTCTL
        /* 試験用: dfjp_dump.txt（y0 y1）があれば、その範囲の字の記録をログに書いて消す */
        if (logfp && hi_inited && (hi_frame & 31) == 0) {
            FILE *df = fopen(dump_path, "r");
            if (df) {
                int y0 = 0, y1 = 0, y, i;
                if (fscanf(df, "%d %d", &y0, &y1) != 2) y1 = -1;
                if (fscanf(df, "%d", &dbg_line) != 1) dbg_line = -1;
                fclose(df); remove(dump_path);
                dbg_until = hi_frame + 200; dbg_draw = 30000;
                for (y = y0; y <= y1 && y < 200; y++)
                    for (i = hi_head[y]; i >= 0; i = hi_next[i])
                        LOG("DUMP y=%d x=%d ch=%02x%02x col=%d ok=%d perm=%d seq=%u seen=%u now=%u", y, hi_ent[i].x, hi_ent[i].a, hi_ent[i].b,
                            hi_ent[i].color, hi_ent[i].ok, hi_ent[i].perm, hi_ent[i].seq, hi_ent[i].seen, hi_frame);
            }
        }
#endif
    }
    if (!hi_inited || out_unit < 0 || !src || line >= 400) return;
    /* 矢印さがしは、変わらなかった行（下の return で抜ける）も見る */
    __try {
        static LARGE_INTEGER sf; static double ssum; static u32 sn;
        LARGE_INTEGER s0, s1;
        if (logfp) QueryPerformanceCounter(&s0);
        if (line < 200) cursor_scan((int)line, src);
        if (logfp) {
            QueryPerformanceCounter(&s1);
            if (!sf.QuadPart) QueryPerformanceFrequency(&sf);
            ssum += (double)(s1.QuadPart - s0.QuadPart) / sf.QuadPart;
            if (++sn >= 2000) { LOG("矢印さがし: 200 行あたり %.3f ms", ssum * 1000 / 10); ssum = 0; sn = 0; }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
    after = *(u8 **)DB_OUT_WRITE; pitch = *(s32 *)DB_OUT_PITCH;
    /* その画面で最初に変わった行では、DOSBox がここで描き始める（RENDER_DrawLine が描く関数に替わる）。
       そのとき描く前の位置は直前の画面の終わりのまま残っているので、描いた後の位置から 2 行戻った所をこの行とする
       （前は after <= before で抜けてしまい、その行だけ 14 ドットを描かず 8 ドットが残った。矢印が動くと矢印の上の行がそれに当たる） */
#ifdef TESTCTL
    if (fp0 != fp1) { static int nf; if (nf++ < 5) LOG("描き始め: 行 %u 関数 %p→%p lineHandler %08x %08x 位置 %p→%p", line, (void *)fp0, (void *)fp1,
        *(u32 *)DB_LINE_HANDLER, *(u32 *)(DB_LINE_HANDLER + 4), before, after); }
#endif
    if (fp0 != fp1 && after && pitch > 0 &&
        ((u32)fp1 == *(u32 *)DB_LINE_HANDLER || (u32)fp1 == *(u32 *)(DB_LINE_HANDLER + 4))) before = after - 2 * pitch;
    if (!before || !after || pitch <= 0 || after <= before) return;
    n = (int)((after - before) / pitch);
#ifdef TESTCTL
    if (dbg_until && hi_frame <= dbg_until && line >= 38 && line <= 52) LOG("LINE %u n=%d", line, n);
#endif
    if (n > 3) { before = after - 2 * pitch; n = 2; }
    if (n < 1) return;
    __try {
        if (!out_unit) { detect_unit(src, before); if (out_unit <= 0) return; }
        if (hi_n) {
            /* 試験用: かかった時間を記録（ログがあるときだけ） */
            static LARGE_INTEGER fq; static double tsum; static u32 tframes, tlast;
            LARGE_INTEGER t0, t1;
            if (logfp) QueryPerformanceCounter(&t0);
            hi_line((int)line, src, before, pitch, n);
            if (logfp) {
                QueryPerformanceCounter(&t1);
                if (!fq.QuadPart) QueryPerformanceFrequency(&fq);
                tsum += (double)(t1.QuadPart - t0.QuadPart) / fq.QuadPart;
                if (hi_frame != tlast) { tlast = hi_frame; tframes++; }
                if (tframes >= 10) { LOG("重ね描き: 描き直した画面 10 回の平均 %.3f ms（字 %d、frame %u）", tsum * 1000 / tframes, hi_n, hi_frame); tsum = 0; tframes = 0; }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { out_unit = -1; LOG("重ね描きで例外。細かい字はやめる"); }
}

static void blit_j(const Ctx *c, const u16 *rows, int h, s32 x, s32 y)
{
    int i, j;
    for (j = 0; j < h; j++) {
        u16 row = rows[j];
        if (!row) continue;
        for (i = 0; i < 16; i++) if ((row << i) & 0x8000) putpx(c, x + i, y + j);
    }
}

/* 元の 1 字の送り幅（0x5a442 と同じ計算） */
static s32 orig_chw(u8 ch)
{
    u32 font = rd32(D(D_FONT));
    if (ch == 0x20) return (s16)rd16(D(D_SPACEW));
    return (s16)rd16(font + 6 + (u32)(s16)(ch - 0x21) * 4) + (s16)rd16(D(D_XSP));
}

/* ===================== コールバック ===================== */
static int ncall;
static int enter(void)
{
    L_flush();
    if (!located && !locate()) { if (ncall++ < 5) LOG("位置が分からない eip=%08x", R()[8]); return 0; }
    return 1;
}

/* 文字列を描く: eax=x edx=y ebx=文字列 */
static u32 cb_drawstr_fn(void)
{
    u32 *r = R();
    s32 x, y, x0, h, xsp, ysp, spw;
    u32 s, font;
    const JFont *jf;
    Ctx c;
    if (!enter()) return 0;
    x = x0 = (s32)r[0]; y = (s32)r[2]; s = r[3];
    font = rd32(D(D_FONT));
    h = (s32)rd32(D(D_HEIGHT)); xsp = (s32)rd32(D(D_XSP)); ysp = (s32)rd32(D(D_YSP)); spw = (s32)rd32(D(D_SPACEW));
    jf = pick_jf(h);
    getctx(&c);
#ifdef TESTCTL
    if (dbg_draw > 0) {
        static u32 seenk[1024]; static int nseen;
        u32 key = (u32)x << 20 | (u32)y << 8 | c.color, q2; int dup = 0;
        for (q2 = 0; q2 < (u32)nseen; q2++) if (seenk[q2] == key) dup = 1;
        if (!dup && nseen < 1024) { seenk[nseen++] = key; dbg_draw--;
            LOG("DRAW x=%d y=%d h=%d jf8=%d clip=%d,%d,%d,%d scr=%08x col=%d row0=%08x rowy=%08x", x, y, h, jf == &jf8, c.cl, c.ct, c.cr, c.cb, c.scr, c.color,
                rd32(D(D_ROWTAB)), rd32(D(D_ROWTAB) + (u32)y * 4)); }
    }
#endif
    for (;;) {
        u8 ch = rd8(s);
        if (!ch) break;
        s++;
        if (is_jl(ch) && is_jt(rd8(s))) {
            const u16 *g = jglyph(jf, ch, rd8(s));
            if (g) {
                blit_j(&c, g, jf->h, x, y);
                if (jf == &jf8 && x >= c.cl && x + 8 <= c.cr && y >= c.ct && y + 8 <= c.cb) hi_add(x, y, ch, rd8(s), c.color);
            }
            s++;
            x += jadv(jf);
            continue;
        }
        if (ch >= 0x21 && ch <= 0xA0) {
            u32 e = font + 4 + (u32)(ch - 0x21) * 4;
            int w = rd16(e + 2);
            blit_orig(&c, font + rd16(e), w, h, x, y);
            x += w + xsp;
        } else if (ch == 0x20) x += spw;
        else if (ch == 0x0d) x = x0;
        else if (ch == 0x0a) y += h + ysp;
    }
    r[0] = (u32)x; r[2] = (u32)y; r[3] = s;
    return 0;
}

/* 1 字の送り幅: al=字。日本語は前のバイトで 1 字分、後のバイトは 0 */
static u32 cb_chw_fn(void)
{
    u32 *r = R();
    u8 ch;
    if (!enter()) return 0;
    ch = (u8)r[0];
    if (is_jl(ch)) r[0] = (u32)jadv(pick_jf((s32)rd32(D(D_HEIGHT))));
    else if (is_jt(ch) || ch < 0x20) r[0] = 0;
    else r[0] = (u32)orig_chw(ch);
    return 0;
}

/* 文字列の幅: eax=文字列 */
static u32 cb_strw_fn(void)
{
    u32 *r = R();
    u32 s;
    s32 w = 0, n = 0, jw;
    if (!enter()) return 0;
    s = r[0];
    jw = jadv(pick_jf((s32)rd32(D(D_HEIGHT))));
    for (;;) {
        u8 ch = rd8(s);
        if (!ch) break;
        if (is_jl(ch) && is_jt(rd8(s + 1))) { w += jw; s += 2; continue; }
        if (ch == 0x20) w += (s16)rd16(D(D_SPACEW));
        else if (ch < 0x20) { s++; continue; }   /* 0x1F は日本語の折り返しの目印（幅 0） */
        else {
            u32 font = rd32(D(D_FONT));
            w += (s16)rd16(font + 6 + (u32)(s16)(ch - 0x21) * 4);
            n++;
        }
        s++;
    }
    r[0] = (u32)(w + n * (s16)rd16(D(D_XSP)));
    return 0;
}

/* 探す: 入力（G_FINDBUF）が英語の地名（大文字小文字を問わない）なら、その日本語に書き換える。ebx=4 は元の命令 */
static int cb_find;
static u32 cb_find_fn(void)
{
    u32 *r = R(), n, p = 0, i;
    const u8 *s = find_sec("LOCN", &n);
    char in[40];
    r[3] = 4;
    if (!s || !located) return 0;
    for (i = 0; i < 39; i++) { in[i] = (char)rd8(G_FINDBUF + delta_of(G_FINDBUF) + i); if (!in[i]) break; }
    in[i] = 0;
    while (p < n && s[p]) {
        const char *en = (const char *)s + p;
        const u8 *ja = s + p + strlen(en) + 1;
        u32 jl = (u32)strlen((const char *)ja);
        if (_stricmp(en, in) == 0) {
            for (i = 0; i <= jl && i < 32; i++) wr8(G_FINDBUF + delta_of(G_FINDBUF) + i, ja[i]);
            LOG("探す: %s → 日本語の地名", in);
            break;
        }
        p += (u32)strlen(en) + 1 + jl + 1;
    }
    return 0;
}

/* 記録欄の印。先頭が日本語の 1 バイト目（0x80-0xAF）なら 2 バイト目の 0x80 を落とす。
 * 英字の 0x20-0x2F は 0x01-0x10 に（0x80 を足すと日本語の 1 バイト目と重なるため）、ほかは元どおり 0x80 を足す */
static int cb_tlmark, cb_tltest;
static u32 cb_tlmark_fn(void)
{
    u32 *r = R(), a = r[0];
    u8 f = rd8(a);
    if (f >= 0x80 && f <= 0xAF) { u8 t = rd8(a + 1); if (t >= 0x80) wr8(a + 1, (u8)(t & 0x7F)); }
    else if (f >= 0x20 && f <= 0x2F) wr8(a, (u8)(f - 0x1F));
    else if (f && f < 0x80) wr8(a, (u8)(f | 0x80));
    r[2] = rd32(r[5] - 0x18);               /* mov edx,[ebp-0x18] */
    return 0;
}
static u32 cb_tltest_fn(void)
{
    u32 *r = R(), b = G_TLBUF + delta_of(G_TLBUF);
    u8 f = rd8(b);
    int pl = 0;
    if (f >= 0x01 && f <= 0x10) { pl = 1; wr8(b, (u8)(f + 0x1F)); }
    else if (f >= 0x80 && f <= 0xAF) { u8 t = rd8(b + 1); if (t && t < 0x80) { pl = 1; wr8(b + 1, (u8)(t | 0x80)); } }
    else if (f >= 0xB0) { pl = 1; wr8(b, (u8)(f & 0x7F)); }
    wr32(r[5] - 0x14, pl ? 0x60 : 0x91);   /* 字の色 */
    return 0;
}

typedef u32 (*CBHandler)(void);
static int alloc_cb(CBHandler h)
{
    u32 *tab = (u32 *)DB_CB_HANDLERS;
    int i;
    for (i = 127; i > 0; i--) if (tab[i] == (u32)h) return i;
    for (i = 127; i > 0; i--) if (tab[i] == DB_CB_ILLEGAL) { tab[i] = (u32)h; return i; }
    return -1;
}

/* 読んだバッファの [pos, pos+n) に、ファイル位置 off からの len バイトを重ねる */
static void overlay(u8 *buf, u32 pos, u32 n, u32 off, const u8 *src, u32 len)
{
    u32 i;
    for (i = 0; i < len; i++) {
        u32 fo = off + i;
        if (fo >= pos && fo < pos + n) buf[fo - pos] = src[i];
    }
}

/* FALL.EXE を読んだバッファの中で、差し込み（FE 38 cb ; C3）と EXE の書き換えを当てる */
static void patch_read(u8 *buf, u32 pos, u32 n)
{
    struct { u32 off; const u8 *orig; int *cb; } P[3] = {
        {F_DRAWSTR, orig_ds, &cb_drawstr}, {F_CHW, orig_cw, &cb_chw}, {F_STRW, orig_cw, &cb_strw}};
    int k, i;
    if (cb_drawstr <= 0) cb_drawstr = alloc_cb(cb_drawstr_fn);
    if (cb_chw <= 0) cb_chw = alloc_cb(cb_chw_fn);
    if (cb_strw <= 0) cb_strw = alloc_cb(cb_strw_fn);
    if (cb_entry <= 0) cb_entry = alloc_cb(cb_entry_fn);
    if (cb_drawstr <= 0 || cb_chw <= 0 || cb_strw <= 0 || cb_entry <= 0) { LOG("コールバックが取れない"); return; }
    /* EXE の文字列があるときだけ: 入口のコールバック・obj3 を広げる・品物の名前 */
    if (find_sec("EXEB", 0)) {
        u32 fn, p = 0;
        const u8 *f = find_sec("EXEF", &fn);
        int same = 1;
        u8 st[6];
        for (i = 0; i < 6; i++) {
            u32 fo = F_ENTRY + i;
            if (fo >= pos && fo < pos + n && buf[fo - pos] != orig_entry[i]) same = 0;
        }
        if (same) {
            st[0] = 0xFE; st[1] = 0x38; st[2] = (u8)cb_entry; st[3] = (u8)(cb_entry >> 8); st[4] = 0xEB; st[5] = 0x72;
            overlay(buf, pos, n, F_ENTRY, st, 6);
            if (F_ENTRY >= pos && F_ENTRY < pos + n) LOG("FALL.EXE 入口 cb=%d", cb_entry);
            while (f && p + 8 <= fn) {
                u32 off = *(const u32 *)(f + p), len = *(const u32 *)(f + p + 4);
                overlay(buf, pos, n, off, f + p + 8, len);
                p += 8 + ((len + 3) & ~3u);
            }
        } else LOG("FALL.EXE の入口が違う");
    }
    for (k = 0; k < 3; k++) {
        u8 st[5];
        int bad = 0;
        st[0] = 0xFE; st[1] = 0x38; st[2] = (u8)*P[k].cb; st[3] = (u8)(*P[k].cb >> 8); st[4] = 0xC3;
        for (i = 0; i < 5; i++) {
            u32 fo = P[k].off + i;
            if (fo >= pos && fo < pos + n && buf[fo - pos] != P[k].orig[i]) bad = 1;
        }
        if (bad) { LOG("FALL.EXE の中身が違う %08x", P[k].off); continue; }
        for (i = 0; i < 5; i++) {
            u32 fo = P[k].off + i;
            if (fo >= pos && fo < pos + n) buf[fo - pos] = st[i];
        }
        if (P[k].off >= pos && P[k].off < pos + n) LOG("FALL.EXE 書き換え %08x cb=%d", P[k].off, *P[k].cb);
    }
    /* 探す（地名の訳があるときだけ）: mov ebx,4 → FE 38 cb ; nop */
    if (find_sec("LOCN", 0)) {
        u8 st[5];
        int bad = 0;
        if (cb_find <= 0) cb_find = alloc_cb(cb_find_fn);
        if (cb_find > 0) {
            st[0] = 0xFE; st[1] = 0x38; st[2] = (u8)cb_find; st[3] = (u8)(cb_find >> 8); st[4] = 0x90;
            for (i = 0; i < 5; i++) {
                u32 fo = F_FINDIN + i;
                if (fo >= pos && fo < pos + n && buf[fo - pos] != orig_findin[i]) bad = 1;
            }
            if (!bad) overlay(buf, pos, n, F_FINDIN, st, 5);
        }
    }
    /* 会話の記録欄の印（日本語の文があるとき） */
    if (find_sec("EXEB", 0)) {
        struct { u32 off; const u8 *orig; int *cb; CBHandler h; u8 t0, t1; } T[2] = {
            {F_TLMARK, orig_tlmark, &cb_tlmark, cb_tlmark_fn, 0x90, 0x90},
            {F_TLTEST, orig_tltest, &cb_tltest, cb_tltest_fn, 0xEB, 0x1C}};   /* jmp 0x16f0e */
        for (k = 0; k < 2; k++) {
            u8 st[6];
            int bad = 0;
            if (*T[k].cb <= 0) *T[k].cb = alloc_cb(T[k].h);
            if (*T[k].cb <= 0) continue;
            for (i = 0; i < 6; i++) {
                u32 fo = T[k].off + i;
                if (fo >= pos && fo < pos + n && buf[fo - pos] != T[k].orig[i]) bad = 1;
            }
            if (bad) { LOG("記録欄の差し込み先が違う %08x", T[k].off); continue; }
            st[0] = 0xFE; st[1] = 0x38; st[2] = (u8)*T[k].cb; st[3] = (u8)(*T[k].cb >> 8); st[4] = T[k].t0; st[5] = T[k].t1;
            overlay(buf, pos, n, T[k].off, st, 6);
        }
    }
    /* マウスの矢印を描く・消す呼び出しを見る（細かい字が有効なときだけ）。ファイル位置は obj2 +0x47600 */
    if (hi_inited) {
        static const u8 o_draw[5] = {0xe8, 0x6f, 0x9b, 0x01, 0x00}, o_hide[5] = {0xe8, 0xcc, 0x9b, 0x01, 0x00},
            o_blit[5] = {0xe8, 0x07, 0x00, 0x00, 0x00};
        static int got;
        struct { u32 off; const u8 *orig; int *cb; CBHandler h; } C[3] = {
            {0x0012b454u + 0x47600u, o_draw, &cb_cdraw, cb_cdraw_fn},
            {0x0012b31fu + 0x47600u, o_hide, &cb_chide, cb_chide_fn},
            {0x00144fbcu + 0x47600u, o_blit, &cb_cblit, cb_cblit_fn}};
        for (k = 0; k < 3; k++) {
            u8 st[5];
            int bad = 0;
            if (*C[k].cb <= 0) *C[k].cb = alloc_cb(C[k].h);
            if (*C[k].cb <= 0) continue;
            for (i = 0; i < 5; i++) {
                u32 fo = C[k].off + i;
                if (fo >= pos && fo < pos + n && buf[fo - pos] != C[k].orig[i]) bad = 1;
            }
            if (bad) { LOG("矢印の差し込み先が違う %08x", C[k].off); continue; }
            st[0] = 0xFE; st[1] = 0x38; st[2] = (u8)*C[k].cb; st[3] = (u8)(*C[k].cb >> 8); st[4] = 0x90;
            overlay(buf, pos, n, C[k].off, st, 5);
            if (C[k].off >= pos && C[k].off < pos + n) { got |= 1 << k; LOG("矢印の差し込み %08x", C[k].off); }
        }
        curhook = got == 7;
    }
}

/* ===================== ファイルの横取り ===================== */
typedef void *(__cdecl *fopen_t)(const char *, const char *);
typedef size_t (__cdecl *fread_t)(void *, size_t, size_t, void *);
typedef int (__cdecl *fseek_t)(void *, long, int);
typedef long (__cdecl *ftell_t)(void *);
typedef int (__cdecl *fclose_t)(void *);
static fopen_t r_fopen; static fread_t r_fread; static fseek_t r_fseek; static ftell_t r_ftell; static fclose_t r_fclose;

typedef struct { void *fp; int exe; const RFile *rf; u32 pos; const RFile *pf; RFile own; } VF;

/* 絵の文字の差し替え（IMGP: [名前 32][大きさ u32][写す数 u32][置く数 u32][細かい字の数 u32]
   [行き先 u32 写し元 u32]... [行き先|色<<24 u32]... [x u16 y u16 前 u8 後 u8 色 u8 0]...） */
static RFile ifiles[256]; static int nifiles;
static void load_imgp(void)
{
    u32 n, p = 0;
    const u8 *s = find_sec("IMGP", &n);
    if (!s) return;
    while (p + 36 <= n && nifiles < 256) {
        u32 sz = *(const u32 *)(s + p + 32);
        ifiles[nifiles].name = (const char *)(s + p);
        ifiles[nifiles].size = sz;
        ifiles[nifiles].data = s + p + 36;
        nifiles++;
        p += 36 + ((sz + 3) & ~3u);
    }
}
static void hi_add(s32 x, s32 y, u8 a, u8 b, u8 color);
/* 元のファイルを全部読んで指示を当てた版を作る。失敗したら 0 */
static u8 *build_imgp(void *fp, const RFile *ip, u32 *outsz)
{
    long sz;
    u8 *org, *out;
    const u32 *q = (const u32 *)ip->data;
    u32 nc = q[0], ns = q[1], nh = q[2], i;
    const u8 *hp;
    if (r_fseek(fp, 0, SEEK_END)) return 0;
    sz = r_ftell(fp);
    r_fseek(fp, 0, SEEK_SET);
    if (sz <= 0 || sz > 4 * 1024 * 1024) return 0;
    org = (u8 *)malloc(sz); out = (u8 *)malloc(sz);
    if (!org || !out) { free(org); free(out); return 0; }
    if (r_fread(org, 1, sz, fp) != (size_t)sz) { free(org); free(out); r_fseek(fp, 0, SEEK_SET); return 0; }
    r_fseek(fp, 0, SEEK_SET);
    memcpy(out, org, sz);
    q += 3;
    for (i = 0; i < nc; i++, q += 2) if (q[0] < (u32)sz && q[1] < (u32)sz) out[q[0]] = org[q[1]];
    for (i = 0; i < ns; i++, q++) { u32 d = q[0] & 0xffffff; if (d < (u32)sz) out[d] = (u8)(q[0] >> 24); }
    hp = (const u8 *)q;
    {
        /* 字ごとの 8x8 の印（hi の並びの後ろ。古いデータには無い） */
        const u8 *vmp = (12 + nc * 8 + ns * 4 + nh * 16 <= ip->size) ? hp + nh * 8 : 0;
        static u16 owners;
        u16 owner = (u16)(++owners ? owners : ++owners);   /* どの絵の字か（読むたびに新しい番号） */
        for (i = 0; i < nh; i++, hp += 8) {
            int k;
            hi_add(*(const u16 *)hp, *(const u16 *)(hp + 2), hp[4], hp[5], hp[6]);
            /* 絵の字は、画面にある限りずっと使う */
            if (hi_inited) for (k = hi_head[*(const u16 *)(hp + 2)]; k >= 0; k = hi_next[k])
                if (hi_ent[k].x == *(const u16 *)hp && hi_ent[k].color == hp[6]) {
                    hi_ent[k].perm = 1; hi_ent[k].owner = owner;
                    if (vmp) memcpy(hi_ent[k].vm, vmp + i * 8, 8);
                    /* 絵は読んだだけで画面に出るとは限らない（人物の画面の絵は、経歴の画面の裏でも読み直される）。
                       確かめる点のある行が全部合うまで描かない（確かめる点の無い行を先に描いて、点が 1 フレームだけ出た） */
                    {
                        const u16 *g8 = jglyph(&jf8, hi_ent[k].a, hi_ent[k].b);
                        int r; u8 br = 0;
                        if (g8) for (r = 0; r < 8; r++) if ((g8[r] >> 8) & hi_ent[k].vm[r]) br |= (u8)(1 << r);
                        hi_ent[k].badrows = br;
                        if (br) hi_ent[k].ok = 0;
                    }
                }
        }
    }
    free(org);
    *outsz = (u32)sz;
    return out;
}

/* 読み込むときに数バイトだけ書き換えるファイル（PTCH: [名前 32][大きさ u32][[位置 u32][長さ u32][中身]...]） */
static RFile pfiles[64]; static int npfiles;
static void load_patches(void)
{
    u32 n, p = 0;
    const u8 *s = find_sec("PTCH", &n);
    if (!s) return;
    while (p + 36 <= n && npfiles < 64) {
        u32 sz = *(const u32 *)(s + p + 32);
        pfiles[npfiles].name = (const char *)(s + p);
        pfiles[npfiles].size = sz;
        pfiles[npfiles].data = s + p + 36;
        npfiles++;
        p += 36 + ((sz + 3) & ~3u);
    }
}
static void overlay(u8 *buf, u32 pos, u32 n, u32 off, const u8 *src, u32 len);
static void apply_patches(const RFile *pf, u8 *buf, u32 pos, u32 n)
{
    u32 p = 0;
    while (p + 8 <= pf->size) {
        u32 off = *(const u32 *)(pf->data + p), len = *(const u32 *)(pf->data + p + 4);
        overlay(buf, pos, n, off, pf->data + p + 8, len);
        p += 8 + ((len + 3) & ~3u);
    }
}
static VF vfs[64];
static CRITICAL_SECTION vf_cs;
static VF *vf_find(void *fp)
{
    int i;
    for (i = 0; i < 64; i++) if (vfs[i].fp == fp) return &vfs[i];
    return 0;
}

/* 名前の終わりが "ARENA2\TEXT.RSC" などに合うか（大文字小文字・区切りを問わない） */
static int tail_match(const char *path, const char *name)
{
    size_t lp = strlen(path), ln = strlen(name), i;
    if (ln > lp) return 0;
    path += lp - ln;
    if (lp > ln && path[-1] != '\\' && path[-1] != '/') return 0;
    for (i = 0; i < ln; i++) {
        char a = path[i], b = name[i];
        if (a == '/') a = '\\';
        if (a >= 'a' && a <= 'z') a -= 32;
        if (a != b) return 0;
    }
    return 1;
}

static void *__cdecl my_fopen(const char *path, const char *mode)
{
    void *fp = r_fopen(path, mode);
    int i, exe;
    const RFile *rf = 0, *pf = 0;
    if (!fp || !path) return fp;
    exe = tail_match(path, "FALL.EXE");
    if (!exe && mode && !strchr(mode, 'w') && !strchr(mode, 'a')) {
        for (i = 0; i < nrfiles; i++) if (tail_match(path, rfiles[i].name)) { rf = &rfiles[i]; break; }
        if (!rf) for (i = 0; i < npfiles; i++) if (tail_match(path, pfiles[i].name)) { pf = &pfiles[i]; break; }
    }
    if (!exe && !rf && !pf && mode && !strchr(mode, 'w') && !strchr(mode, 'a')) {
        for (i = 0; i < nifiles; i++) if (tail_match(path, ifiles[i].name)) {
            u32 sz = 0;
            u8 *d = build_imgp(fp, &ifiles[i], &sz);
            VF *v;
            if (!d) break;
            EnterCriticalSection(&vf_cs);
            v = vf_find(0);
            if (v) {
                memset(v, 0, sizeof *v);
                v->fp = fp; v->own.name = ifiles[i].name; v->own.data = d; v->own.size = sz; v->rf = &v->own;
            } else free(d);
            LeaveCriticalSection(&vf_cs);
            LOG("fopen %s → 絵の文字を差し替え", path);
            return fp;
        }
    }
    if (exe || rf || pf) {
        VF *v;
        EnterCriticalSection(&vf_cs);
        v = vf_find(0);
        if (v) { memset(v, 0, sizeof *v); v->fp = fp; v->exe = exe; v->rf = rf; v->pos = 0; v->pf = pf; }
        LeaveCriticalSection(&vf_cs);
        LOG("fopen %s (%s)%s", path, mode, rf ? " → 差し替え" : "");
    }
    return fp;
}

static size_t __cdecl my_fread(void *buf, size_t sz, size_t cnt, void *fp)
{
    VF *v = fp ? vf_find(fp) : 0;
    u32 n, pos;
    if (!v) return r_fread(buf, sz, cnt, fp);
    if (v->exe || v->pf) {
        long p0 = r_ftell(fp);
        size_t r = r_fread(buf, sz, cnt, fp);
        if (r && v->exe) patch_read((u8 *)buf, (u32)p0, (u32)(r * sz));
        if (r && v->pf) apply_patches(v->pf, (u8 *)buf, (u32)p0, (u32)(r * sz));
        return r;
    }
    n = (u32)(sz * cnt);
    pos = v->pos;
    if (pos >= v->rf->size || !sz) return 0;
    if (n > v->rf->size - pos) n = v->rf->size - pos;
    n -= n % sz;
    memcpy(buf, v->rf->data + pos, n);
    v->pos = pos + n;
    return n / sz;
}
static int __cdecl my_fseek(void *fp, long off, int whence)
{
    VF *v = fp ? vf_find(fp) : 0;
    long np;
    if (!v || !v->rf) return r_fseek(fp, off, whence);
    np = whence == SEEK_SET ? off : whence == SEEK_CUR ? (long)v->pos + off : (long)v->rf->size + off;
    if (np < 0) return -1;
    v->pos = (u32)np;
    return 0;
}
static long __cdecl my_ftell(void *fp)
{
    VF *v = fp ? vf_find(fp) : 0;
    if (!v || !v->rf) return r_ftell(fp);
    return (long)v->pos;
}
static int __cdecl my_fclose(void *fp)
{
    VF *v = fp ? vf_find(fp) : 0;
    if (v) {
        EnterCriticalSection(&vf_cs);
        if (v->own.data) free((void *)v->own.data);
        memset(v, 0, sizeof *v);
        LeaveCriticalSection(&vf_cs);
    }
    return r_fclose(fp);
}

/* ===================== 取り付け ===================== */
static void put32(u32 addr, u32 val)
{
    DWORD old;
    VirtualProtect((void *)addr, 4, PAGE_EXECUTE_READWRITE, &old);
    *(u32 *)addr = val;
    VirtualProtect((void *)addr, 4, old, &old);
}

static int check_dosbox(void)
{
    static const u8 loopcall[7] = {0xff, 0x14, 0x85, 0x60, 0xb4, 0x75, 0x00};
    HMODULE crt = GetModuleHandleA("msvcrt.dll");
    if ((uintptr_t)GetModuleHandleA(NULL) != 0x400000 || !crt) return 0;
    if (IsBadReadPtr((void *)DB_LOOPCALL, 7) || memcmp((void *)DB_LOOPCALL, loopcall, 7)) return 0;
    if (*(void **)IAT_FOPEN != (void *)GetProcAddress(crt, "fopen")) return 0;
    if (*(void **)IAT_FREAD != (void *)GetProcAddress(crt, "fread")) return 0;
    if (*(void **)IAT_FSEEK != (void *)GetProcAddress(crt, "fseek")) return 0;
    if (*(void **)IAT_FTELL != (void *)GetProcAddress(crt, "ftell")) return 0;
    if (*(void **)IAT_FCLOSE != (void *)GetProcAddress(crt, "fclose")) return 0;
    return 1;
}

static void load_blob(HMODULE self)
{
    HRSRC r = FindResourceA(self, "DFJP", (LPCSTR)RT_RCDATA);
    HGLOBAL g;
    u32 sz;
    if (!r) return;
    g = LoadResource(self, r);
    sz = SizeofResource(self, r);
    if (!g || sz < 8) return;
    blob = (const u8 *)LockResource(g); blobsize = sz;
    if (memcmp(blob, "DFJP", 4)) { blob = 0; return; }
    { u32 n; cmap = (const u16 *)find_sec("CMAP", &n); ncmap = cmap ? n / 2 : 0; }
    load_font(&jf8, "FN08"); load_font(&jf12, "FN12"); load_font(&jf14, "FN14"); load_font(&jf16, "FN16");
    load_files();
    load_patches();
    load_imgp();
}

static void install(HMODULE self)
{
    char path[MAX_PATH], *q;
    GetModuleFileNameA(self, path, MAX_PATH);
    q = strrchr(path, '\\');
    if (q) {
        strcpy(q + 1, "dfjp_debug.txt");
        if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) {
            strcpy(q + 1, "dfjp_dump.txt"); strcpy(dump_path, path);
#ifdef TESTCTL
            strcpy(q + 1, "dfjp_nocur.txt");     /* 試験用: 矢印はゲームが描く（前の版と比べる） */
            if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) nocur = 1;
#endif
            strcpy(q + 1, "dfjp.log");
            logfp = fopen(path, "w");
        }
    }
    if (!check_dosbox()) { LOG("DOSBox の版が違うので何もしない"); return; }
    if (q) {
        strcpy(q + 1, "dfjp_off.txt");      /* 試験用: 英語のまま動かす */
        if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES) { LOG("dfjp_off.txt があるので差し替えない"); return; }
    }
    InitializeCriticalSection(&vf_cs);
    load_blob(self);
    LOG("データ %u バイト、字 %u、差し替えファイル %d", blobsize, ncmap, nrfiles);
    r_fopen = *(fopen_t *)IAT_FOPEN; r_fread = *(fread_t *)IAT_FREAD; r_fseek = *(fseek_t *)IAT_FSEEK;
    r_ftell = *(ftell_t *)IAT_FTELL; r_fclose = *(fclose_t *)IAT_FCLOSE;
    put32(IAT_FOPEN, (u32)my_fopen); put32(IAT_FREAD, (u32)my_fread); put32(IAT_FSEEK, (u32)my_fseek);
    put32(IAT_FTELL, (u32)my_ftell); put32(IAT_FCLOSE, (u32)my_fclose);
    /* 細かい字: VGA_DrawPart の call [RENDER_DrawLine] を差し替える（字体が無い・命令が違うときはしない） */
    {
        static const u8 call[6] = {0xff, 0x15, 0x50, 0x16, 0xef, 0x01};
        if (HIF->full && !memcmp((void *)DB_DRAWLINE_CALL1, call, 6) && !memcmp((void *)DB_DRAWLINE_CALL2, call, 6)) {
            u32 at[2] = {DB_DRAWLINE_CALL1, DB_DRAWLINE_CALL2};
            int k;
            for (k = 0; k < 2; k++) {
                DWORD old;
                u8 *p = (u8 *)at[k];
                VirtualProtect(p, 6, PAGE_EXECUTE_READWRITE, &old);
                p[0] = 0xE8; *(u32 *)(p + 1) = (u32)my_drawline - (at[k] + 5); p[5] = 0x90;
                VirtualProtect(p, 6, old, &old);
                FlushInstructionCache(GetCurrentProcess(), p, 6);
            }
            hi_init();
            LOG("細かい字を有効にした");
        }
    }
    LOG("取り付け完了");
}

/* ===================== winmm の転送 ===================== */
#include "winmm_exports.h"
#define DECL(n) static FARPROC p_##n;
WINMM_FUNCS(DECL)
static void load_winmm(void)
{
    char path[MAX_PATH];
    HMODULE w;
    GetSystemDirectoryA(path, MAX_PATH);
    lstrcatA(path, "\\winmm.dll");
    w = LoadLibraryA(path);
    if (!w) return;
#define GETP(n) p_##n = GetProcAddress(w, #n);
    WINMM_FUNCS(GETP)
}
#define THUNK(n) __declspec(naked) void ex_##n(void) { __asm { jmp dword ptr [p_##n] } }
WINMM_FUNCS(THUNK)

#ifdef TESTCTL
#include "testctl.inc"
#endif

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        load_winmm();
        install(h);
#ifdef TESTCTL
        ctl_start();
#endif
    }
    return TRUE;
}
