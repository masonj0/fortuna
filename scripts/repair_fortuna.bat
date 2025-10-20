@echo off
REM Repair corrupted or missing files

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Admin rights required
    exit /b 1
)

echo Repairing Fortuna Faucet installation...

REM /f flag performs repair. Assumes MSI is in the 'dist' folder.
msiexec.exe /f "..\dist\Fortuna-Faucet-2.1.0-x64.msi" ^
    /qn ^
    /l*v "%TEMP%\fortuna_repair.log"

if %errorlevel% equ 0 (
    echo Repair completed successfully.
) else (
    echo Repair failed. Check log: %TEMP%\fortuna_repair.log
)

exit /b %errorlevel%