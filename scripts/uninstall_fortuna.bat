@echo off
REM Complete removal of Fortuna Faucet

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Admin rights required
    exit /b 1
)

echo WARNING: This will remove Fortuna Faucet completely.
set /p confirm="Are you sure? (y/N): "

if /i not "%confirm%"=="y" exit /b 0

REM Find and remove MSI by UpgradeCode
for /f "tokens=2 delims=" %%A in ('wmic product where "Name like 'Fortuna Faucet%%'" get IdentifyingNumber /value') do (
    for /f "tokens=2 delims==" %%B in ("%%A") do (
        msiexec.exe /x %%B /qn /l*v "%TEMP%\fortuna_uninstall.log"
    )
)

REM Clean up directories
if exist "%PROGRAMFILES%\Fortuna Faucet" rmdir /s /q "%PROGRAMFILES%\Fortuna Faucet" 2>nul
if exist "%APPDATA%\Fortuna Faucet" rmdir /s /q "%APPDATA%\Fortuna Faucet" 2>nul

echo Uninstall complete.