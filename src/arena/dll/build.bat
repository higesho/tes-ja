@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d %~dp0
if not exist out mkdir out
cl /nologo /O1 /MT /W3 /utf-8 /GS- /D_CRT_SECURE_NO_WARNINGS /LD main.c game.c files.c hires.c img.c text.c testctl.c /Fo:out\ /Fe:out\winmm.dll /link /DEF:winmm.def /DYNAMICBASE:NO kernel32.lib user32.lib
