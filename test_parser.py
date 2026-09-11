"""Regression tests for the supplied Purchase bill and Sale workbook-like data."""

from invoice_parser import parse_invoice


PURCHASE_OCR = """Tax Invoice
Jain Enterprises
\"NAMAN\", OPP. JAIN TEMPLE
PARWARPURA, ITWARI, NAGPUR - 2
GSTIN: 27ACGPJ5346J1ZE
State: 27-Maharashtra
Bill To:
Shri Saree Collection
NAGPUR
Invoice Details:
No: 3265
Date: 02-09-2026
1 Shawl SUDAMA 2 6214 20 ₹ 150.00 ₹ 3,000.00
2 Shawl Saloni 6214 20 ₹ 160.00 ₹ 3,200.00
Total 40 ₹ 6,200.00
Tax Summary:
6214 5,904.88 2.5 147.62 2.5 147.62 295.24
TOTAL 5,904.88 147.62 147.62 295.24
Sub Total : ₹ 6,200.00
Discount (4.76%) : ₹ 295.12
Tax (5.0%) : ₹ 295.24
Round off : - ₹ 0.12
Total : ₹ 6,200.00"""


purchase = parse_invoice(PURCHASE_OCR, 'purchase')
expected_purchase = {
    'party_name': 'Shri Saree Collection',
    'gstin': '27ACGPJ5346J1ZE',
    'invoice_no': '3265',
    'invoice_date': '02-09-2026',
    'place_of_supply': 'NAGPUR',
    'rate': 5.0,
    'taxable_amount': 5904.88,
    'cgst': 147.62,
    'sgst': 147.62,
    'total': 6200.0,
}

for key, expected in expected_purchase.items():
    assert purchase.get(key) == expected, f'{key}: expected {expected}, got {purchase.get(key)}'


SALE_OCR = """Tax Invoice
Bill To: HUKUMCHAND SHANTIKUMAR BROS
NAGPUR
Invoice Details:
No: 1799
Date: 02.03.2024
HSN CODE Quantity Taxable Value CGST SGST TOTAL
5407 40 5400 135 135 5670"""

sale = parse_invoice(SALE_OCR, 'sale')
assert sale['party_name'] == 'HUKUMCHAND SHANTIKUMAR BROS'
assert sale['invoice_no'] == '1799'
assert sale['invoice_date'] == '02.03.2024'
assert sale['place_of_supply'] == 'NAGPUR'
assert len(sale['items']) == 1
assert sale['items'][0]['hsn'] == '5407'
assert sale['items'][0]['quantity'] == 40.0
assert sale['items'][0]['taxable'] == 5400.0
assert sale['items'][0]['cgst'] == 135.0
assert sale['items'][0]['sgst'] == 135.0
assert sale['items'][0]['total'] == 5670.0

print('PASS: Purchase and Sale parser regression tests')
