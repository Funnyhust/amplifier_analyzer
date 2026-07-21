@echo off
setlocal
pushd "%~dp0"

set "PYTHON_EXE=python"
if exist "..\..\app_desktop\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\..\app_desktop\.venv\Scripts\python.exe"
) else if exist "..\..\app_desktop\.venv-local\Scripts\python.exe" (
    set "PYTHON_EXE=..\..\app_desktop\.venv-local\Scripts\python.exe"
)

echo [1/2] Converting Markdown to LaTeX...
"%PYTHON_EXE%" convert_md_to_tex.py
if errorlevel 1 goto :failed

echo [2/2] Building PDF with XeLaTeX...
xelatex -interaction=nonstopmode -halt-on-error study_guide.tex
if errorlevel 1 goto :failed
xelatex -interaction=nonstopmode -halt-on-error study_guide.tex
if errorlevel 1 goto :failed

:ok
echo.
echo [OK] Created: %CD%\study_guide.pdf
popd
exit /b 0

:failed
echo.
echo [ERROR] Build failed. Check study_guide.log.
pause
popd
exit /b 1
