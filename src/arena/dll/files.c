/* DOSBox が開くゲームのファイルを日本語版に振り替える（msvcrt!fopen の IAT 横取り）
   ・ARENAJP\data\ にある同名のファイル（訳した文章だけのファイル）はそれを開く
   ・原作のデータを含むものは、原作を読んで差分を当てた写しを一時ファイル（閉じれば消える）で渡す
       GLOBAL.BSA   … 中の INF の *TEXT を inf.bin の訳に替える
       SPELLSG.65 / SPELLS.LST … 呪文の名前を spells.bin の訳に替える
       POINTER1.DAT … 後半（TEMPLATE.DAT の見出しの位置+1）を訳した TEMPLATE.DAT に合わせる */
#include "arenajp.h"
#include <stdio.h>
#include <stdlib.h>

typedef FILE *(__cdecl *FopenFn)(const char *, const char *);
typedef size_t (__cdecl *FwriteFn)(const void *, size_t, size_t, FILE *);
typedef int (__cdecl *FseekFn)(FILE *, long, int);
static FopenFn g_fopen;
static FwriteFn pfwrite;
static FseekFn pfseek;

#define MAXF 64
static char g_names[MAXF][16];
static int g_nfiles;
static char g_datadir[MAX_PATH];
static uint8_t *g_inf, *g_spells;
static uint32_t g_infsize, g_spellsize;
static int g_haspics;

static const char *BaseName(const char *p)
{
    const char *b = p, *s;
    for (s = p; *s; s++) if (*s == '\\' || *s == '/' || *s == ':') b = s + 1;
    return b;
}

/* 中身を一時ファイルに書いて、先頭に戻した FILE* を返す（DOSBox と同じ msvcrt の FILE） */
static FILE *TempFile(const void *d, uint32_t n)
{
    char tmpdir[MAX_PATH], tmp[MAX_PATH];
    FILE *f;
    if (!pfwrite || !pfseek) return NULL;
    GetTempPathA(MAX_PATH, tmpdir);
    GetTempFileNameA(tmpdir, "arj", 0, tmp);
    f = g_fopen(tmp, "w+bD");
    if (!f) return NULL;
    pfwrite(d, 1, n, f);
    pfseek(f, 0, SEEK_SET);
    return f;
}

/* ---------- INF の *TEXT を差し替える ----------
   inf.bin: "ARJI" u32 件数, {char 名前[13], u16 番号, u16 長さ, 文}* */
static const uint8_t KEYS[8] = { 0xEA, 0x7B, 0x4E, 0xBD, 0x19, 0xC9, 0x38, 0x99 };

static int InfFindText(const uint8_t *t, uint32_t n, int id, uint32_t *b, uint32_t *e)
{
    char key[24];
    int kl = wsprintfA(key, "*TEXT %d\r\n", id);
    uint32_t i, j;
    for (i = 0; i + kl <= n; i++) {
        if (memcmp(t + i, key, kl)) continue;
        /* 「*TEXT 1」が「*TEXT 10」に当たらないよう、行頭であることも見る */
        if (i > 0 && t[i - 1] != '\n') continue;
        *b = i + kl;
        for (j = *b; j < n; j++) {
            if (j + 2 < n && t[j] == '\r' && t[j + 1] == '\n' && (t[j + 2] == '*' || t[j + 2] == '@')) break;
        }
        *e = j;
        return 1;
    }
    return 0;
}

/* 平文の INF に訳を当てる。新しい中身（malloc）を返す。当てるものがなければ NULL */
static uint8_t *PatchInf(const char *name, const uint8_t *src, uint32_t n, uint32_t *outn)
{
    uint32_t cnt, p = 8, k, cur = n;
    uint8_t *t = NULL;
    if (!g_inf || g_infsize < 8) return NULL;
    cnt = *(uint32_t *)(g_inf + 4);
    for (k = 0; k < cnt && p + 17 <= g_infsize; k++) {
        const char *nm = (const char *)g_inf + p;
        uint16_t id = *(uint16_t *)(g_inf + p + 13), len = *(uint16_t *)(g_inf + p + 15);
        const uint8_t *s = g_inf + p + 17;
        uint32_t b, e;
        p += 17 + len;
        if (lstrcmpiA(nm, name)) continue;
        if (!t) { t = (uint8_t *)malloc(n + 1); memcpy(t, src, n); }
        if (InfFindText(t, cur, id, &b, &e)) {
            uint8_t *u = (uint8_t *)malloc(cur - (e - b) + len + 1);
            memcpy(u, t, b);
            memcpy(u + b, s, len);
            memcpy(u + b + len, t + e, cur - e);
            cur = cur - (e - b) + len;
            free(t); t = u;
        }
    }
    if (t) *outn = cur;
    return t;
}

