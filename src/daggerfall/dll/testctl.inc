/* 試験用の操作口（build_test.bat で TESTCTL を付けたときだけ入る。配布物には入れない）
   共有メモリ Local\DFJP_CTL_<pid> に命令を書くと、SDL のイベントとして積む */
typedef struct { uint8_t type, which, state; uint16_t x, y; int16_t xrel, yrel; } SMotion;
typedef struct { uint8_t type, which, button, state; uint16_t x, y; } SButton;
typedef struct { uint8_t scancode; int sym; int mod; uint16_t unicode; } SKeysym;
typedef struct { uint8_t type, which, state; SKeysym keysym; } SKey;
typedef union { uint8_t type; uint8_t pad[64]; } SEvent;
typedef struct { volatile LONG seq, ack; int cmd, a, b, c, d; } Ctl;

static int (__cdecl *pPushEvent)(SEvent *);
static Ctl *g_ctl;

static void ctl_do(int cmd, int a, int b, int c, int d)
{
    SEvent e;
    memset(&e, 0, sizeof e);
    if (!pPushEvent) {
        HMODULE sdl = GetModuleHandleA("SDL.dll");
        if (sdl) pPushEvent = (int (__cdecl *)(SEvent *))GetProcAddress(sdl, "SDL_PushEvent");
        if (!pPushEvent) return;
    }
    if (cmd == 1) {
        SMotion *m = (SMotion *)&e;
        m->type = 4; m->x = (uint16_t)a; m->y = (uint16_t)b; m->xrel = (int16_t)c; m->yrel = (int16_t)d;
    } else if (cmd == 2) {
        SButton *bt = (SButton *)&e;
        bt->type = b ? 5 : 6; bt->button = (uint8_t)a; bt->state = (uint8_t)b; bt->x = (uint16_t)c; bt->y = (uint16_t)d;
    } else if (cmd == 3) {
        SKey *k = (SKey *)&e;
        k->type = c ? 2 : 3; k->state = (uint8_t)c; k->keysym.scancode = (uint8_t)a; k->keysym.sym = b; k->keysym.unicode = (uint16_t)d;
    } else return;
    pPushEvent(&e);
}

static DWORD WINAPI ctl_thread(LPVOID p)
{
    LONG last = 0;
    (void)p;
    for (;;) {
        Sleep(5);
        if (g_ctl->seq != last) {
            last = g_ctl->seq;
            ctl_do(g_ctl->cmd, g_ctl->a, g_ctl->b, g_ctl->c, g_ctl->d);
            g_ctl->ack = last;
        }
    }
}

static void ctl_start(void)
{
    char name[64];
    HANDLE m;
    wsprintfA(name, "Local\\DFJP_CTL_%lu", GetCurrentProcessId());
    m = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, 4096, name);
    if (!m) return;
    g_ctl = (Ctl *)MapViewOfFile(m, FILE_MAP_ALL_ACCESS, 0, 0, 4096);
    if (!g_ctl) return;
    CreateThread(NULL, 0, ctl_thread, NULL, 0, NULL);
}
