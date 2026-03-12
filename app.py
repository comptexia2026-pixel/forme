# =============================================================================
# app.py
# Interface Streamlit pour l'extraction de term sheets.
#
# Fonctionnement :
#   1. L'utilisateur charge un ou plusieurs PDF
#   2. Le pipeline d'extraction tourne automatiquement
#   3. Les resultats s'affichent dans un tableau
#   4. L'utilisateur telecharge le fichier Excel
#
# Usage :
#   streamlit run app.py
# =============================================================================

import streamlit as st
import tempfile
import shutil
import logging
from pathlib import Path
from datetime import datetime
from io import BytesIO

# Import des modules du projet
import config
from modules.pdf_extractor import PDFExtractor
from modules.field_extractor import FieldExtractor
from modules.data_exporter import DataExporter
from modules.validator import DataValidator

# =============================================================================
# CONFIGURATION DE LA PAGE
# =============================================================================

st.set_page_config(
    page_title="BIL - Term Sheet Extractor",
    page_icon="",
    layout="wide",
)

# --- Theme BIL violet ---
st.markdown("""
<style>
    :root {
        --bil-purple-dark: #2D1B4E;
        --bil-purple: #4A2D7A;
        --bil-purple-light: #6B42B0;
        --bil-accent: #E8B84B;
        --bil-white: #F8F6FC;
        --bil-gray: #E2DDE9;
    }

    .stApp {
        background: linear-gradient(135deg, #2D1B4E 0%, #1A0F30 50%, #2D1B4E 100%);
    }

    /* En-tete BIL */
    .bil-header {
        background: linear-gradient(90deg, #4A2D7A, #6B42B0);
        padding: 30px 40px;
        border-radius: 0 0 20px 20px;
        margin: -1rem -1rem 2rem -1rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(74, 45, 122, 0.4);
        border-bottom: 3px solid #E8B84B;
    }

    .bil-header h1 {
        color: #FFFFFF;
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: 12px;
        margin: 0;
        text-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }

    .bil-header p {
        color: #E8B84B;
        font-size: 1.1rem;
        margin-top: 8px;
        letter-spacing: 3px;
        font-weight: 300;
    }

    /* Cartes */
    .card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 12px;
        padding: 24px;
        margin: 12px 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        border-left: 4px solid #6B42B0;
    }

    .card-title {
        color: #4A2D7A;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 12px;
        letter-spacing: 1px;
    }

    /* Statistiques */
    .stat-row {
        display: flex;
        gap: 20px;
        margin: 20px 0;
    }

    .stat-box {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(232, 184, 75, 0.3);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        flex: 1;
    }

    .stat-box .number {
        color: #E8B84B;
        font-size: 2.2rem;
        font-weight: 800;
    }

    .stat-box .label {
        color: #E2DDE9;
        font-size: 0.85rem;
        letter-spacing: 1px;
        margin-top: 4px;
    }

    /* Boutons */
    .stButton > button {
        background: linear-gradient(135deg, #6B42B0, #4A2D7A);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 24px;
        font-weight: 600;
        letter-spacing: 1px;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #8B6CC5, #6B42B0);
        box-shadow: 0 4px 15px rgba(107, 66, 176, 0.4);
        transform: translateY(-1px);
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #E8B84B, #D4A843);
        color: #2D1B4E;
        border: none;
        border-radius: 8px;
        padding: 12px 32px;
        font-weight: 700;
        font-size: 1.1rem;
        letter-spacing: 1px;
        transition: all 0.3s ease;
        width: 100%;
    }

    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #F0C85C, #E8B84B);
        box-shadow: 0 4px 15px rgba(232, 184, 75, 0.4);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2D1B4E, #1A0F30);
        border-right: 2px solid #6B42B0;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #E8B84B !important;
    }

    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li {
        color: #E2DDE9 !important;
    }

    /* Texte general */
    .main .stMarkdown h1, .main .stMarkdown h2, .main .stMarkdown h3 {
        color: #E8B84B;
    }

    .main .stMarkdown p, .main .stMarkdown li {
        color: #E2DDE9;
    }

    /* Tableau */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* Upload */
    .stFileUploader {
        border-radius: 10px;
    }

    /* Barre de confiance */
    .conf-high { color: #4CAF50; font-weight: 700; }
    .conf-mid { color: #FF9800; font-weight: 700; }
    .conf-low { color: #F44336; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# EN-TETE
# =============================================================================

st.markdown("""
<div class="bil-header">
    <h1>BIL</h1>
    <p>TERM SHEET EXTRACTOR</p>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# FONCTIONS
# =============================================================================

def process_uploaded_pdf(uploaded_file) -> dict:
    """
    Traite un fichier PDF uploade : extraction du texte puis des champs.

    Le fichier est d'abord sauvegarde dans un repertoire temporaire
    car PDFExtractor a besoin d'un chemin sur disque.

    Args:
        uploaded_file: objet UploadedFile de Streamlit.

    Returns:
        Dictionnaire avec source_file, values, confidence.
    """
    # Sauvegarde temporaire du fichier
    temp_dir = Path(tempfile.mkdtemp())
    temp_path = temp_dir / uploaded_file.name

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        # Extraction du texte
        pdf_extractor = PDFExtractor(str(temp_path))
        text = pdf_extractor.extract()

        if not text:
            return {
                "source_file": uploaded_file.name,
                "values": {
                    "PST_ISIN": None, "BIL": None,
                    "CAPITAL_PROTECTION": None, "MATURITY": None,
                    "WORST_OR_AVERAGE": None, "ISSUER": None,
                },
                "confidence": {
                    "PST_ISIN": 0.0, "BIL": 0.0,
                    "CAPITAL_PROTECTION": 0.0, "MATURITY": 0.0,
                    "WORST_OR_AVERAGE": 0.0, "ISSUER": 0.0,
                },
            }

        # Extraction des champs
        field_extractor = FieldExtractor(
            text=text,
            patterns=config.EXTRACTION_PATTERNS,
            bil_keywords=config.BIL_KEYWORDS,
            known_issuers=config.KNOWN_ISSUERS,
        )

        results = field_extractor.extract_all()

        return {
            "source_file": uploaded_file.name,
            "values": results["values"],
            "confidence": results["confidence"],
        }

    finally:
        # Nettoyage du fichier temporaire
        shutil.rmtree(temp_dir, ignore_errors=True)


def generate_excel(records: list) -> bytes:
    """
    Genere un fichier Excel en memoire et retourne les bytes.

    On utilise DataExporter pour creer le fichier dans un dossier
    temporaire, puis on lit les bytes pour le telechargement.

    Args:
        records: liste des enregistrements extraits.

    Returns:
        Contenu du fichier Excel en bytes.
    """
    temp_dir = Path(tempfile.mkdtemp())

    try:
        exporter = DataExporter(
            output_dir=str(temp_dir),
            filename="resultats_extraction",
            csv_separator=config.CSV_SEPARATOR,
            csv_encoding=config.CSV_ENCODING,
        )

        excel_path = exporter.export_excel(records)

        with open(excel_path, "rb") as f:
            return f.read()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def confidence_indicator(score: float) -> str:
    """Retourne un indicateur textuel pour le score de confiance."""
    if score >= 0.7:
        return "OK"
    elif score >= 0.4:
        return "??"
    else:
        return "!!"


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("### Comment utiliser")
    st.markdown("""
    1. Chargez vos PDF ci-dessous
    2. Cliquez sur **Lancer l'extraction**
    3. Consultez les resultats
    4. Telechargez le fichier Excel
    """)

    st.markdown("---")

    st.markdown("### Champs extraits")
    st.markdown("""
    - **PST_ISIN** : code ISIN
    - **BIL** : produit BIL (oui/non)
    - **CAPITAL_PROTECTION** : protection capital (%)
    - **MATURITY** : date de maturite
    - **WORST_OR_AVERAGE** : W ou A
    - **ISSUER** : banque emettrice
    """)

    st.markdown("---")

    st.markdown("### Scores de confiance")
    st.markdown("""
    - **OK** : extraction fiable
    - **??** : a verifier
    - **!!** : non trouve ou douteux
    """)


# =============================================================================
# CONTENU PRINCIPAL
# =============================================================================

# --- Upload des PDF ---
st.markdown("### Chargez vos term sheets")

uploaded_files = st.file_uploader(
    "Glissez vos fichiers PDF ici",
    type=["pdf"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.markdown(f"**{len(uploaded_files)} fichier(s) charge(s)**")

    # --- Bouton de lancement ---
    if st.button("Lancer l'extraction"):

        records = []
        progress = st.progress(0, text="Extraction en cours...")

        for i, uploaded_file in enumerate(uploaded_files):
            progress.progress(
                (i + 1) / len(uploaded_files),
                text=f"Traitement de {uploaded_file.name}..."
            )
            record = process_uploaded_pdf(uploaded_file)
            records.append(record)

        progress.empty()
        st.session_state.records = records

    # --- Affichage des resultats ---
    if "records" in st.session_state and st.session_state.records:
        records = st.session_state.records

        # Statistiques
        n_total = len(records)
        n_isin = sum(1 for r in records if r["values"].get("PST_ISIN"))
        n_issuer = sum(1 for r in records if r["values"].get("ISSUER"))
        n_maturity = sum(1 for r in records if r["values"].get("MATURITY"))

        st.markdown(f"""
        <div class="stat-row">
            <div class="stat-box">
                <div class="number">{n_total}</div>
                <div class="label">PDF TRAITES</div>
            </div>
            <div class="stat-box">
                <div class="number">{n_isin}</div>
                <div class="label">ISIN TROUVES</div>
            </div>
            <div class="stat-box">
                <div class="number">{n_issuer}</div>
                <div class="label">EMETTEURS TROUVES</div>
            </div>
            <div class="stat-box">
                <div class="number">{n_maturity}</div>
                <div class="label">MATURITES TROUVEES</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # --- Tableau des resultats ---
        st.markdown("### Resultats de l'extraction")

        import pandas as pd

        rows = []
        for record in records:
            v = record["values"]
            c = record["confidence"]
            rows.append({
                "Fichier": record["source_file"],
                "ISIN": v.get("PST_ISIN") or "",
                "BIL": "Oui" if v.get("BIL") else "Non",
                "Protection Capital": f"{v['CAPITAL_PROTECTION']}%" if v.get("CAPITAL_PROTECTION") is not None else "",
                "Maturite": v.get("MATURITY") or "",
                "Type Payoff": v.get("WORST_OR_AVERAGE") or "",
                "Emetteur": v.get("ISSUER") or "",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # --- Detail par document ---
        st.markdown("### Detail par document")

        for record in records:
            with st.expander(f"{record['source_file']}"):
                v = record["values"]
                c = record["confidence"]

                fields = [
                    ("PST_ISIN", "Code ISIN"),
                    ("BIL", "Produit BIL"),
                    ("CAPITAL_PROTECTION", "Protection Capital"),
                    ("MATURITY", "Date Maturite"),
                    ("WORST_OR_AVERAGE", "Type Payoff"),
                    ("ISSUER", "Emetteur"),
                ]

                for field_key, field_label in fields:
                    value = v.get(field_key)
                    conf = c.get(field_key, 0.0)
                    indicator = confidence_indicator(conf)

                    if field_key == "BIL":
                        display_val = "Oui" if value else "Non"
                    elif field_key == "CAPITAL_PROTECTION" and value is not None:
                        display_val = f"{value}%"
                    else:
                        display_val = str(value) if value else "(non trouve)"

                    # Couleur selon confiance
                    if conf >= 0.7:
                        css_class = "conf-high"
                    elif conf >= 0.4:
                        css_class = "conf-mid"
                    else:
                        css_class = "conf-low"

                    st.markdown(
                        f'<div class="card" style="padding: 12px; margin: 6px 0;">'
                        f'<strong style="color: #4A2D7A;">{field_label}</strong> : '
                        f'{display_val} '
                        f'<span class="{css_class}">[{indicator}]</span> '
                        f'<span style="color: #999; font-size: 0.8rem;">'
                        f'confiance: {conf:.0%}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        # --- Telechargement Excel ---
        st.markdown("---")
        st.markdown("### Telecharger les resultats")

        excel_bytes = generate_excel(records)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        st.download_button(
            label=f"Telecharger le fichier Excel ({n_total} document(s))",
            data=excel_bytes,
            file_name=f"extraction_termsheets_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.markdown("""
    <div class="card">
        <div class="card-title">Pret a commencer</div>
        <p style="color: #4A2D7A;">
            Chargez vos fichiers PDF de term sheets ci-dessus
            pour lancer l'extraction automatique des champs :
            ISIN, emetteur, protection du capital, maturite,
            type de payoff et detection BIL.
        </p>
    </div>
    """, unsafe_allow_html=True)
