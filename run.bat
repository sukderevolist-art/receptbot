@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe bot.py
) else if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    "%LocalAppData%\Programs\Python\Python313\python.exe" bot.py
) else (
    python bot.py
)
