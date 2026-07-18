@echo off
setlocal

rem Always build relative to the directory containing this script.
pushd "%~dp0"

set "TEX_FILE=report.tex"
if not "%~1"=="" set "TEX_FILE=%~1"

if not exist "%TEX_FILE%" (
    echo [ERROR] TeX source not found: %TEX_FILE%
    popd
    exit /b 1
)

where xelatex >nul 2>&1
if errorlevel 1 (
    echo [ERROR] xelatex was not found in PATH.
    echo Install MiKTeX or TeX Live, then reopen the terminal.
    popd
    exit /b 1
)

where latexmk >nul 2>&1
if not errorlevel 1 (
    echo [BUILD] latexmk + XeLaTeX: %TEX_FILE%
    latexmk -xelatex -interaction=nonstopmode -halt-on-error "%TEX_FILE%"
    if errorlevel 1 goto :build_failed
    goto :build_ok
)

echo [1/2] XeLaTeX: %TEX_FILE%
xelatex -interaction=nonstopmode -halt-on-error "%TEX_FILE%"
if errorlevel 1 goto :build_failed

echo [2/2] Updating references and table of contents...
xelatex -interaction=nonstopmode -halt-on-error "%TEX_FILE%"
if errorlevel 1 goto :build_failed

:build_ok
for %%F in ("%TEX_FILE%") do set "PDF_FILE=%%~nF.pdf"
echo.
echo [OK] PDF created: %~dp0%PDF_FILE%
popd
exit /b 0

:build_failed
echo.
echo [ERROR] PDF build failed. Check the corresponding .log file.
popd
exit /b 1
