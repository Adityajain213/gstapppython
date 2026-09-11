"""Invoice parsing for Purchase and Sale invoices.

The parser is deliberately section-aware.  It avoids selecting arbitrary numbers
from an invoice because invoice pages contain many unrelated numbers such as
quantities, item prices, HSN codes, discounts, GST rates and totals.
"""

import re
from typing import Optional

NUMBER = r"-?[\d,]+(?:\.\d+)?"


def _money(value) -> Optional[float]:
    """Convert OCR text such as '₹ 5,904.88' into a float."""
    if value is None:
        return None
    value = str(value).replace("₹", "").replace(",", "").strip()
    value = re.sub(r"-\s+", "-", value)
    try:
        return float(value)
    except ValueError:
        return None


def _clean_lines(text: str):
    """Normalize OCR while keeping one logical line per entry."""
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _search(patterns, text, flags=re.I):
    """Return the first captured group from a list of patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return ""


def _find_party(lines):
    """Find the customer/recipient name from the Bill To section.

    Handles both layouts used by invoice OCR:
      1. ``Bill To:`` on one line followed by the party name.
      2. ``Bill To: PARTY NAME`` on the same line.
    """
    for index, line in enumerate(lines):
        bill_match = re.match(r"^bill\s*to\s*[:\-]?\s*(.*)$", line, re.I)
        if not bill_match:
            continue

        # First handle the same-line party name.
        same_line = bill_match.group(1).strip()
        same_line = re.split(r"\s+No\s*[:#]", same_line, maxsplit=1, flags=re.I)[0].strip()
        if same_line and not re.match(r"^(invoice|invoice details|date)$", same_line, re.I):
            return same_line

        # Otherwise inspect the lines immediately below Bill To.
        for candidate in lines[index + 1:index + 6]:
            candidate = re.split(r"\s+No\s*[:#]", candidate, maxsplit=1, flags=re.I)[0].strip()
            if not candidate or re.match(r"^(invoice|invoice details|no\b|date\b)$", candidate, re.I):
                continue
            if re.search(r"^(nagpur|mumbai|delhi|kolkata|raipur|pune)$", candidate, re.I):
                continue
            return candidate

    return ""


def _find_place(lines, party):
    """Return only the city/location used as Place of Supply."""
    text = "\n".join(lines)
    match = re.search(r"Place\s+of\s+Supply\s*[:\-]?\s*([^\n]+)", text, re.I)
    if match:
        value = re.split(r"\s+(?:Date|Invoice|No)\s*[:#]?", match.group(1), maxsplit=1, flags=re.I)[0]
        return value.strip(" :-")

    # In the supplied purchase invoice the city is directly below the party.
    for index, line in enumerate(lines):
        if party and re.search(re.escape(party), line, re.I):
            remainder = re.sub(re.escape(party), "", line, count=1, flags=re.I).strip()
            remainder = re.split(r"No\s*[:#]", remainder, maxsplit=1, flags=re.I)[0].strip(" :")
            if remainder and not re.search(r"^(bill\s*to|invoice|date|details)$", remainder, re.I):
                return remainder
            for candidate in lines[index + 1:index + 4]:
                candidate = re.split(r"\s+(?:Date|No)\s*[:#]?", candidate, maxsplit=1, flags=re.I)[0].strip()
                if candidate and not re.match(r"^(No|Date|Invoice|Invoice Details)\b", candidate, re.I):
                    return candidate
    return ""


def _find_invoice_number(lines):
    text = "\n".join(lines)
    return _search(
        [
            r"\bNo\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]*)",
            r"Invoice\s*(?:No|Number)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]*)",
        ],
        text,
    )


def _find_invoice_date(lines):
    text = "\n".join(lines)
    return _search(
        [
            r"\bDate\s*[:#]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})",
            r"Invoice\s+Date\s*[:#]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})",
        ],
        text,
    )


def _find_gstin(lines):
    text = "\n".join(lines).upper()
    match = re.search(r"\bGSTIN(?:\s+OF\s+RECIPIENT)?\s*[:#]?\s*([0-9A-Z]{15})\b", text)
    return match.group(1) if match else ""


def _parse_tax_summary(lines):
    """Parse the Purchase tax-summary row.

    Example sequence from the supplied bill:
        6214 | 5904.88 | 2.5 | 147.62 | 2.5 | 147.62 | 295.24
    """
    result = {"rate": None, "taxable_amount": None, "cgst": None, "sgst": None, "igst": None}
    tax_start = next((i for i, line in enumerate(lines) if re.search(r"tax\s+summary", line, re.I)), 0)
    number_pattern = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

    for line in lines[tax_start:]:
        numbers = number_pattern.findall(line.replace("₹", ""))
        if len(numbers) < 7:
            continue
        for i in range(len(numbers) - 6):
            hsn = numbers[i].replace(",", "")
            if not re.fullmatch(r"\d{4,8}", hsn):
                continue
            values = [_money(v) for v in numbers[i + 1:i + 7]]
            if any(v is None for v in values):
                continue
            taxable, cgst_rate, cgst_amount, sgst_rate, sgst_amount, _ = values
            if taxable > 0 and 0 <= cgst_rate <= 100 and 0 <= sgst_rate <= 100:
                result.update(
                    taxable_amount=taxable,
                    cgst=cgst_amount,
                    sgst=sgst_amount,
                    rate=cgst_rate + sgst_rate,
                )
                return result
    return result


def _find_final_total(lines):
    """Find the final invoice total from the explicit Total label."""
    for line in reversed(lines):
        match = re.search(rf"^Total\s*[:\-]?\s*₹?\s*({NUMBER})\s*$", line, re.I)
        if match:
            return _money(match.group(1))
    return _money(_search([rf"Grand\s+Total\s*[:\-]?\s*₹?\s*({NUMBER})"], "\n".join(lines)))


def _parse_purchase_items(lines):
    """Parse Purchase item rows when the OCR preserves the item table."""
    items = []
    pattern = re.compile(
        rf"^(?:\d+\s+)?(.+?)\s+(\d{{4,8}})\s+(\d+(?:\.\d+)?)\s+₹?({NUMBER})\s+₹?({NUMBER})$"
    )
    for line in lines:
        match = pattern.match(line.replace("₹", ""))
        if match:
            items.append({
                "description": match.group(1).strip(),
                "hsn": match.group(2),
                "quantity": _money(match.group(3)),
                "rate": _money(match.group(4)),
                "amount": _money(match.group(5)),
            })
    return items


def _parse_sale_items(lines):
    """Parse Sale item rows into the exact fields used by the Sale workbook.

    The supplied Sale workbook is line-item based.  Each item row contains:
    HSN, quantity, taxable value and one or more GST amounts.  Invoice-level
    fields are repeated only on the first row of each invoice when saved.
    """
    items = []
    start = 0

    # Start looking after an item/table heading when present.
    for i, line in enumerate(lines):
        if re.search(r"HSN|ITEM|DESCRIPTION|QTY|QUANTITY", line, re.I):
            start = i
            break

    number_pattern = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
    for line in lines[start:]:
        if re.search(r"tax\s+summary|sub\s+total|grand\s+total|terms|bank details", line, re.I):
            continue

        # Handle the numeric Sale workbook-style row first:
        # HSN | QUANTITY | TAXABLE VALUE | CGST | SGST | TOTAL
        # Example: 5407 | 40 | 5400 | 135 | 135 | 5670
        nums = number_pattern.findall(line.replace("₹", ""))
        numeric_sale_row_added = False
        if len(nums) >= 6:
            for idx in range(len(nums) - 5):
                hsn = nums[idx].replace(",", "")
                if not re.fullmatch(r"\d{4,8}", hsn):
                    continue
                values = [_money(v) for v in nums[idx + 1:idx + 6]]
                if any(v is None for v in values):
                    continue
                quantity, taxable, cgst, sgst, total = values
                if quantity >= 0 and taxable >= 0 and cgst >= 0 and sgst >= 0:
                    items.append({
                        "description": "", "hsn": hsn, "quantity": quantity,
                        "rate": None, "amount": taxable, "taxable": taxable,
                        "igst": None, "cgst": cgst, "sgst": sgst, "total": total,
                    })
                    numeric_sale_row_added = True
                    break
        if numeric_sale_row_added:
            continue

        # Common OCR line shape:
        # item description | HSN | quantity | price/rate | amount
        item_match = re.match(
            rf"^(?:\d+\s+)?(.+?)\s+(\d{{4,8}})\s+(\d+(?:\.\d+)?)\s+₹?({NUMBER})\s+₹?({NUMBER})$",
            line.replace("₹", ""),
        )
        if item_match:
            items.append({
                "description": item_match.group(1).strip(),
                "hsn": item_match.group(2),
                "quantity": _money(item_match.group(3)),
                "rate": _money(item_match.group(4)),
                "amount": _money(item_match.group(5)),
                "taxable": None,
                "igst": None,
                "cgst": None,
                "sgst": None,
                "total": _money(item_match.group(5)),
            })
            continue

        # Inter-state Sale rows can use HSN | QUANTITY | TAXABLE | IGST | TOTAL.
        if len(nums) >= 5:
            for idx in range(len(nums) - 4):
                hsn = nums[idx].replace(",", "")
                if not re.fullmatch(r"\d{4,8}", hsn):
                    continue
                values = [_money(v) for v in nums[idx + 1:idx + 5]]
                if any(v is None for v in values):
                    continue
                quantity, taxable, igst, total = values
                if quantity >= 0 and taxable >= 0 and igst >= 0:
                    items.append({
                        "description": "",
                        "hsn": hsn,
                        "quantity": quantity,
                        "rate": None,
                        "amount": taxable,
                        "taxable": taxable,
                        "igst": igst,
                        "cgst": None,
                        "sgst": None,
                        "total": total,
                    })
                    break
    return items


def _parse_sale_tax_from_items(items):
    """Return combined GST rate from extracted item tax amounts when possible."""
    for item in items:
        taxable = item.get("taxable")
        cgst = item.get("cgst")
        sgst = item.get("sgst")
        igst = item.get("igst")
        if taxable and taxable > 0:
            if cgst is not None and sgst is not None:
                return (cgst + sgst) / taxable * 100
            if igst is not None:
                return igst / taxable * 100
    return None


def parse_invoice(text: str, invoice_type: str):
    """Convert OCR text into a structured Purchase or Sale invoice record."""
    lines = _clean_lines(text)
    party = _find_party(lines)
    place = _find_place(lines, party)
    gstin = _find_gstin(lines)

    if invoice_type == "sale":
        items = _parse_sale_items(lines)
        total = _find_final_total(lines)

        # Sale invoices commonly contain line totals rather than a separate
        # invoice total.  Use the sum of line totals if no explicit final total exists.
        if total is None and items:
            total = sum(item.get("total") or 0 for item in items)

        taxable = sum(item.get("taxable") or 0 for item in items) if items else None
        cgst = sum(item.get("cgst") or 0 for item in items) if items else None
        sgst = sum(item.get("sgst") or 0 for item in items) if items else None
        igst = sum(item.get("igst") or 0 for item in items) if items else None
        rate = _parse_sale_tax_from_items(items)

        # Explicit GST rate is preferable when the invoice prints it.
        explicit_rate = _search(
            [rf"(?:GST|Tax)\s*(?:Rate)?\s*[:\-]?\s*({NUMBER})\s*%", rf"({NUMBER})\s*%\s*GST"],
            "\n".join(lines),
        )
        if explicit_rate:
            rate = _money(explicit_rate)

        invoice_fields = [
            "party_name", "gstin", "invoice_no", "invoice_date", "place_of_supply", "rate"
        ]
        return {
            "party_name": party,
            "gstin": gstin,
            "invoice_no": _find_invoice_number(lines),
            "invoice_date": _find_invoice_date(lines),
            "place_of_supply": place,
            "rate": rate,
            "taxable_amount": taxable,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst,
            "total": total,
            "invoice_fields": invoice_fields,
            "items": items,
            "items_text": "",
        }

    # Purchase flow remains based on the explicit tax summary.
    tax = _parse_tax_summary(lines)
    return {
        "party_name": party,
        "gstin": gstin,
        "invoice_no": _find_invoice_number(lines),
        "invoice_date": _find_invoice_date(lines),
        "place_of_supply": place,
        "rate": tax["rate"],
        "taxable_amount": tax["taxable_amount"],
        "igst": tax["igst"],
        "cgst": tax["cgst"],
        "sgst": tax["sgst"],
        "total": _find_final_total(lines),
        "invoice_fields": [
            "party_name", "gstin", "invoice_no", "invoice_date", "place_of_supply",
            "rate", "taxable_amount", "igst", "cgst", "sgst", "total"
        ],
        "items": _parse_purchase_items(lines),
        "items_text": "",
    }
