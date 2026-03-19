# modules/coord_extractor.py
#
# The main idea: instead of relying on extract_text() which glues words,
# we extract each word with its (x, y) coordinates using a tight tolerance,
# then reconstruct the document structure ourselves.
#
# Pipeline:
#   1. extract_words(x_tolerance=1, y_tolerance=1)   -- avoids gluing
#   2. group words into lines by Y proximity          -- reconstruct lines
#   3. detect columns by X clustering                 -- find label/value layout
#   4. build label-value pairs                        -- structured extraction
#   5. also produce clean full text                   -- for regex fallback

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

import config

logger = logging.getLogger(__name__)


@dataclass
class Word:
    """A single word with its bounding box."""
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    page: int = 0


@dataclass
class Line:
    """A reconstructed line -- a list of words sorted left-to-right."""
    words: list  # list[Word]
    y: float     # average Y of the line
    page: int = 0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x_min(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x_max(self) -> float:
        return max(w.x1 for w in self.words)


@dataclass
class LabelValuePair:
    """A label in the left column matched to its value in the right column."""
    label: str
    value: str
    label_x: float
    value_x: float
    y: float
    page: int = 0


@dataclass
class ExtractionResult:
    """Everything the coordinate extractor produces."""
    words: list           # list[Word] -- all words across all pages
    lines: list           # list[Line] -- all reconstructed lines
    pairs: list           # list[LabelValuePair] -- label-value pairs from tables
    clean_text: str       # full document text, properly spaced
    page_count: int
    tables_pdfplumber: list  # raw pdfplumber tables as fallback


# ---------------------------------------------------------------------------
# Step 1: Extract words from all pages
# ---------------------------------------------------------------------------
def _extract_words(pdf_path: str) -> tuple[list[Word], int, list]:
    """Open the PDF, extract words with tight tolerance, return Word objects."""
    all_words = []
    all_tables = []
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for pi, page in enumerate(pdf.pages):
            # Tight tolerance prevents word gluing
            raw_words = page.extract_words(
                x_tolerance=config.WORD_X_TOLERANCE,
                y_tolerance=config.WORD_Y_TOLERANCE,
                keep_blank_chars=False,
            )
            for w in raw_words:
                all_words.append(Word(
                    text=w["text"],
                    x0=w["x0"],
                    top=w["top"],
                    x1=w["x1"],
                    bottom=w["bottom"],
                    page=pi,
                ))

            # Also grab pdfplumber tables as fallback
            try:
                tables = page.extract_tables()
                for t in tables:
                    if t:
                        all_tables.append({"page": pi, "rows": t})
            except Exception:
                pass

    logger.info(f"Extracted {len(all_words)} words from {page_count} pages")
    return all_words, page_count, all_tables


# ---------------------------------------------------------------------------
# Step 2: Reconstruct lines by grouping words with similar Y
# ---------------------------------------------------------------------------
def _group_into_lines(words: list[Word]) -> list[Line]:
    """
    Group words into lines. Two words are on the same line if their
    'top' values are within LINE_Y_THRESHOLD of each other.
    Sort words left-to-right within each line.
    """
    if not words:
        return []

    # Sort by page, then by Y (top), then by X (x0)
    sorted_words = sorted(words, key=lambda w: (w.page, w.top, w.x0))

    lines = []
    current_line_words = [sorted_words[0]]
    current_y = sorted_words[0].top
    current_page = sorted_words[0].page

    for w in sorted_words[1:]:
        # Same line if close in Y and same page
        if w.page == current_page and abs(w.top - current_y) <= config.LINE_Y_THRESHOLD:
            current_line_words.append(w)
        else:
            # Finish current line
            current_line_words.sort(key=lambda x: x.x0)
            avg_y = sum(cw.top for cw in current_line_words) / len(current_line_words)
            lines.append(Line(
                words=current_line_words,
                y=avg_y,
                page=current_page,
            ))
            current_line_words = [w]
            current_y = w.top
            current_page = w.page

    # Don't forget the last line
    if current_line_words:
        current_line_words.sort(key=lambda x: x.x0)
        avg_y = sum(cw.top for cw in current_line_words) / len(current_line_words)
        lines.append(Line(
            words=current_line_words,
            y=avg_y,
            page=current_page,
        ))

    logger.info(f"Reconstructed {len(lines)} lines")
    return lines


# ---------------------------------------------------------------------------
# Step 3: Detect column boundaries
# ---------------------------------------------------------------------------
def _detect_columns(lines: list[Line], page: int = 0) -> list[float]:
    """
    Find column boundaries by looking at the X positions where words start.
    We look for a clear gap in X positions -- that gap separates label from value.

    Returns a sorted list of column-start X positions.
    For BIL term sheets, this typically finds [~36, ~142].
    """
    # Collect all word x0 positions on the target page
    x_starts = []
    for line in lines:
        if line.page != page:
            continue
        for w in line.words:
            x_starts.append(round(w.x0, 0))

    if not x_starts:
        return []

    # Build a histogram of x0 positions (binned to nearest 5pt)
    from collections import Counter
    bin_size = 5
    binned = Counter(int(x / bin_size) * bin_size for x in x_starts)

    # Find the most common x0 positions -- these are column starts
    # Sort bins by frequency (descending)
    common_bins = sorted(binned.items(), key=lambda x: -x[1])

    # Take the top bins and cluster them
    column_starts = []
    for bx, count in common_bins:
        if count < 3:
            break
        # Only add if far enough from existing columns
        if all(abs(bx - c) > config.COLUMN_GAP_MIN for c in column_starts):
            column_starts.append(bx)

    column_starts.sort()
    logger.debug(f"Page {page} column starts: {column_starts}")
    return column_starts


# ---------------------------------------------------------------------------
# Step 4: Build label-value pairs from two-column regions
# ---------------------------------------------------------------------------
def _build_label_value_pairs(lines: list[Line]) -> list[LabelValuePair]:
    """
    For pages that have a two-column layout (label on left, value on right),
    match labels to their values.

    Strategy: for each line, split words into left-group and right-group
    based on a detected column boundary. The left text is the label,
    the right text is the value.
    """
    pairs = []
    pages = set(l.page for l in lines)

    for page in pages:
        page_lines = [l for l in lines if l.page == page]
        columns = _detect_columns(lines, page)

        if len(columns) < 2:
            # No clear two-column layout on this page, skip
            continue

        # Use the boundary between column 1 and column 2
        # Midpoint between the two main column starts
        col_boundary = (columns[0] + columns[1]) / 2

        for line in page_lines:
            left_words = [w for w in line.words if w.x0 < col_boundary]
            right_words = [w for w in line.words if w.x0 >= col_boundary]

            if not left_words or not right_words:
                continue

            label = " ".join(w.text for w in sorted(left_words, key=lambda w: w.x0))
            value = " ".join(w.text for w in sorted(right_words, key=lambda w: w.x0))

            # Skip very long labels (these are paragraphs, not label-value pairs)
            if len(label) > 60:
                continue

            pairs.append(LabelValuePair(
                label=label.strip(),
                value=value.strip(),
                label_x=left_words[0].x0,
                value_x=right_words[0].x0,
                y=line.y,
                page=line.page,
            ))

    logger.info(f"Built {len(pairs)} label-value pairs")
    return pairs


# ---------------------------------------------------------------------------
# Step 5: Produce clean full text
# ---------------------------------------------------------------------------
def _build_clean_text(lines: list[Line]) -> str:
    """
    Join all reconstructed lines into a clean, properly-spaced document.
    This text is used for regex fallback extraction.
    """
    parts = []
    prev_page = -1
    for line in lines:
        if line.page != prev_page:
            if prev_page >= 0:
                parts.append("\n\n--- PAGE BREAK ---\n\n")
            prev_page = line.page
        parts.append(line.text)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_from_pdf(pdf_path: str) -> ExtractionResult:
    """
    Full coordinate-based extraction pipeline.
    Returns an ExtractionResult with words, lines, label-value pairs,
    clean text, and raw pdfplumber tables.
    """
    logger.info(f"Starting coordinate extraction: {pdf_path}")

    words, page_count, raw_tables = _extract_words(pdf_path)
    lines = _group_into_lines(words)
    pairs = _build_label_value_pairs(lines)
    clean_text = _build_clean_text(lines)

    logger.info(
        f"Extraction done: {len(words)} words, {len(lines)} lines, "
        f"{len(pairs)} pairs, {len(clean_text)} chars text"
    )

    return ExtractionResult(
        words=words,
        lines=lines,
        pairs=pairs,
        clean_text=clean_text,
        page_count=page_count,
        tables_pdfplumber=raw_tables,
    )
