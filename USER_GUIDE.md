# User Guide
**Term Sheet Extraction Pipeline**
Nasser Kassioui

---

## Installation

```bash
pip install pdfplumber pypdf openpyxl streamlit
```

## Option 1: Command Line

Place your PDF term sheets in `data/input/`, then run:

```bash
python main.py
```

Results appear in `data/output/`:
- `extraction_results.xlsx` -- the Excel file with all extracted data
- `annotated/` -- highlighted copies of each PDF

### Options

```bash
python main.py --input /path/to/pdfs --output /path/to/results
python main.py --verbose          # detailed logging
python main.py --no-highlight     # skip PDF highlighting
```

## Option 2: Streamlit Web Interface

```bash
streamlit run app.py
```

1. Open the browser (usually http://localhost:8501)
2. Upload one or more PDF term sheets
3. Click "Extract"
4. View results in the table
5. Download the Excel file or highlighted PDFs

## What Gets Extracted

| Field | Description | Example |
|---|---|---|
| PST_ISIN | Product ISIN | CH1481964653 |
| BIL | Is it a BIL product? | True / False |
| CLN | Credit Linked Note? | True / False |
| ISSUER | Issuing entity | Banque Internationale a Luxembourg S.A. |
| CURRENCY | Settlement currency | EUR, CHF, USD |
| MATURITY | Final fixing / maturity date | 07/09/2027 |
| COUPON | Coupon rate | 5.60% |
| WORST_OR_AVERAGE | Worst-of (W) or Average (A) | W |
| CAPITAL_PROTECTION | Protection level | 0, 80, 100 (or empty) |
| SSPA_TYPE | SSPA product classification | 1230, 1260 |
| UNDERLYING_ISINS | ISINs of underlying assets | (listed in Sheet 2) |

## Supported Languages

The pipeline handles term sheets in:
- English (EN)
- French (FR)
- German (DE)

Language is detected automatically.

## Troubleshooting

**"No PDFs found"**: Check that your files have a `.pdf` extension and are
in the correct input directory.

**Missing field values**: Some products genuinely do not specify certain fields
(e.g., Barrier Reverse Convertibles have no Capital Protection). An empty cell
means the field was not present in the document.

**Incorrect values**: Run with `--verbose` to see the extraction log.
Check `data/output/extraction.log` for details.

---
Nasser Kassioui
