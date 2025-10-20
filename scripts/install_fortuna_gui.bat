@echo off
REM Interactive MSI installation with standard Windows UI

title Fortuna Faucet Installation Wizard

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Administrator privileges required
    echo Please right-click this file and select "Run as Administrator"
    pause
    exit /b 1
)

REM Assumes the MSI is in the 'dist' subfolder relative to the project root
msiexec.exe /i "..\dist\Fortuna-Faucet-2.1.0-x64.msi" /L*v "%TEMP%\fortuna_install.log"

if %errorlevel% equ 0 (
    echo Installation completed successfully!
    echo Access dashboard at: http://localhost:3000
) else (
    echo Installation failed. Log: %TEMP%\fortuna_install.log
)
pause