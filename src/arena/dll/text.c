/* 日本語フォント（美咲 8x8、EUC 区点順 94x94x8 バイト） */
#include "arenajp.h"
#include <stdio.h>
#include <stdlib.h>

static uint8_t *g_font;

uint8_t *ReadAll(const char *path, uint32_t *size)
{
    FILE *f = fopen(path, "rb");
    uint8_t *b;
    long n;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
    b = (uint8_t *)malloc(n + 1);
    if (b && fread(b, 1, n, f) != (size_t)n) { free(b); b = NULL; }
    fclose(f);
    if (b) { b[n] = 0; if (size) *size = (uint32_t)n; }
    return b;
}

int Font_Load(const char *path)
{
    uint32_t size;
    g_font = ReadAll(path, &size);
    return g_font && size >= 94*94*8;
}

const uint8_t *Font_Glyph(uint8_t c1, uint8_t c2)
{
    if (c1 < 0xA1 || c1 > 0xFE || c2 < 0xA1 || c2 > 0xFE) return NULL;
    return g_font + (((c1 - 0xA1) * 94) + (c2 - 0xA1)) * 8;
}
