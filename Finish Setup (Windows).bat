@echo off
rem Double-click once on Windows. The dispatcher is a set of bash scripts, so it runs inside WSL (Ubuntu). Experimental path: see README.
setlocal
cd /d "%~dp0"
where wsl >nul 2>nul
if errorlevel 1 (
  echo WSL is not installed. Open PowerShell as Administrator and run:  wsl --install -d Ubuntu
  echo Restart the computer, open Ubuntu once to create a user, then double-click this file again.
  pause
  exit /b 1
)
for /f "usebackq delims=" %%i in (`wsl wslpath -a "%~dp0."`) do set KITW=%%i
echo Agent Ops Kit: finishing setup inside WSL (Ubuntu)...
wsl -e bash -lc "bash '%KITW%/finish-setup-wsl.sh'"
if errorlevel 1 (
  echo Something above needs attention. Fix it and double-click this file again.
  pause
  exit /b 1
)
rem Start the dispatcher at every Windows logon, and now.
schtasks /create /tn "AgentOps" /sc onlogon /tr "wsl.exe -e bash -lc \"'%KITW%/start-loop-wsl.sh'\"" /f >nul
schtasks /run /tn "AgentOps" >nul
echo.
echo Done. Open http://localhost:8787/ in your browser.
pause
