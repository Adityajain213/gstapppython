"""OCR abstraction for Windows development and Android packaging.

Windows:
    Uses pytesseract + the Tesseract executable.

Android:
    Uses the native ML Kit bridge when the Android build provides it.

The selected bill image is read temporarily and is never copied into the
application's permanent data storage.
"""

import os


# Standard Windows installation path used by the Winget Tesseract package.
WINDOWS_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _desktop_ocr(image_path: str) -> str:
    """Run Tesseract OCR on Windows/desktop."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Python OCR packages are missing. Run: python -m pip install -r requirements.txt"
        ) from exc

    # If Tesseract is not on PATH, use the standard installation path directly.
    if os.path.exists(WINDOWS_TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = WINDOWS_TESSERACT_PATH

    try:
        # Open the image only for OCR. It is not copied to app storage.
        with Image.open(image_path) as image:
            return pytesseract.image_to_string(image)
    except Exception as exc:
        raise RuntimeError(
            "Tesseract OCR could not run. Verify that Tesseract is installed at "
            f"{WINDOWS_TESSERACT_PATH} or added to PATH. Original error: {exc}"
        ) from exc


def extract_text(image_path: str) -> str:
    """Extract text using Android ML Kit when available, otherwise Tesseract."""
    # Android native bridge. Kept isolated so the parser is platform-independent.
    try:
        from jnius import autoclass

        Bridge = autoclass("com.personal.invoiceextractor.MLKitTextRecognizer")
        return str(Bridge.recognize(image_path))
    except Exception:
        # Desktop fallback for local testing.
        return _desktop_ocr(image_path)
