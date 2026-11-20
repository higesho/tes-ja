/* The Elder Scrolls: Arena 日本語化 DLL（GOG 版 DOSBox 0.74-2 に winmm.dll として読ませる） */
#pragma once
#include <windows.h>
#include <stdint.h>
#include <string.h>

/* ---- DOSBox 0.74-2 (GOG, md5 2318a4462513382c45298be63ec007d8) の内部 ---- */
typedef uint32_t (*CB_Handler)(void);
#define DBX_CBTABLE     ((CB_Handler *)0x75B460)   /* CallBack_Handlers[128] */
#define DBX_CBMAX       128
#define DBX_REGS        ((volatile uint32_t *)0x75B1E0) /* eax ecx edx ebx esp ebp esi edi */
#define DBX_EIP         (*(volatile uint32_t *)0x75B200)
#define DBX_FLAGS       (*(volatile uint32_t *)0x75B204)
#define DBX_SEGVAL(i)   (((volatile uint16_t *)0x75B100)[i])   /* 0.74-2 は Bit16u val[8] */
#define DBX_SEGPHYS(i)  (((volatile uint32_t *)0x75B110)[i])
#define DBX_MEMBASE     (*(uint8_t **)0x1D4A380)
#define DBX_INT21       0x4B2350                    /* DOS_21Handler */
#define DBX_LOOPCALL    0x4017EA                    /* Normal_Loop: call [eax*4+CallBack_Handlers] */
#define DBX_MEMWRITEB   0x4F67A0                    /* void mem_writeb(PhysPt, Bit8u) */
#define DBX_IAT_FOPEN   0x243198C                   /* msvcrt!fopen の IAT */
#define DBX_MEMREADB    0x4F64B0                    /* Bit8u mem_readb(PhysPt) */
typedef void (__cdecl *MemWriteB)(uint32_t, uint32_t);
typedef uint32_t (__cdecl *MemReadB)(uint32_t);
#define vwr8(a, v) (((MemWriteB)DBX_MEMWRITEB)((a), (v)))
#define vrd8(a) ((uint8_t)((MemReadB)DBX_MEMREADB)(a))

enum { R_AX, R_CX, R_DX, R_BX, R_SP, R_BP, R_SI, R_DI };
enum { S_ES, S_CS, S_SS, S_DS };
#define FLAG_CF 0x0001

static __inline uint16_t reg16(int r) { return (uint16_t)DBX_REGS[r]; }
static __inline void set16(int r, uint16_t v) { DBX_REGS[r] = (DBX_REGS[r] & 0xFFFF0000u) | v; }
static __inline uint8_t *lin(uint32_t a) { return DBX_MEMBASE + a; }
/* 0xA0000 以上（VGA・EMS のページ枠など）は DOSBox の処理を通す */
static __inline uint8_t rd8(uint32_t a) { return a < 0xA0000 ? DBX_MEMBASE[a] : vrd8(a); }
static __inline uint16_t rd16(uint32_t a) { return (uint16_t)(rd8(a) | (rd8(a + 1) << 8)); }
static __inline void wr8(uint32_t a, uint8_t v) { if (a < 0xA0000) DBX_MEMBASE[a] = v; else vwr8(a, v); }
static __inline void wr16(uint32_t a, uint16_t v) { wr8(a, (uint8_t)v); wr8(a + 1, (uint8_t)(v >> 8)); }
static __inline uint32_t farptr(uint32_t a) { return ((uint32_t)rd16(a + 2) << 4) + rd16(a); }
static __inline uint32_t segbase(int s) { return DBX_SEGVAL(s) << 4; }

/* main.c */
extern char g_dir[MAX_PATH];
extern int g_trace;
extern int g_nopatch;
extern int g_nostr, g_nohook;
void LogF(const char *fmt, ...);
int  AllocCallback(CB_Handler h);

/* game.c */
void Game_Init(void);
void Game_Tick(void);
uint32_t Game_DG(void);

/* hires.c */
int  Hires_Install(const char *fontpath);
void Hires_Note(int sx, int sy, uint8_t c1, uint8_t c2, uint8_t col, uint16_t seg);

/* img.c */
void Img_Load(const char *path);
int  Img_Has(const char *name);
int  Img_Any(void);
uint8_t *Img_Patch(const char *name, const uint8_t *d, uint32_t n, uint32_t *outn);

/* files.c */
void Files_Install(void);

/* testctl.c */
void TestCtl_Start(void);
void TestCtl_Before(uint32_t cb, uint16_t *ax);
void TestCtl_After(uint16_t ax);
extern int g_test;

/* text.c */
uint8_t *ReadAll(const char *path, uint32_t *size);
int  Font_Load(const char *path);
const uint8_t *Font_Glyph(uint8_t c1, uint8_t c2);
