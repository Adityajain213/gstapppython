"""Local monthly Excel storage for the Invoice Extractor app."""

from pathlib import Path
from openpyxl import Workbook, load_workbook
from datetime import datetime

PURCHASE_HEADERS = [
    "Party Name", "Invoice no.", "Invoice date ", "Place Of Supply",
    "E-commerce e-GSTIN", "Rate", "Taxable amount", "IGST", "CGST", "SGST", "TOTAL"
]

SALE_HEADERS = [
    "GSTIN OF RECIPIENT", "             Party Name", "Invoice no.", "Invoice date ",
    "Invoice value", "Place of supply", "RATE", "HSN CODE", "QUANTITY",
    "TAXABLE VALUE", "IGST", "CGST", "SGST", "TOTAL"
]


def _storage_dir():
    """Use Kivy private app storage on Android and a local folder on Windows."""
    try:
        from kivy.app import App
        return Path(App.get_running_app().user_data_dir) / "workbooks"
    except Exception:
        return Path.home() / "InvoiceExtractorData" / "workbooks"


def _type_dir(invoice_type):
    folder = _storage_dir() / ("Purchase" if invoice_type == "purchase" else "Sale")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _month_name(month_key):
    """Convert YYYY-MM into a friendly month name."""
    try:
        return datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month_key


def _month_key_from_date(value):
    """Extract YYYY-MM from common invoice-date formats."""
    if not value:
        return None
    text = str(value).strip()
    formats = ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def list_workbooks(invoice_type=None):
    """Return all locally stored monthly workbooks, newest month first."""
    roots = []
    if invoice_type in {"purchase", "sale"}:
        roots = [_type_dir(invoice_type)]
    else:
        roots = [_type_dir("purchase"), _type_dir("sale")]

    result = []
    for root in roots:
        kind = "purchase" if root.name.lower() == "purchase" else "sale"
        for path in root.glob("*.xlsx"):
            month_key = path.stem.rsplit("_", 1)[-1]
            result.append({
                "type": kind,
                "path": path,
                "month_key": month_key,
                "month_label": _month_name(month_key),
                "name": path.name,
            })
    result.sort(key=lambda item: (item["month_key"], item["type"]), reverse=True)
    return result


def create_monthly_workbook(invoice_type, month_key):
    """Create a new monthly workbook and return its path."""
    if invoice_type not in {"purchase", "sale"}:
        raise ValueError("Invoice type must be purchase or sale.")
    try:
        datetime.strptime(month_key, "%Y-%m")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM format.") from exc

    folder = _type_dir(invoice_type)
    prefix = "Purchase" if invoice_type == "purchase" else "Sale"
    path = folder / f"{prefix}_{month_key}.xlsx"

    if not path.exists():
        headers = PURCHASE_HEADERS if invoice_type == "purchase" else SALE_HEADERS
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(headers)
        wb.save(path)
    return path


def get_excel_path(invoice_type, month_key=None):
    """Return a monthly workbook path, creating it if a month is supplied."""
    if month_key is None:
        month_key = datetime.now().strftime("%Y-%m")
    return create_monthly_workbook(invoice_type, month_key)