static FILE *OpenBsa(const char *path)
{
    uint32_t size, n, idx, pos, i, rep = 0, osz = 0, cap;
    uint8_t *d = ReadAll(path, &size), *out;
    FILE *f;
    if (!d || size < 2) { free(d); return NULL; }
    n = d[0] | (d[1] << 8);
    if (size < 2 + n * 18) { free(d); return NULL; }
    idx = size - n * 18;
    cap = size + 1024 * 1024;
    out = (uint8_t *)malloc(cap);
    memcpy(out, d, 2); osz = 2;
    pos = 2;
    for (i = 0; i < n; i++) {
        uint8_t *e = d + idx + i * 18;
        uint32_t esz = e[14] | (e[15] << 8) | (e[16] << 16) | ((uint32_t)e[17] << 24);
        char name[16];
        uint8_t *nb = NULL;
        uint32_t nsz = 0, k;
        memcpy(name, e, 12); name[12] = 0;
        if (lstrlenA(name) > 4 && !lstrcmpiA(name + lstrlenA(name) - 4, ".INF")) {
            uint8_t *plain = (uint8_t *)malloc(esz + 1);
            for (k = 0; k < esz; k++) plain[k] = d[pos + k] ^ (uint8_t)((k & 0xFF) + KEYS[k % 8]);
            nb = PatchInf(name, plain, esz, &nsz);
            free(plain);
            if (nb) for (k = 0; k < nsz; k++) nb[k] ^= (uint8_t)((k & 0xFF) + KEYS[k % 8]);
        } else if (Img_Has(name)) {
            nb = Img_Patch(name, d + pos, esz, &nsz);
        }
        if (nb) {
            if (osz + nsz > cap) { cap = osz + nsz + 1024 * 1024; out = (uint8_t *)realloc(out, cap); }
            memcpy(out + osz, nb, nsz); osz += nsz;
            e[14] = (uint8_t)nsz; e[15] = (uint8_t)(nsz >> 8); e[16] = (uint8_t)(nsz >> 16); e[17] = (uint8_t)(nsz >> 24);
            free(nb);
            rep++;
        } else {
            if (osz + esz > cap) { cap = osz + esz + 1024 * 1024; out = (uint8_t *)realloc(out, cap); }
            memcpy(out + osz, d + pos, esz); osz += esz;
        }
        pos += esz;
    }
    if (osz + n * 18 > cap) out = (uint8_t *)realloc(out, osz + n * 18);
    memcpy(out + osz, d + idx, n * 18); osz += n * 18;
    f = TempFile(out, osz);
    free(out); free(d);
    LogF("GLOBAL.BSA の INF・絵 %u 個を差し替えて渡す", rep);
    return f;
}

/* ---------- 呪文の名前 ----------
   spells.bin: "ARJS" u32 件数, {u16 番号, u8 長さ, 名前}* */
static FILE *OpenSpells(const char *path)
{
    uint32_t size, cnt, p = 8, k;
    uint8_t *d = ReadAll(path, &size);
    FILE *f;
    if (!d) return NULL;
    cnt = *(uint32_t *)(g_spells + 4);
    for (k = 0; k < cnt && p + 3 <= g_spellsize; k++) {
        uint16_t i = *(uint16_t *)(g_spells + p);
        uint8_t len = g_spells[p + 2];
        if (len > 32) len = 32;
        if ((uint32_t)i * 85 + 85 <= size) {
            memset(d + i * 85 + 52, 0, 33);
            memcpy(d + i * 85 + 52, g_spells + p + 3, len);
        }
        p += 3 + g_spells[p + 2];
    }
    f = TempFile(d, size);
    free(d);
    LogF("呪文の名前を差し替えて渡す: %s", BaseName(path));
    return f;
}

