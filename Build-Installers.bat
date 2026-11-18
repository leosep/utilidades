@echo off
REM Double-click to build the installers on Windows (needs Python 3.10+ and Inno Setup 6).
cd /d "%~dp0"
python -m pip install -r packaging\requirements-build.txt
if errorlevel 1 goto done
python packaging\build.py
:done
pause
