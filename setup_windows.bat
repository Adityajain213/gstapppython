@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo Invoice Extractor - Windows Setup
echo ============================================

echo.
echo [1/3] Installing Python packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package installation failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Checking Tesseract OCR...
where tesseract >nul 2>&1
if errorlevel 1 (
    echo Tesseract is not installed or is not in PATH.
    echo.
    echo If winget is available, run:
    echo   winget install UB-Mannheim.TesseractOCR
    echo.
    echo Then close and reopen PowerShell before running the app.
) else (
    echo Tesseract found:
    tesseract --version | findstr /B /C:"tesseract"
)

echo.
echo [3/3] Setup complete.
echo Run the app with:
echo   python main.py
pause
