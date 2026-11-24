@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
set O=..\build\release
set OUT=winmm.dll
set DEF=
if "%1"=="test" (
  set O=..\build\test
  set OUT=..\build\test\winmm.dll
  set DEF=/DDFJP_TEST
)
if not exist %O% mkdir %O%
rc /nologo /fo %O%\dfjp.res dfjp.rc || exit /b 1
cl /nologo /O2 /W3 /MT /LD /utf-8 %DEF% dfjp.c %O%\dfjp.res /Fo%O%\ /Fe:%OUT% /link /DEF:winmm.def /IMPLIB:%O%\winmm.lib kernel32.lib user32.lib || exit /b 1
