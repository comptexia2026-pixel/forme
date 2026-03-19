#!/usr/bin/env python3
# app.py
#
# Streamlit interface for the term sheet extraction pipeline.
# Purple BIL theme, upload PDFs, view results, download Excel.
#
# Usage:
#   streamlit run app.py

import tempfile
import logging
from pathlib import Path
from io import BytesIO

import streamlit as st

from modules.coord_extractor import extract_from_pdf
from modules.lang_detector import detect_language
from modules.field_extractor import FieldExtractor
from modules.excel_exporter import export_excel
from modules.highlighter import highlight_pdf

logging.basicConfig(level=logging.INFO)

# -- Page config --
st.set_page_config(
    page_title="Term Sheet Extractor",
    page_icon="📄",
    layout="wide",
)

# -- Custom CSS: BIL purple theme --
st.markdown("""
<style>
    .stApp {
        background-color: #f5f0fa;
    }
    .main-header {
        background: linear-gradient(135deg, #4A2D7A 0%, #6B3FA0 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 2rem;
    }
    .main-header p {
        color: #d4c4e8;
        margin: 0.5rem 0 0 0;
    }
    .result-card {
        background: white;
        border: 1px solid #e0d4f0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .field-label {
        font-weight: bold;
        color: #4A2D7A;
    }
    .stButton>button {
        background-color: #4A2D7A;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# -- Header --
st.markdown("""
<div class="main-header">
    <h1>Term Sheet Extractor</h1>
    <p>Coordinate-based extraction pipeline for structured product term sheets</p>
    <p style="font-size: 0.85rem; margin-top: 1rem;">Nasser Kassioui</p>
</div>
""", unsafe_allow_html=True)


def process_uploaded_pdf(uploaded_file) -> dict:
    """Process a single uploaded PDF file."""
    # Write to temp file (pdfplumber needs a file path)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Run the pipeline
    result = extract_from_pdf(tmp_path)
    language = detect_language(result.clean_text)
    extractor = FieldExtractor(
        pairs=result.pairs,
        clean_text=result.clean_text,
        language=language,
    )
    values = extractor.extract_all()

    # Generate highlighted PDF
    highlighted_bytes = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as hl_tmp:
            hl_path = hl_tmp.name
        n = highlight_pdf(tmp_path, hl_path, values)
        if n > 0:
            highlighted_bytes = Path(hl_path).read_bytes()
    except Exception:
        pass

    return {
        "source_file": uploaded_file.name,
        "language": language,
        "values": values,
        "clean_text": result.clean_text,
        "pairs_count": len(result.pairs),
        "lines_count": len(result.lines),
        "words_count": len(result.words),
        "page_count": result.page_count,
        "highlighted_pdf": highlighted_bytes,
        "tmp_path": tmp_path,
    }


# -- File upload --
uploaded_files = st.file_uploader(
    "Upload term sheet PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    if st.button("Extract", type="primary"):
        records = []
        progress = st.progress(0)

        for i, uf in enumerate(uploaded_files):
            with st.spinner(f"Processing {uf.name}..."):
                try:
                    record = process_uploaded_pdf(uf)
                    records.append(record)
                except Exception as e:
                    st.error(f"Error on {uf.name}: {e}")
            progress.progress((i + 1) / len(uploaded_files))

        if records:
            st.session_state["records"] = records

# -- Display results --
if "records" in st.session_state and st.session_state["records"]:
    records = st.session_state["records"]

    st.markdown("---")
    st.subheader(f"Results ({len(records)} document(s))")

    # Summary table
    summary_data = []
    for r in records:
        v = r["values"]
        summary_data.append({
            "File": r["source_file"],
            "Lang": r["language"],
            "ISIN": v.get("PST_ISIN", ""),
            "BIL": v.get("BIL", ""),
            "Issuer": v.get("ISSUER", ""),
            "Currency": v.get("CURRENCY", ""),
            "Maturity": v.get("MATURITY", ""),
            "Coupon": v.get("COUPON", ""),
            "W/A": v.get("WORST_OR_AVERAGE", ""),
            "Cap. Prot.": v.get("CAPITAL_PROTECTION", ""),
        })

    st.dataframe(summary_data, use_container_width=True)

    # Detailed view per document
    for r in records:
        with st.expander(f"Details: {r['source_file']}"):
            v = r["values"]
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**ISIN:** {v.get('PST_ISIN', 'N/A')}")
                st.markdown(f"**BIL:** {v.get('BIL', 'N/A')}")
                st.markdown(f"**CLN:** {v.get('CLN', 'N/A')}")
                st.markdown(f"**Language:** {r['language']}")

            with col2:
                st.markdown(f"**Issuer:** {v.get('ISSUER', 'N/A')}")
                st.markdown(f"**Currency:** {v.get('CURRENCY', 'N/A')}")
                st.markdown(f"**Maturity:** {v.get('MATURITY', 'N/A')}")
                st.markdown(f"**Coupon:** {v.get('COUPON', 'N/A')}")

            with col3:
                st.markdown(f"**Worst/Avg:** {v.get('WORST_OR_AVERAGE', 'N/A')}")
                st.markdown(f"**Cap. Protection:** {v.get('CAPITAL_PROTECTION', 'N/A')}")
                st.markdown(f"**SSPA Type:** {v.get('SSPA_TYPE', 'N/A')}")
                st.markdown(f"**Pages:** {r['page_count']}")

            # Underlying ISINs
            underlyings = v.get("UNDERLYING_ISINS", [])
            if underlyings:
                st.markdown(f"**Underlyings:** {', '.join(underlyings)}")

            # Stats
            st.caption(
                f"Extraction stats: {r['words_count']} words, "
                f"{r['lines_count']} lines, {r['pairs_count']} label-value pairs"
            )

            # Download highlighted PDF
            if r.get("highlighted_pdf"):
                st.download_button(
                    label="Download highlighted PDF",
                    data=r["highlighted_pdf"],
                    file_name=f"annotated_{r['source_file']}",
                    mime="application/pdf",
                )

    # Export Excel
    st.markdown("---")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        export_excel(records, tmp.name)
        excel_bytes = Path(tmp.name).read_bytes()

    st.download_button(
        label="Download Excel results",
        data=excel_bytes,
        file_name="extraction_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