def open_excel(path):
    """Open an Excel workbook in the user's default spreadsheet application."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Excel file does not exist: {path}")

    # Windows desktop testing: use the registered spreadsheet application.
    if __import__('platform').system() == 'Windows':
        import os
        os.startfile(str(path))
        return

    # Android: copy the selected workbook into public Downloads and open it.
    try:
        from jnius import autoclass
        import shutil

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        BuildVersion = autoclass('android.os.Build$VERSION')
        Environment = autoclass('android.os.Environment')
        File = autoclass('java.io.File')
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')

        activity = PythonActivity.mActivity
        filename = path.name
        mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        if int(BuildVersion.SDK_INT) >= 29:
            MediaStore = autoclass('android.provider.MediaStore')
            ContentValues = autoclass('android.content.ContentValues')
            values = ContentValues()
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
            values.put(MediaStore.MediaColumns.MIME_TYPE, mime_type)
            values.put(MediaStore.MediaColumns.RELATIVE_PATH, 'Download/InvoiceExtractor')
            values.put(MediaStore.MediaColumns.IS_PENDING, 1)

            resolver = activity.getContentResolver()
            collection = MediaStore.Downloads.getContentUri('external')
            uri = resolver.insert(collection, values)
            if uri is None:
                raise RuntimeError('Android could not create the Excel file in Downloads.')

            input_stream = open(path, 'rb')
            output_stream = resolver.openOutputStream(uri)
            try:
                while True:
                    chunk = input_stream.read(8192)
                    if not chunk:
                        break
                    output_stream.write(chunk)
                output_stream.flush()
            finally:
                input_stream.close()
                output_stream.close()

            values = ContentValues()
            values.put(MediaStore.MediaColumns.IS_PENDING, 0)
            resolver.update(uri, values, None, None)

            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, mime_type)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            activity.startActivity(intent)
            return

        downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        target_dir = File(downloads, 'InvoiceExtractor')
        target_dir.mkdirs()
        target = File(target_dir, filename)
        shutil.copyfile(str(path), target.getAbsolutePath())

        StrictMode = autoclass('android.os.StrictMode')
        StrictMode.setVmPolicy(StrictMode.VmPolicy.Builder().build())

        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.fromFile(target), mime_type)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        activity.startActivity(intent)

    except Exception as exc:
        raise RuntimeError(
            'No compatible spreadsheet application could open the Excel file. '
            'Please install Microsoft Excel or Google Sheets.'
        ) from exc


def save_invoice(invoice_type, data, workbook_path=None):
    """Append a verified invoice to the selected monthly workbook."""
    if invoice_type not in {"purchase", "sale"}:
        raise ValueError("Invoice type must be purchase or sale.")

    # Use the workbook selected by the user. If none was selected, use the
    # invoice date month so records naturally remain separated by month.
    if workbook_path:
        path = Path(workbook_path)
    else:
        month_key = _month_key_from_date(data.get("invoice_date")) or datetime.now().strftime("%Y-%m")
        path = get_excel_path(invoice_type, month_key)

    path.parent.mkdir(parents=True, exist_ok=True)
    headers = PURCHASE_HEADERS if invoice_type == "purchase" else SALE_HEADERS

    if path.exists():
        wb = load_workbook(path)
        ws = wb[wb.sheetnames[0]]
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(headers)

    if invoice_type == "purchase":
        ws.append([
            data.get("party_name", ""), data.get("invoice_no", ""), data.get("invoice_date", ""),
            data.get("place_of_supply", ""), "", data.get("rate", ""),
            data.get("taxable_amount", ""), data.get("igst", ""), data.get("cgst", ""),
            data.get("sgst", ""), data.get("total", ""),
        ])
    else:
        items = data.get("items") or []
        if not items:
            ws.append([
                data.get("gstin", ""), data.get("party_name", ""), data.get("invoice_no", ""),
                data.get("invoice_date", ""), data.get("invoice_value", data.get("total", "")),
                data.get("place_of_supply", ""), data.get("rate", ""), "", "",
                data.get("taxable_amount", ""), data.get("igst", ""), data.get("cgst", ""),
                data.get("sgst", ""), data.get("total", ""),
            ])
        else:
            for index, item in enumerate(items):
                ws.append([
                    data.get("gstin", "") if index == 0 else None,
                    data.get("party_name", "") if index == 0 else None,
                    data.get("invoice_no", "") if index == 0 else None,
                    data.get("invoice_date", "") if index == 0 else None,
                    data.get("invoice_value", data.get("total", "")) if index == 0 else None,
                    data.get("place_of_supply", "") if index == 0 else None,
                    data.get("rate", "") if index == 0 else None,
                    item.get("hsn", ""), item.get("quantity", ""),
                    item.get("taxable", item.get("amount", "")), item.get("igst", ""),
                    item.get("cgst", ""), item.get("sgst", ""),
                    item.get("total", item.get("amount", "")),
                ])

    wb.save(path)
    return str(path)
