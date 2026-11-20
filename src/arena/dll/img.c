/* 絵（IMG / MNU）の日本語化: 原作の絵を解読して pics.bin の差分（四角い部分）を当て、無圧縮の絵にする
   pics.bin: "ARJX" u32 件数, {char 名前[13], u16 x, u16 y, u16 w, u16 h, 画素（元との XOR） w*h}*
   圧縮の解読は OpenTESArena（Compression.h）を C に写したもの */
#include "arenajp.h"
#include <stdlib.h>

static uint8_t *g_pics;
static uint32_t g_picsize;

static const struct { const char *n; int w, h; } RAWIMG[] = {
    {"ARENARW.IMG",16,16},{"CITY.IMG",16,11},{"DITHER.IMG",8,100},{"DITHER2.IMG",8,100},{"DUNGEON.IMG",14,8},
    {"DZTTAV.IMG",32,34},{"NOCAMP.IMG",25,19},{"NOSPELL.IMG",25,19},{"P1.IMG",320,53},{"POPTALK.IMG",320,77},
    {"S2.IMG",320,36},{"SLIDER.IMG",289,7},{"TOWN.IMG",9,10},{"UPDOWN.IMG",8,16},{"VILLAGE.IMG",8,8}};

static void Type04(const uint8_t *s, const uint8_t *e, uint8_t *out, int n)
{
    uint8_t hist[4096];
    int hp = 0, o = 0, bits = 0, mask = 0;
    memset(hist, 0x20, sizeof hist);
    while (s < e && o < n) {
        if (!bits) { bits = 8; mask = *s++; } else mask >>= 1;
        if (mask & 1) {
            if (s >= e) break;
            hist[hp++ & 0xFFF] = *s; out[o++] = *s++;
        } else {
            int b1, b2, cnt, cp, i;
            if (e - s < 2) break;
            b1 = *s++; b2 = *s++;
            cnt = (b2 & 0x0F) + 3; cp = (((b2 & 0xF0) << 4) | b1) + 18;
            for (i = 0; i < cnt && o < n; i++) { uint8_t v = hist[cp++ & 0xFFF]; hist[hp++ & 0xFFF] = v; out[o++] = v; }
        }
        bits--;
    }
    while (o < n) out[o++] = 0;
}

static uint8_t HIGH[256], LOWC[256];
static void InitTables(void)
{
    int i = 0, v, c;
    static const int hb[][2] = { {0,32},{1,16},{2,16},{3,16} };
    if (LOWC[0]) return;
    for (v = 0; v < 4; v++) for (c = 0; c < hb[v][1]; c++) HIGH[i++] = (uint8_t)hb[v][0];
    for (v = 4; v < 12; v++) for (c = 0; c < 8; c++) HIGH[i++] = (uint8_t)v;
    for (v = 12; v < 24; v++) for (c = 0; c < 4; c++) HIGH[i++] = (uint8_t)v;
    for (v = 24; v < 48; v++) for (c = 0; c < 2; c++) HIGH[i++] = (uint8_t)v;
    for (v = 48; v < 64; v++) HIGH[i++] = (uint8_t)v;
    i = 0;
    for (c = 0; c < 32; c++) LOWC[i++] = 3;
    for (c = 0; c < 48; c++) LOWC[i++] = 4;
    for (c = 0; c < 64; c++) LOWC[i++] = 5;
    for (c = 0; c < 48; c++) LOWC[i++] = 6;
    for (c = 0; c < 48; c++) LOWC[i++] = 7;
    for (c = 0; c < 16; c++) LOWC[i++] = 8;
}

static void Type08(const uint8_t *s, const uint8_t *e, uint8_t *out, int n)
{
    static uint8_t hist[4096];
    static uint16_t idxmap[941], tree[627], freq[627];
    uint16_t bm = 0;
    int vb = 0, hp = 0, o = 0, i, k;
    InitTables();
    memset(hist, 0x20, sizeof hist);
    for (i = 0; i < 626; i++) idxmap[i] = (uint16_t)((i >> 1) + 314);
    idxmap[626] = 0;
    for (i = 627; i < 941; i++) idxmap[i] = (uint16_t)(i - 627);
    for (i = 0; i < 314; i++) tree[i] = (uint16_t)(627 + i);
    for (i = 314; i < 627; i++) tree[i] = (uint16_t)((i - 314) * 2);
    for (i = 0; i < 314; i++) freq[i] = 1;
    for (i = 314, k = 0; i < 627; i++, k += 2) freq[i] = (uint16_t)(freq[k] + freq[k + 1]);
#define FILL() while (vb < 9) { if (s < e) bm |= (uint16_t)(*s++ << (8 - vb)); vb += 8; }
    while (o < n) {
        uint16_t node = tree[626], fi, cw;
        while (node < 627) {
            FILL();
            node = tree[node + ((bm >> 15) & 1)];
            bm <<= 1; vb--;
        }
        fi = idxmap[node];
        do {
            uint16_t f, ni;
            freq[fi]++;
            f = freq[fi]; ni = (uint16_t)(fi + 1);
            if (ni < 627 && freq[ni] < f) {
                uint16_t t, m;
                while (ni < 627 && freq[ni] < f) ni++;
                ni--;
                freq[fi] = freq[ni]; freq[ni] = f;
                t = tree[fi]; tree[fi] = tree[ni]; tree[ni] = t;
                m = tree[ni]; idxmap[m] = ni; if (m < 627) idxmap[m + 1] = ni;
                m = tree[fi]; idxmap[m] = fi; if (m < 627) idxmap[m + 1] = fi;
                fi = ni;
            }
            fi = idxmap[fi];
        } while (fi != 0);
        cw = (uint16_t)(node - 627);
        if (cw < 256) { hist[hp++ & 0xFFF] = (uint8_t)cw; out[o++] = (uint8_t)cw; }
        else {
            uint8_t ti; uint16_t oh, bc, ol, cp, cnt, j;
            FILL();
            ti = (uint8_t)(bm >> 8); bm <<= 8; vb -= 8;
            oh = (uint16_t)(HIGH[ti] << 6); bc = (uint16_t)(LOWC[ti] - 2); ol = ti;
            for (j = 0; j < bc; j++) { FILL(); ol = (uint16_t)((ol << 1) | ((bm >> 15) & 1)); bm <<= 1; vb--; }
            cp = (uint16_t)(hp - (oh | (ol & 0x3F)) - 1);
            cnt = (uint16_t)(cw - 256 + 3);
            for (j = 0; j < cnt && o < n; j++) { uint8_t v = hist[cp++ & 0xFFF]; hist[hp++ & 0xFFF] = v; out[o++] = v; }
        }
    }
#undef FILL
}

