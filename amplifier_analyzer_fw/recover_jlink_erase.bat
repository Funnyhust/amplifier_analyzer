@echo off
setlocal EnableExtensions

set "JLINK=%USERPROFILE%\.platformio\packages\tool-jlink\JLink.exe"
set "SCRIPT=%~dp0recover_erase.jlink"

if not exist "%JLINK%" (
    for /f "delims=" %%I in ('where JLink.exe 2^>nul') do set "JLINK=%%I"
)

if not exist "%JLINK%" (
    echo [ERROR] JLink.exe not found.
    echo Install SEGGER J-Link or PlatformIO tool-jlink first.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERROR] Missing command file: %SCRIPT%
    pause
    exit /b 1
)

echo ============================================================
echo STM32F103C8 J-Link continuous mass-erase recovery
echo.
echo Wiring required:
echo   J-Link VTref  -^> target 3V3
echo   J-Link GND    -^> target GND
echo   J-Link SWDIO  -^> PA13
echo   J-Link SWCLK  -^> PA14
echo   J-Link RESET  -^> NRST  ^(strongly recommended^)
echo.
echo Hold target RESET now, start this script, then release RESET.
echo Set BOOT0=1 and power-cycle if the running firmware disables SWD.
echo Press Ctrl+C immediately after an erase succeeds.
echo ============================================================
echo.

set /a ATTEMPT=0

:retry
set /a ATTEMPT+=1
echo.
echo ---------------- ERASE ATTEMPT %ATTEMPT% ----------------

"%JLINK%" -NoGui 1 -Device STM32F103C8 -If SWD -Speed 50 -AutoConnect 1 -ExitOnError 1 -CommanderScript "%SCRIPT%"

echo Attempt %ATTEMPT% finished. Retrying in 1 second...
timeout /t 1 /nobreak >nul
goto retry
