@echo off
setlocal

pushd "%~dp0"

where xelatex >nul 2>&1
if errorlevel 1 (
    echo [ERROR] xelatex was not found in PATH.
    echo Install MiKTeX or TeX Live, then reopen the terminal.
    popd
    exit /b 1
)

echo [1/2] Building report.tex...
xelatex -interaction=nonstopmode -halt-on-error report.tex
if errorlevel 1 goto :build_failed

echo [2/2] Updating table of contents and references...
xelatex -interaction=nonstopmode -halt-on-error report.tex
if errorlevel 1 goto :build_failed

echo.
echo [OK] Build completed: %~dp0report.pdf
popd
exit /b 0

:build_failed
echo.
echo [ERROR] Build failed. See report.log for details.
popd
exit /b 1
