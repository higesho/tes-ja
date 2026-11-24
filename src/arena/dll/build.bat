@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d %~dp0
set O=out
set OUT=out\winmm.dll
set DEF=
set EXTRA=
if "%1"=="test" (
  set O=..\build\test
  set OUT=..\build\test\winmm.dll
  set DEF=/DARJP_TEST
  set EXTRA=testctl.c
)
if not exist %O% mkdir %O%
rc /nologo /fo %O%\arenajp.res arenajp.rc || exit /b 1
cl /nologo /O1 /MT /W3 /utf-8 /GS- /D_CRT_SECURE_NO_WARNINGS %DEF% /LD main.c game.c files.c hires.c img.c text.c %EXTRA% %O%\arenajp.res /Fo:%O%\ /Fe:%OUT% /link /DEF:winmm.def /DYNAMICBASE:NO kernel32.lib user32.lib || exit /b 1
