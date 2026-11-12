@echo off
REM Builds / updates dist\Mimamori\Mimamori.exe
REM Safe to re-run: only the exe and _internal are replaced. Your config,
REM downloaded engine, models and logs in dist\Mimamori are kept.
REM Needs Python 3.11 or 3.12 (64-bit) from python.org on PATH.
REM Translation runs in llama.cpp's own llama-server.exe, which Mimamori downloads
REM itself on first use (CPU or GPU build, chosen by the GPU layers setting).
setlocal
cd /d "%~dp0"

REM Mimamori must be closed: Windows won't let us replace files it has open.
REM (Closing the window only hides it to the tray.)
if /I not "%~1"=="__logged" (
    tasklist /FI "IMAGENAME eq Mimamori.exe" 2>nul | find /I "Mimamori.exe" >nul && (
        echo.
        echo  Mimamori is running ^(maybe hidden in the tray^), so it can't be updated.
        choice /C YN /M " Close it now"
        if errorlevel 2 (
            echo  OK - quit Mimamori from its tray icon, then run build.bat again.
            pause
            exit /b 1
        )
        taskkill /F /T /IM Mimamori.exe >nul 2>&1
        timeout /t 2 /nobreak >nul
        echo  Closed.
        echo.
    )
)

REM Re-run this script with all output saved to build.log, then show the result
if /I not "%~1"=="__logged" (
    echo Building Mimamori... this takes a few minutes. Full details go to build.log
    echo.
    call "%~f0" __logged %* > build.log 2>&1
    if errorlevel 1 (
        echo.
        echo  Build FAILED. Last lines of build.log:
        echo.
        powershell -NoProfile -Command "Get-Content build.log -Tail 20"
    ) else (
        echo.
        echo  ============================================================
        echo   Done!  Run:  dist\Mimamori\Mimamori.exe
        echo   Your config, voice engine and model were left alone.
        echo  ============================================================
    )
    echo.
    pause
    exit /b
)
set MODE=%~2

if not exist .venv (
    py -3.11 -m venv .venv 2>nul || python -m venv .venv
)
set PY=.venv\Scripts\python.exe
"%PY%" -c "import sys" || goto :fail

echo  [1/4] Updating the Python setup... >con

"%PY%" -m pip install --upgrade pip
echo  [2/4] Installing packages... >con
"%PY%" -m pip install -r requirements.txt || goto :fail


echo  [3/4] Building the exe (the slow part, a few minutes)... >con
REM Build into a staging folder, never straight into dist\Mimamori
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name Mimamori ^
    --icon assets\mimamori.ico ^
    --add-data "assets;assets" ^
    --distpath build\stage ^
    --collect-all fugashi ^
    --collect-all unidic_lite ^
    --hidden-import unidic_lite ^
    main.py || goto :fail

echo  [4/4] Copying it into dist\Mimamori... >con
if not exist dist\Mimamori mkdir dist\Mimamori
if exist dist\Mimamori\_internal rmdir /s /q dist\Mimamori\_internal
xcopy /e /i /y /q build\stage\Mimamori\_internal dist\Mimamori\_internal >nul || goto :fail
copy /y build\stage\Mimamori\Mimamori.exe dist\Mimamori\ >nul || goto :fail
REM tidy up the exe from before the rename
if exist dist\Mimamori\AnkiAutoFill.exe del /q dist\Mimamori\AnkiAutoFill.exe

echo.
echo ============================================================
echo  Done!  Your app is in:  dist\Mimamori\
echo  (config, engine and models in that folder were left alone)
echo ============================================================
goto :eof

:fail
echo.
echo Build failed - see the messages above.
exit /b 1
