# Technical Note: Table Reconstruction in PDF Term Sheets
# Author: Nasser Kassioui

## The Problem

Structured product term sheets (BIL, Leonteq, BNP, etc.) encode financial data
in semi-structured layouts with tables, label-value pairs, and multi-column
regions. Standard PDF text extraction fails because:

1. **Word gluing**: pdfplumber's default tolerance (x_tolerance=3) merges
   adjacent words when character spacing is tight. Example:
   "SettlementCurrency" instead of "Settlement Currency".

2. **Column destruction**: extract_text() linearises columns into a single
   stream, losing the spatial relationship between labels and values.

3. **Table detection failures**: pdfplumber's extract_tables() relies on
   visible lines/borders. Many term sheets use invisible table grids.


## Our Approach

### Step 1: Tight-tolerance word extraction

We extract words with x_tolerance=1 and y_tolerance=1. This prevents
any word merging. On the EN test PDF, this produces 745 properly
separated words instead of 107 glued blobs with default settings.

### Step 2: Line reconstruction by Y-proximity

Words are grouped into lines when their vertical positions (top coordinate)
are within 3 points of each other. This threshold was determined empirically:
- Typical line height in BIL PDFs: 7-12pt
- Inter-line gap: 4-8pt
- Threshold of 3pt separates lines without merging adjacent ones

### Step 3: Column detection by X-clustering

For each page, we histogram all word x0 (left-edge) positions, binned to
5pt resolution. The two most common x0 bins that are at least 20pt apart
become the column boundaries. In BIL term sheets:
- Column 1 (labels): x0 ~ 36pt
- Column 2 (values): x0 ~ 142pt

### Step 4: Label-value pair construction

For each line, words left of the column boundary form the label; words right
form the value. Lines with labels longer than 60 characters are skipped
(they are paragraph text, not key-value data).

### Step 5: Field extraction (two-pass)

Pass 1: Look up the label-value pairs against a multilingual label map.
Pass 2: Regex fallback on the clean reconstructed text.


## Limits

1. **Multi-line values**: If a value spans two physical lines (e.g., a long
   issuer name), the current approach only captures the first line.

2. **Three-column layouts**: Some issuers use three columns (label, sub-label,
   value). The current binary column split would assign the sub-label to
   the wrong group.

3. **Merged cells**: pdfplumber cannot detect merged cells in invisible-grid
   tables. We rely on spatial heuristics instead.

4. **Non-BIL layouts**: The column boundary detection adapts per page, but
   issuers with radically different layouts (e.g., Credit Suisse with
   horizontal tables) may need issuer-specific adjustments.


## Possible Improvements

1. **Adaptive column detection per vertical region**: Instead of one column
   boundary per page, detect boundaries per section (PRODUCT DETAILS vs
   DATES vs GENERAL INFORMATION).

2. **Multi-line value stitching**: If a label on line N has a value, and
   line N+1 has no label (empty left column), append line N+1's content
   to the previous value.

3. **Machine learning layout classification**: Train a model on annotated
   term sheet pages to classify regions as "header", "table", "paragraph".

4. **OCR fallback**: For scanned or image-heavy PDFs, add Tesseract OCR
   with the coordinate extraction applied to OCR output.
