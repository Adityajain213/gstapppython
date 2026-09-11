# Invoice Extractor

Python/Kivy invoice-to-Excel app for personal/internal Android use.

## Current features
- Purchase and Sale modes.
- OCR extraction and editable review.
- Local Purchase.xlsx and Sale.xlsx files.
- Bill images are not permanently stored.
- After saving: success notification, form reset, and return to the next upload screen.
- Home screen has **View Purchase Excel** and **View Sale Excel** buttons.
- Windows opens the workbook in the registered spreadsheet application.
- Android copies the workbook to a shared Downloads/InvoiceExtractor folder and opens it with Excel, Google Sheets, or another compatible spreadsheet app.

## Windows test
```text
python main.py
```

## Android packaging
Use Buildozer/WSL or another Linux Android build environment with the included `buildozer.spec`.
