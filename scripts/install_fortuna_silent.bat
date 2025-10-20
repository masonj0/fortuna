@echo off
REM Automated deployment (no UI, minimal interaction)

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Admin rights required
    exit /b 1
)

REM Assumes the MSI is in the 'dist' subfolder relative to the project root
msiexec.exe /i "..\dist\Fortuna-Faucet-2.1.0-x64.msi" ^
    /qn ^
    /l*v "%TEMP%\fortuna_silent_install.log" ^
    /norestart ^
    ALLUSERS=1 ^
    INSTALLSCOPE=perMachine

exit /b %errorlevel%