/* 名前の差分があれば、新しい中身（malloc）を返す。なければ NULL */
uint8_t *Img_Patch(const char *name, const uint8_t *d, uint32_t n, uint32_t *outn)
{
    uint32_t cnt, p = 8, k, rawsz = 0;
    int w = 0, h = 0, raw = -1, i, hit = 0;
    uint16_t flags = 0, len = 0;
    uint8_t *pix = NULL, *out;
    if (!g_pics) return NULL;
    cnt = *(uint32_t *)(g_pics + 4);
    for (k = 0; k < cnt && p + 21 <= g_picsize; k++) {
        uint16_t pw = *(uint16_t *)(g_pics + p + 17), ph = *(uint16_t *)(g_pics + p + 19);
        if (!lstrcmpiA((const char *)g_pics + p, name)) { hit = 1; break; }
        p += 21 + pw * ph;
    }
    if (!hit) return NULL;
    for (i = 0; i < (int)(sizeof RAWIMG / sizeof RAWIMG[0]); i++)
        if (!lstrcmpiA(name + (name[0] == '_'), RAWIMG[i].n)) { raw = i; w = RAWIMG[i].w; h = RAWIMG[i].h; }
    if (raw >= 0) {
        rawsz = w * h;
        if (n < rawsz) return NULL;
        pix = (uint8_t *)malloc(rawsz); memcpy(pix, d, rawsz);
    } else {
        if (n < 12) return NULL;
        w = *(uint16_t *)(d + 4); h = *(uint16_t *)(d + 6);
        flags = *(uint16_t *)(d + 8); len = *(uint16_t *)(d + 10);
        if (w <= 0 || h <= 0 || w * h > 64000 || 12u + len > n) return NULL;
        pix = (uint8_t *)malloc(w * h);
        if ((flags & 0xFF) == 0) memcpy(pix, d + 12, w * h);
        else if ((flags & 0xFF) == 4) Type04(d + 12, d + 12 + len, pix, w * h);
        else if ((flags & 0xFF) == 8) Type08(d + 14, d + 12 + len, pix, w * h);
        else { free(pix); return NULL; }
    }
    /* 差分を当てる（同じ名前の四角が続けて並んでいる） */
    p = 8;
    for (k = 0; k < cnt && p + 21 <= g_picsize; k++) {
        const char *nm = (const char *)g_pics + p;
        int x = *(uint16_t *)(g_pics + p + 13), y = *(uint16_t *)(g_pics + p + 15);
        int pw = *(uint16_t *)(g_pics + p + 17), ph = *(uint16_t *)(g_pics + p + 19), r;
        const uint8_t *s = g_pics + p + 21;
        p += 21 + pw * ph;
        if (lstrcmpiA(nm, name)) continue;
        /* 画素は元の絵との XOR（原作の画素そのものは持たない） */
        for (r = 0; r < ph; r++)
            if (y + r < h && x + pw <= w) {
                uint8_t *q = pix + (y + r) * w + x; const uint8_t *t = s + r * pw; int i;
                for (i = 0; i < pw; i++) q[i] ^= t[i];
            }
    }
    if (raw >= 0) { *outn = rawsz; return pix; }
    {
        uint32_t pal = (flags & 0x100) ? 768 : 0, tail = n - (12 + len);
        if (pal > tail) pal = tail;
        out = (uint8_t *)malloc(12 + w * h + pal);
        memcpy(out, d, 12);
        *(uint16_t *)(out + 8) = (uint16_t)(flags & 0xFF00);
        *(uint16_t *)(out + 10) = (uint16_t)(w * h);
        memcpy(out + 12, pix, w * h);
        if (pal) memcpy(out + 12 + w * h, d + 12 + len, pal);
        *outn = 12 + w * h + pal;
        free(pix);
        return out;
    }
}

int Img_Has(const char *name)
{
    uint32_t cnt, p = 8, k;
    if (!g_pics) return 0;
    cnt = *(uint32_t *)(g_pics + 4);
    for (k = 0; k < cnt && p + 21 <= g_picsize; k++) {
        uint16_t pw = *(uint16_t *)(g_pics + p + 17), ph = *(uint16_t *)(g_pics + p + 19);
        if (!lstrcmpiA((const char *)g_pics + p, name)) return 1;
        p += 21 + pw * ph;
    }
    return 0;
}

void Img_Load(const char *path)
{
    g_pics = ReadAll(path, &g_picsize);
    if (g_pics && (g_picsize < 8 || memcmp(g_pics, "ARJX", 4))) { free(g_pics); g_pics = NULL; }
    LogF("絵の差分 %s", g_pics ? "あり" : "なし");
}

int Img_Any(void) { return g_pics != NULL; }
