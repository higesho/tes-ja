/* 試験用の操作口（loljp.ini の [Debug] Test=1 のときだけ）
   共有メモリ Local\ARJP_CTL_<pid> に命令を書くと、SDL のイベントとして積む */
#include "arenajp.h"

typedef struct { uint8_t type, which, state; uint16_t x, y; int16_t xrel, yrel; } SMotion;
typedef struct { uint8_t type, which, button, state; uint16_t x, y; } SButton;
typedef struct { uint8_t scancode; int sym; int mod; uint16_t unicode; } SKeysym;
typedef struct { uint8_t type, which, state; SKeysym keysym; } SKey;

typedef union { uint8_t type; uint8_t pad[64]; } SEvent;

typedef struct {
    volatile LONG seq, ack;
    int cmd, a, b, c, d;
    int w, h, pitch, bpp;          /* 撮影の結果 */
    uint8_t pad[4096 - 52];
    uint8_t pix[1280 * 960 * 4];   /* 撮影の画素 */
} Ctl;

typedef struct { uint32_t flags; void *format; int w, h; uint16_t pitch; void *pixels; } SSurface;
typedef struct { void *palette; uint8_t BitsPerPixel, BytesPerPixel; } SFormat;
static SSurface *(__cdecl *pGetVideoSurface)(void);
static int (__cdecl *pLockSurface)(SSurface *);
static void (__cdecl *pUnlockSurface)(SSurface *);

static int (__cdecl *pPushEvent)(SEvent *);
static Ctl *g_ctl;

static void Push(SEvent *e) { if (pPushEvent) pPushEvent(e); }

/* マウス位置の強制（INT 33h AX=3 の答えを書き換える）。x,y はゲームの 320x200 */
volatile int g_mfx = -1, g_mfy = -1;
static int g_mxmax = 639, g_mymax = 199, g_int33 = -1;

static int FindInt33(void)
{
    uint32_t v = rd16(0x33 * 4) + ((uint32_t)rd16(0x33 * 4 + 2) << 4);
    int k;
    if (rd8(v) == 0xEB) v += 2 + (int8_t)rd8(v + 1);
    for (k = 0; k < 16; k++)
        if (rd8(v + k) == 0xFE && rd8(v + k + 1) == 0x38) return rd16(v + k + 2);
    return -1;
}

void TestCtl_Before(uint32_t cb, uint16_t *ax)
{
    g_int33 = FindInt33();
    *ax = (cb == (uint32_t)g_int33) ? reg16(R_AX) : 0xFFFF;
    if (*ax != 0xFFFF && g_trace) {
        static int seen[64];
        if (*ax < 64 && seen[*ax] < 3) { seen[*ax]++; LogF("INT33 AX=%X CX=%X DX=%X", *ax, reg16(R_CX), reg16(R_DX)); }
    }
    if (*ax == 7) g_mxmax = reg16(R_DX);
    if (*ax == 8) g_mymax = reg16(R_DX);
}

void TestCtl_After(uint16_t ax)
{
    if (ax == 3 && g_mfx >= 0) {
        set16(R_CX, (uint16_t)(g_mfx * (g_mxmax + 1) / 320));
        set16(R_DX, (uint16_t)(g_mfy * (g_mymax + 1) / 200));
    }
}

static void DoCmd(int cmd, int a, int b, int c, int d)
{
    SEvent e;
    memset(&e, 0, sizeof e);
    switch (cmd) {
    case 1: { /* 移動 a=x b=y（窓の座標） */
        SMotion *m = (SMotion *)&e;
        m->type = 4; m->x = (uint16_t)a; m->y = (uint16_t)b; m->xrel = (int16_t)c; m->yrel = (int16_t)d;
        Push(&e); break; }
    case 2: { /* ボタン a=1左 3右 b=1押す 0離す c,d=座標 */
        SButton *bt = (SButton *)&e;
        bt->type = b ? 5 : 6; bt->button = (uint8_t)a; bt->state = (uint8_t)b; bt->x = (uint16_t)c; bt->y = (uint16_t)d;
        Push(&e); break; }
    case 5: { /* 撮影: SDL の画面の画素を写す */
        SSurface *sf = pGetVideoSurface ? pGetVideoSurface() : NULL;
        g_ctl->w = 0;
        if (sf && sf->pixels && (int)sf->pitch * sf->h <= (int)sizeof g_ctl->pix) {
            if (pLockSurface) pLockSurface(sf);
            g_ctl->w = sf->w; g_ctl->h = sf->h; g_ctl->pitch = sf->pitch;
            g_ctl->bpp = ((SFormat *)sf->format)->BitsPerPixel;
            memcpy(g_ctl->pix, sf->pixels, sf->pitch * sf->h);
            if (pUnlockSurface) pUnlockSurface(sf);
        }
        break; }
    case 4: /* マウス位置の強制 a=x b=y（a<0 で解除） */
        g_mfx = a; g_mfy = b; break;
    case 3: { /* キー a=scancode b=sym c=1押す 0離す d=unicode */
        SKey *k = (SKey *)&e;
        k->type = c ? 2 : 3; k->state = (uint8_t)c; k->keysym.scancode = (uint8_t)a; k->keysym.sym = b; k->keysym.unicode = (uint16_t)d;
        Push(&e); break; }
    }
}

static DWORD WINAPI CtlThread(LPVOID p)
{
    LONG last = 0;
    for (;;) {
        Sleep(5);
        if (g_ctl->seq != last) {
            last = g_ctl->seq;
            DoCmd(g_ctl->cmd, g_ctl->a, g_ctl->b, g_ctl->c, g_ctl->d);
            g_ctl->ack = last;
        }
    }
    return 0;
}

void TestCtl_Start(void)
{
    char name[64];
    HANDLE m;
    HMODULE sdl = GetModuleHandleA("SDL.dll");
    if (!sdl) sdl = LoadLibraryA("SDL.dll");
    pPushEvent = (int (__cdecl *)(SEvent *))GetProcAddress(sdl, "SDL_PushEvent");
    pGetVideoSurface = (SSurface *(__cdecl *)(void))GetProcAddress(sdl, "SDL_GetVideoSurface");
    pLockSurface = (int (__cdecl *)(SSurface *))GetProcAddress(sdl, "SDL_LockSurface");
    pUnlockSurface = (void (__cdecl *)(SSurface *))GetProcAddress(sdl, "SDL_UnlockSurface");
    wsprintfA(name, "Local\\ARJP_CTL_%lu", GetCurrentProcessId());
    m = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(Ctl), name);
    if (!m) return;
    g_ctl = (Ctl *)MapViewOfFile(m, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(Ctl));
    if (!g_ctl) return;
    CreateThread(NULL, 0, CtlThread, NULL, 0, NULL);
    LogF("試験の操作口 %s", name);
}
