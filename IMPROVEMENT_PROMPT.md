# Improvement Prompt for Term Sheet Extraction Pipeline
# Use this prompt with another AI to continue improving the project.

---

You are working on a PDF extraction pipeline for structured product term sheets
(financial derivatives). The system extracts fields like ISIN, Issuer, Currency,
Maturity, Coupon, Worst-of/Average, and Capital Protection from semi-structured
PDF documents in English, French, and German.

## Current Architecture

The pipeline uses a coordinate-based approach:
1. pdfplumber extracts each word with its (x, y) bounding box using
   x_tolerance=1 and y_tolerance=1 (to prevent word gluing).
2. Words are grouped into lines by Y-proximity (threshold: 3pt).
3. Columns are detected by histogramming word x0 positions.
4. Label-value pairs are built by splitting lines at the column boundary.
5. A two-pass field extractor uses the pairs first, regex fallback second.

## Key Files

- `config.py` -- all constants, label maps, regex patterns
- `modules/coord_extractor.py` -- word extraction, line/column reconstruction
- `modules/field_extractor.py` -- two-pass extraction (pairs + regex)
- `modules/excel_exporter.py` -- Excel output
- `modules/highlighter.py` -- PDF annotation
- `modules/lang_detector.py` -- keyword-based language detection
- `main.py` -- CLI entry point
- `app.py` -- Streamlit web interface

## What Works Well

- 100% accuracy on BIL term sheets (EN, FR, DE) for: ISIN, Issuer, Currency,
  Maturity, Coupon, Worst-of, SSPA type
- Word gluing is solved by tight extraction tolerance
- Two-column label-value detection is robust for BIL documents

## What Needs Improvement

### 1. Multi-line values
When a value spans two physical lines (e.g., a long issuer name with address),
only the first line is captured. Implement line continuation: if line N+1 has
no label (left column is empty), append it to line N's value.

### 2. Three-column layouts
Some issuers (Credit Suisse, UBS) use three columns: label | sub-label | value.
The current binary column split fails on these. Detect more than 2 column
clusters and handle them.

### 3. Underlying asset extraction
BIL term sheets have a table of underlying assets (stocks/indices) with columns
for name, exchange, ticker, initial fixing level, barrier level. This table
is not yet parsed. Extract underlyings as structured records.

### 4. Section detection
Currently the system processes all pages uniformly. Implementing section
detection (PRODUCT DETAILS, DATES, REDEMPTION, GENERAL INFORMATION) would
allow section-specific extraction strategies.

### 5. Non-BIL issuers
The pipeline has been tested only on BIL documents. Test and adapt for:
- Leonteq (engine-api termsheets)
- BNP Paribas (bnpparibasmarkets.ch)
- Credit Suisse / Eavest
- Goldman Sachs / IDAD
- UBS, Julius Baer, Vontobel

### 6. Date normalisation
Dates are currently returned as found (30.10.2029, 07/09/2027, etc.).
Normalise all dates to ISO 8601 (YYYY-MM-DD) for consistency.

### 7. Validation layer
Add a validation step that cross-checks extracted values:
- ISIN checksum verification (Luhn algorithm on ISIN)
- Currency must be a valid ISO 4217 code
- Maturity date must be in the future (relative to issue date)
- Coupon must be a plausible percentage (0-50%)

### 8. Confidence scores
For each extracted field, return a confidence score (high/medium/low) based
on whether it came from a label-value pair (high) or regex fallback (medium)
or heuristic (low).

### 9. Batch processing robustness
Handle edge cases: password-protected PDFs, scanned-image PDFs (add OCR
fallback), corrupt files, zero-page PDFs.

## Test Data

Three BIL term sheets are provided:
- termsheet-ch1284250102-fr.pdf (FR, 9 pages, Barrier Reverse Convertible)
- termsheet-ch1481964646-de.pdf (DE, 6 pages, Express Certificate)
- termsheet-ch1481964653-en.pdf (EN, 5 pages, Express Certificate)

When you make changes, test on all three and verify that the extraction
accuracy does not regress.

---
