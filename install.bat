@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1

set PYTHON_EXE=python

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe
)

"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
    echo Python не найден или не запускается.
    echo Установите Python 3.11+ с https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Готово. Для запуска используйте run.bat
pause
