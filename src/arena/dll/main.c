/* winmm.dll の代理と DOSBox への差し込み */
#include "arenajp.h"
#include <stdio.h>
#include <stdarg.h>

char g_dir[MAX_PATH];
int g_trace;
int g_nopatch;
int g_test;
int g_nostr, g_nohook;
static HMODULE g_winmm;
static int g_log;

/* ---------- winmm の転送 ---------- */
#include "winmm_exports.h"

#define DECL(n) FARPROC p_##n;
WINMM_FUNCS(DECL)

static void LoadWinmm(void)
{
    char path[MAX_PATH];
    GetSystemDirectoryA(path, MAX_PATH);
    lstrcatA(path, "\\winmm.dll");
    g_winmm = LoadLibraryA(path);
#define GETP(n) p_##n = GetProcAddress(g_winmm, #n);
    WINMM_FUNCS(GETP)
}

#define THUNK(n) __declspec(naked) void ex_##n(void) { __asm { jmp dword ptr [p_##n] } }
WINMM_FUNCS(THUNK)

/* ---------- 記録 ---------- */
void LogF(const char *fmt, ...)
{
    char buf[1024], path[MAX_PATH];
    va_list ap;
    FILE *f;
    if (!g_log) return;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof buf - 1, fmt, ap);
    buf[sizeof buf - 1] = 0;
    va_end(ap);
    wsprintfA(path, "%s\\arenajp.log", g_dir);
    f = fopen(path, "a");
    if (f) { fputs(buf, f); fputc('\n', f); fclose(f); }
}

/* ---------- コールバックの割り当て ---------- */
static CB_Handler g_illegal;

static void FindIllegal(void)
{
    int i, j, best = 0;
    for (i = 0; i < DBX_CBMAX; i++) {
        int n = 0;
        for (j = 0; j < DBX_CBMAX; j++) if (DBX_CBTABLE[j] == DBX_CBTABLE[i]) n++;
        if (n > best) { best = n; g_illegal = DBX_CBTABLE[i]; }
    }
}

int AllocCallback(CB_Handler h)
{
    int i;
    if (!g_illegal) FindIllegal();
    for (i = DBX_CBMAX - 1; i > 0; i--) {
        if (DBX_CBTABLE[i] == g_illegal) { DBX_CBTABLE[i] = h; return i; }
    }
    return -1;
}

/* ---------- Normal_Loop の呼び出しを横取り ---------- */
static int g_inited;

static uint32_t __cdecl Dispatch(uint32_t cb)
{
    CB_Handler h = DBX_CBTABLE[cb];
    uint32_t r;
    uint16_t ax = 0xFFFF;
    if (!g_inited) { g_inited = 1; Game_Init(); }
    Game_Tick();
    if (g_test) TestCtl_Before(cb, &ax);
    r = h();
    if (g_test && ax != 0xFFFF) TestCtl_After(ax);
    return r;
}

static __declspec(naked) void DispatchStub(void)
{
    __asm {
        push eax
        call Dispatch
        add esp, 4
        ret
    }
}

static int CheckHost(void)
{
    static const uint8_t loopcall[] = { 0xFF, 0x14, 0x85, 0x60, 0xB4, 0x75, 0x00 };
    static const uint8_t int21[] = { 0x81, 0xEC, 0xCC, 0x06, 0x00, 0x00, 0x0F, 0xB6, 0x0D, 0xE1, 0xB1, 0x75, 0x00 };
    static const uint8_t memalloc[] = { 0xA3, 0x80, 0xA3, 0xD4, 0x01 };
    static const uint8_t memwb[] = { 0x53, 0x83, 0xEC, 0x18, 0x8B, 0x5C, 0x24, 0x20, 0x8B, 0x54, 0x24, 0x24 };
    HMODULE hexe = GetModuleHandleA(NULL);
    if ((uintptr_t)hexe != 0x400000) return 0;
    __try {
        if (memcmp((void *)DBX_LOOPCALL, loopcall, sizeof loopcall)) return 0;
        if (memcmp((void *)DBX_INT21, int21, sizeof int21)) return 0;
        if (memcmp((void *)0x4F7C9C, memalloc, sizeof memalloc)) return 0;
        if (memcmp((void *)DBX_MEMWRITEB, memwb, sizeof memwb)) return 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return 1;
}

static void InstallHook(void)
{
    DWORD old;
    uint8_t *p = (uint8_t *)DBX_LOOPCALL;
    VirtualProtect(p, 8, PAGE_EXECUTE_READWRITE, &old);
    p[0] = 0xE8;
    *(int32_t *)(p + 1) = (int32_t)((uint8_t *)DispatchStub - (p + 5));
    p[5] = 0x90; p[6] = 0x90;
    VirtualProtect(p, 8, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 8);
}

static void Init(HMODULE self)
{
    char ini[MAX_PATH], *s;
    GetModuleFileNameA(self, g_dir, MAX_PATH);
    s = strrchr(g_dir, '\\'); if (s) *s = 0;
    lstrcatA(g_dir, "\\ARENAJP");
    wsprintfA(ini, "%s\\arenajp.ini", g_dir);
    g_log = GetPrivateProfileIntA("Debug", "Log", 0, ini);
    g_trace = GetPrivateProfileIntA("Debug", "TraceText", 0, ini);
    g_nopatch = GetPrivateProfileIntA("Debug", "NoPatch", 0, ini);
    g_nostr = GetPrivateProfileIntA("Debug", "NoStrings", 0, ini);
    g_nohook = GetPrivateProfileIntA("Debug", "NoHooks", 0, ini);
    if (GetPrivateProfileIntA("Main", "Enable", 1, ini) == 0) return;
    if (!CheckHost()) { LogF("DOSBox が想定と違うので何もしない"); return; }
    {
        char p[MAX_PATH];
        wsprintfA(p, "%s\\jpfont8.bin", g_dir);
        if (!Font_Load(p)) { LogF("フォントが読めない: %s", p); return; }
    }
    Files_Install();
    if (GetPrivateProfileIntA("Main", "Hires", 1, ini)) {
        char p[MAX_PATH];
        wsprintfA(p, "%s\\jpfont16.bin", g_dir);
        if (!Hires_Install(p)) LogF("16 ドットの描き直しは使わない");
    }
    InstallHook();
    g_test = GetPrivateProfileIntA("Debug", "Test", 0, ini);
    if (g_test) TestCtl_Start();
    LogF("arenajp: 差し込み完了");
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        LoadWinmm();
        Init(h);
    }
    return TRUE;
}
