# modules/highlighter.py
#
# Highlights extracted values in the PDF by searching for the text
# at the word level (using pdfplumber coordinates) and adding
# highlight annotations (using pypdf).

import re
import logging
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

logger = logging.getLogger(__name__)

# Colors for each field (RGB 0-1)
FIELD_COLORS = {
    "PST_ISIN":           (1.0, 0.8, 0.0),    # yellow
    "ISSUER":             (0.6, 0.8, 1.0),    # light blue
    "CURRENCY":           (0.6, 1.0, 0.6),    # light green
    "MATURITY":           (1.0, 0.6, 0.6),    # light red
    "CAPITAL_PROTECTION": (0.8, 0.6, 1.0),    # light purple
    "COUPON":             (1.0, 0.9, 0.5),    # gold
    "WORST_OR_AVERAGE":   (1.0, 0.7, 0.4),    # orange
}


def _search_terms(field: str, value) -> list[str]:
    """Generate search strings for a given field and value."""
    if value is None or value == "":
        return []
    v = str(value)
    if field == "PST_ISIN":
        return [v]
    if field == "ISSUER":
        terms = [v]
        # Also try the first word (e.g. "Banque" from "Banque Internationale...")
        parts = v.split()
        if len(parts) > 1 and len(parts[0]) > 3:
            terms.append(parts[0])
        return terms
    if field == "CURRENCY":
        return [v]
    if field == "MATURITY":
        return [v]
    if field == "CAPITAL_PROTECTION":
        return [f"{v}%", f"{v} %", v]
    if field == "COUPON":
        return [v]
    if field == "WORST_OR_AVERAGE":
        if v == "W":
            return ["Worst", "worst-of", "worst of", "Schlechteste"]
        if v == "A":
            return ["Average", "average"]
    return [v]


def highlight_pdf(pdf_path: str, output_path: str, extracted_values: dict) -> int:
    """
    Create an annotated copy of the PDF with highlights on extracted values.
    Returns the number of annotations added.
    """
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        count = 0
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                ph = page.height
                page_words = page.extract_words(x_tolerance=2, y_tolerance=2)
                if not page_words:
                    continue

                for field, value in extracted_values.items():
                    if field in ("CLN", "BIL", "UNDERLYING_ISINS", "DENOMINATION", "SSPA_TYPE"):
                        continue
                    terms = _search_terms(field, value)
                    color = FIELD_COLORS.get(field, (0.5, 0.5, 0.5))

                    found = False
                    for term in terms:
                        if found:
                            break
                        # Single-word match
                        for w in page_words:
                            if term.lower() in w["text"].lower() and len(term) >= 2:
                                x0 = float(w["x0"]) - 1
                                x1 = float(w["x1"]) + 1
                                y0 = ph - float(w["bottom"]) - 1
                                y1 = ph - float(w["top"]) + 1

                                hl = Highlight(
                                    rect=(x0, y0, x1, y1),
                                    quad_points=ArrayObject([
                                        FloatObject(x0), FloatObject(y1),
                                        FloatObject(x1), FloatObject(y1),
                                        FloatObject(x0), FloatObject(y0),
                                        FloatObject(x1), FloatObject(y0),
                                    ]),
                                )
                                hl[NameObject("/C")] = ArrayObject([
                                    FloatObject(color[0]),
                                    FloatObject(color[1]),
                                    FloatObject(color[2]),
                                ])
                                hl[NameObject("/T")] = TextStringObject(field)
                                hl[NameObject("/Contents")] = TextStringObject(f"{field}: {value}")

                                writer.add_annotation(page_number=page_num, annotation=hl)
                                count += 1
                                found = True
                                break

        if count > 0:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                writer.write(f)

        logger.info(f"Highlighted {count} annotations in {output_path}")
        return count

    except Exception as e:
        logger.error(f"Highlight error: {e}")
        return 0
