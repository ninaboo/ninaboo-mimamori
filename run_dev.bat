@echo off
REM Run from source without building (after build.bat has created .venv once).
cd /d "%~dp0"
.venv\Scripts\python.exe main.py
