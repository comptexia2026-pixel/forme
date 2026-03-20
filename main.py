#!/usr/bin/env python3
# main.py
#
# CLI entry point for the term sheet extraction pipeline.
#
# Usage:
#   python main.py
#   python main.py --input path/to/pdfs --output path/to/results
#   python main.py --verbose

import argparse
import logging
import sys
import time
from pathlib import Path

import config
from modules.coord_extractor import extract_from_pdf
from modules.lang_detector import detect_language
from modules.field_extractor import FieldExtractor
from modules.excel_exporter import export_excel
from modules.highlighter import highlight_pdf


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt))
    root.addHandler(console)

    # File handler
    log_dir = config.OUTPUT_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_dir / "extraction.log"), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)


def discover_pdfs(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        return []
    return sorted(f for f in input_dir.iterdir() if f.suffix.lower() == ".pdf")


def process_single_pdf(pdf_path: Path) -> dict:
    """Run the full extraction pipeline on one PDF."""
    logger = logging.getLogger("pipeline")
    logger.info(f"Processing: {pdf_path.name}")

    # Step 1: Coordinate-based extraction
    result = extract_from_pdf(str(pdf_path))

    # Step 2: Language detection
    language = detect_language(result.clean_text)
    logger.info(f"  Language: {language}")

    # Step 3: Field extraction (two-pass: pairs first, then regex)
    extractor = FieldExtractor(
        pairs=result.pairs,
        clean_text=result.clean_text,
        language=language,
    )
    values = extractor.extract_all()

    # Log what we found
    logger.info(
        f"  ISIN={values.get('PST_ISIN')} | BIL={values.get('BIL')} | "
        f"ISSUER={values.get('ISSUER')} | CCY={values.get('CURRENCY')} | "
        f"MAT={values.get('MATURITY')} | W/A={values.get('WORST_OR_AVERAGE')}"
    )

    return {
        "source_file": pdf_path.name,
        "language": language,
        "values": values,
        "clean_text": result.clean_text,
        "coord_result": result,
    }


def print_summary(records: list):
    sep = "=" * 65
    print(f"\n{sep}")
    print("  EXTRACTION SUMMARY")
    print(sep)
    print(f"  Documents processed: {len(records)}\n")

    fields = [
        "PST_ISIN", "BIL", "ISSUER", "CURRENCY", "MATURITY",
        "CAPITAL_PROTECTION", "WORST_OR_AVERAGE", "COUPON",
    ]
    print("  Fill rate:")
    print("  " + "-" * 45)
    for field in fields:
        filled = sum(
            1 for r in records
            if r.get("values", {}).get(field) is not None
            and r.get("values", {}).get(field) != ""
            and r.get("values", {}).get(field) != "nan"
        )
        rate = (filled / len(records) * 100) if records else 0
        bar = "#" * int(rate / 5) + "." * (20 - int(rate / 5))
        print(f"    {field:<24s} [{bar}] {rate:5.1f}%")
    print(f"\n{sep}")


def main():
    parser = argparse.ArgumentParser(description="Term Sheet PDF Extractor")
    parser.add_argument("--input", "-i", type=str, default=str(config.INPUT_DIR))
    parser.add_argument("--output", "-o", type=str, default=str(config.OUTPUT_DIR))
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-highlight", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("pipeline")

    start = time.time()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Discover PDFs
    pdf_files = discover_pdfs(input_dir)
    if not pdf_files:
        logger.warning(f"No PDFs found in {input_dir}")
        print(f"Put your PDF files in: {input_dir}")
        return

    logger.info(f"Found {len(pdf_files)} PDF(s) in {input_dir}")

    # Process each PDF
    records = []
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"[{i}/{len(pdf_files)}] {pdf_file.name}")
        try:
            record = process_single_pdf(pdf_file)
            records.append(record)
        except Exception as e:
            logger.error(f"Failed on {pdf_file.name}: {e}", exc_info=True)

    if not records:
        logger.error("No records produced.")
        return

    # Highlight PDFs and record the annotated file path
    if not args.no_highlight:
        annotated_dir = output_dir / "annotated"
        for record in records:
            pdf_path = input_dir / record["source_file"]
            if pdf_path.exists():
                annotated_name = f"annotated_{record['source_file']}"
                out_path = annotated_dir / annotated_name
                n = highlight_pdf(str(pdf_path), str(out_path), record["values"])
                logger.info(f"  Highlighted {record['source_file']}: {n} annotations")
                # Store the annotated filename in the record for Excel export
                record["annotated_pdf"] = annotated_name if n > 0 else ""
            else:
                record["annotated_pdf"] = ""
    else:
        for record in records:
            record["annotated_pdf"] = ""

    # Export Excel (after highlighting so we have the annotated paths)
    excel_path = output_dir / "extraction_results.xlsx"
    export_excel(records, str(excel_path))

    # Summary
    print_summary(records)
    elapsed = time.time() - start
    logger.info(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