/* ---------- POINTER1.DAT（後半 2500 個の u32 = TEMPLATE.DAT の見出し '#' の位置+1） ---------- */
static FILE *OpenPointer(const char *path)
{
    char tp[MAX_PATH];
    uint32_t size, tsize, i, k = 0;
    uint8_t *d = ReadAll(path, &size), *t;
    FILE *f;
    wsprintfA(tp, "%s\\TEMPLATE.DAT", g_datadir);
    t = ReadAll(tp, &tsize);
    if (!d || !t || size < 20000) { free(d); free(t); return NULL; }
    for (i = 0; i < tsize && k < 2500; i++) {
        if (t[i] == '#' && (i == 0 || t[i - 1] == '\n')) {
            uint32_t v = i + 1;
            memcpy(d + 10000 + k * 4, &v, 4);
            k++;
        }
    }
    f = TempFile(d, size);
    free(d); free(t);
    LogF("POINTER1.DAT を訳した TEMPLATE.DAT（見出し %u 個）に合わせて渡す", k);
    return f;
}

static int InData(const char *b)
{
    int i;
    for (i = 0; i < g_nfiles; i++) if (!lstrcmpiA(b, g_names[i])) return 1;
    return 0;
}

static int ImgKeyHas(const char *b)
{
    char key[MAX_PATH];
    wsprintfA(key, "_%s", b);
    return Img_Has(key);
}

static FILE *__cdecl MyFopen(const char *path, const char *mode)
{
    if (path && _strnicmp(path, g_datadir, lstrlenA(g_datadir))) {
        const char *b = BaseName(path);
        FILE *f = NULL;
        if ((g_inf || g_haspics) && !lstrcmpiA(b, "GLOBAL.BSA")) f = OpenBsa(path);
        else if (ImgKeyHas(b)) {
            /* ばらのファイルの絵は「_名前」の差分を当てる（BSA の中の同名の絵とは中身が違う） */
            char key[MAX_PATH];
            uint32_t sz, nsz;
            uint8_t *d = ReadAll(path, &sz), *nb;
            wsprintfA(key, "_%s", b);
            if (d && (nb = Img_Patch(key, d, sz, &nsz)) != NULL) { f = TempFile(nb, nsz); free(nb); LogF("絵を差し替えて渡す: %s", b); }
            free(d);
        }
        else if (g_spells && (!lstrcmpiA(b, "SPELLSG.65") || !lstrcmpiA(b, "SPELLS.LST"))) f = OpenSpells(path);
        else if (!lstrcmpiA(b, "POINTER1.DAT") && InData("TEMPLATE.DAT")) f = OpenPointer(path);
        else if (InData(b)) {
            char p[MAX_PATH];
            wsprintfA(p, "%s\\%s", g_datadir, b);
            f = g_fopen(p, "rb");
            if (f) LogF("振り替え %s", b);
        }
        if (f) return f;
    }
    return g_fopen(path, mode);
}

void Files_Install(void)
{
    WIN32_FIND_DATAA fd;
    HANDLE h;
    char pat[MAX_PATH];
    DWORD old;
    FopenFn *iat = (FopenFn *)DBX_IAT_FOPEN;
    HMODULE m = GetModuleHandleA("msvcrt.dll");
    pfwrite = (FwriteFn)GetProcAddress(m, "fwrite");
    pfseek = (FseekFn)GetProcAddress(m, "fseek");
    wsprintfA(g_datadir, "%s\\data", g_dir);
    wsprintfA(pat, "%s\\*", g_datadir);
    h = FindFirstFileA(pat, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            if (lstrlenA(fd.cFileName) >= 16 || g_nfiles >= MAXF) continue;
            lstrcpyA(g_names[g_nfiles++], fd.cFileName);
        } while (FindNextFileA(h, &fd));
        FindClose(h);
    }
    wsprintfA(pat, "%s\\inf.bin", g_dir);
    g_inf = ReadAll(pat, &g_infsize);
    if (g_inf && (g_infsize < 8 || memcmp(g_inf, "ARJI", 4))) { free(g_inf); g_inf = NULL; }
    wsprintfA(pat, "%s\\spells.bin", g_dir);
    g_spells = ReadAll(pat, &g_spellsize);
    if (g_spells && (g_spellsize < 8 || memcmp(g_spells, "ARJS", 4))) { free(g_spells); g_spells = NULL; }
    wsprintfA(pat, "%s\\pics.bin", g_dir);
    Img_Load(pat);
    g_haspics = Img_Any();
    LogF("振り替えるファイル %d 個、INF %s、呪文 %s", g_nfiles, g_inf ? "あり" : "なし", g_spells ? "あり" : "なし");
    g_fopen = *iat;
    VirtualProtect(iat, 4, PAGE_READWRITE, &old);
    *iat = MyFopen;
    VirtualProtect(iat, 4, old, &old);
}
