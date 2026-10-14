@echo off
chcp 65001 >nul
title Code Focus
setlocal
set "TOOL=%~dp0"
if "%TOOL:~-1%"=="\" set "TOOL=%TOOL:~0,-1%"

rem ---------- find a Python ----------
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && set "PY=py"
)
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
  )
)
if not defined PY goto NOPY

rem ---------- make sure pygments is there ----------
"%PY%" -c "import pygments" >nul 2>nul
if errorlevel 1 (
  echo [i] Installing dependency: pygments ...
  "%PY%" -m pip install pygments
)

cd /d "%TOOL%"
"%PY%" "%TOOL%\ask.py"
echo.
pause
exit /b 0

:NOPY
echo.
echo   [!] Python not found.
echo.
echo   Install Python 3.8+  :  https://www.python.org/downloads/
echo   During setup TICK the box "Add python.exe to PATH".
echo   Then double-click this file again.
echo.
pause
exit /b 1
