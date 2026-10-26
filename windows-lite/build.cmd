@echo off
rem Run as administrator
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath \"%~f0\"" & exit /b)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-lite-iso.ps1" %*
pause
