# config.py
# All constants, regex patterns, and field definitions for the pipeline.
# Centralised here so nothing is scattered across modules.

from pathlib import Path

# -- Directories --
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "data" / "input"
OUTPUT_DIR = BASE_DIR / "data" / "output"

# -- PDF extraction tolerances --
# Using x_tolerance=1 prevents pdfplumber from gluing words together.
# Default (3) produces "SettlementCurrency" instead of "Settlement" + "Currency".
WORD_X_TOLERANCE = 1
WORD_Y_TOLERANCE = 1

# Line reconstruction: words within this Y-distance are on the same line.
# Typical line height in these PDFs is ~7-12pt, so 3pt is tight enough.
LINE_Y_THRESHOLD = 3.0

# Column detection: minimum gap between clusters to split columns.
# The BIL term sheets use a clear gap around x=140 between labels and values.
COLUMN_GAP_MIN = 20.0

# -- BIL detection --
BIL_KEYWORDS = [
    "Banque Internationale à Luxembourg",
    "Banque Internationale a Luxembourg",
    "69 Route d'Esch",
    "69 Route d\u2019Esch",
    "69, Route d'Esch",
    "L-2953 Luxembourg",
]

# -- Language detection (keyword-based, no external dependency) --
LANG_KEYWORDS = {
    "FR": [
        "Émetteur", "Emetteur", "Date de Constatation", "Sous-Jacent",
        "Remboursement", "Devise de Paiement", "Valeur Nominale",
        "Protection du Capital", "Coupon Conditionnel", "Date d'Émission",
        "Offre au Public", "Pour la Suisse", "Risques Significatifs",
    ],
    "DE": [
        "Emittentin", "Basiswert", "Rückzahlung", "Auszahlungswährung",
        "Denomination", "Liberierung", "Verfall", "Kapitalschutz",
        "Privatplatzierung", "Für die Schweiz", "Bedeutende Risiken",
        "Valorennummer", "Renditeoptimierung",
    ],
    "EN": [
        "Issuer", "Underlying", "Settlement Currency", "Redemption Date",
        "Maturity Date", "Capital Protection", "Denomination",
        "For Switzerland", "Significant Risks", "Swiss Security Number",
    ],
}

# -- Valid ISIN prefixes --
VALID_ISIN_PREFIXES = [
    "XS", "CH", "DE", "FR", "US", "GB", "NL", "LU", "IE", "NO",
    "SE", "DK", "AT", "IT", "ES", "FI", "BE", "PT", "AU", "CA",
    "JP", "SG", "HK",
]

# -- Valid currencies --
VALID_CURRENCIES = {
    "USD", "EUR", "CHF", "GBP", "JPY", "CAD", "AUD", "SGD", "HKD",
    "NOK", "SEK", "DKK", "CNY", "CNH", "NZD", "PLN", "CZK",
}

# -- Known issuers (for fallback matching) --
KNOWN_ISSUERS = [
    "Banque Internationale à Luxembourg S.A.",
    "Banque Internationale a Luxembourg S.A.",
    "BNP Paribas Issuance B.V.",
    "BNP Paribas",
    "UBS AG",
    "Credit Suisse International",
    "Credit Suisse AG",
    "Leonteq Securities AG",
    "Goldman Sachs International",
    "Goldman Sachs Finance Corp International",
    "Julius Baer Financial Products",
    "Vontobel Financial Products",
    "Barclays Bank PLC",
    "NATIXIS STRUCTURED ISSUANCE SA",
    "Natixis",
    "Societe Generale",
    "EFG International Finance",
    "Raiffeisen Schweiz",
    "Zurcher Kantonalbank",
    "Morgan Stanley",
    "J.P. Morgan",
    "HSBC",
    "Citigroup",
    "Deutsche Bank",
    "Commerzbank",
]

# -- Issuer false positives --
ISSUER_FALSE_POSITIVES = [
    "FINMA", "ECB", "FCA", "CSSF", "ACPR", "BaFin", "SEC",
    "NASDAQ", "NYSE", "SIX", "SIX SIS", "Euroclear", "Clearstream",
    "S&P", "Moody's", "Fitch", "Standard & Poor's",
    "Swiss Federal", "European Central",
]

# -- Multilingual label maps --
# Maps label text (as found in the PDF) to the canonical field name.
# Covers EN, FR, DE variants.
LABEL_TO_FIELD = {
    # ISIN
    "ISIN":                         "PST_ISIN",
    "ISIN Code":                    "PST_ISIN",
    "Code ISIN":                    "PST_ISIN",
    # Issuer
    "Issuer":                       "ISSUER",
    "Émetteur":                     "ISSUER",
    "Emetteur":                     "ISSUER",
    "Emittentin":                   "ISSUER",
    # Currency
    "Settlement Currency":          "CURRENCY",
    "Specified Currency":           "CURRENCY",
    "Redemption Currency":          "CURRENCY",
    "Devise de Paiement":           "CURRENCY",
    "Auszahlungswährung":           "CURRENCY",
    # Maturity
    "Maturity Date":                "MATURITY",
    "Redemption Date":              "MATURITY",
    "Final Fixing Date":            "MATURITY",
    "Expiration Date":              "MATURITY",
    "Date de Constatation Finale":  "MATURITY",
    "Date de Remboursement":        "MATURITY",
    "Verfall":                      "MATURITY",
    "Rückzahlungstag":              "MATURITY",
    # Capital Protection
    "Capital Protection":           "CAPITAL_PROTECTION",
    "Capital Protection (at Expiry)": "CAPITAL_PROTECTION",
    "Minimum Redemption":           "CAPITAL_PROTECTION",
    "Protection du Capital":        "CAPITAL_PROTECTION",
    "Kapitalschutz":                "CAPITAL_PROTECTION",
    # Coupon
    "Conditional Coupon Amount":    "COUPON",
    "Coupon":                       "COUPON",
    "Bedingte Couponzahlung":       "COUPON",
    # Product type
    "SSPA Product Type":            "SSPA_TYPE",
    # Skip labels (we want to ignore these)
    "Governing Law":                "_SKIP_",
    "Listing":                      "_SKIP_",
    "Valuation Date":               "_SKIP_",
}

# -- SSPA-based capital protection inference --
# Used when no explicit Capital Protection is found in the document.
# Maps SSPA product type code to expected capital protection percentage.
SSPA_CAPITAL_PROTECTION = {
    "1100": 100,   # Capital Protection with Participation
    "1110": 100,   # Capital Protection with Cap
    "1120": 100,   # Capital Protection with Barrier
    "1130": 100,   # Capital Protection with Coupon
    "1140": 100,   # Capital Protection with Twin-Win
    "1199": 100,   # Miscellaneous Capital Protection
    "1200": 0,     # Yield Enhancement (no protection)
    "1210": 0,     # Discount Certificate
    "1220": 0,     # Reverse Convertible
    "1230": 0,     # Barrier Reverse Convertible
    "1240": 0,     # Express Certificate with Barrier
    "1250": 0,     # Yield Enhancement misc
    "1260": 0,     # Express Certificate
    "1300": 0,     # Participation (no protection)
    "1310": 0,     # Tracker Certificate
    "1320": 0,     # Outperformance Certificate
    "1330": 0,     # Bonus Certificate
    "2100": 0,     # Warrant
    "2110": 0,     # Spread Warrant
    "2200": 0,     # Knock-Out Warrant
    "2300": 0,     # Mini-Future
}

# -- Month name to number mapping (for date normalisation, EN/FR/DE) --
MONTH_MAP = {
    # EN
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # FR
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    # DE
    "januar": 1, "februar": 2, "märz": 3, "marz": 3,
    "juni": 6, "juli": 7, "oktober": 10, "dezember": 12,
}

# -- Worst-of / Average detection keywords --
WORST_OF_KEYWORDS_EN = [
    r"\bworst[\s\-]?of\b", r"\bworst\s+performance\b",
    r"\bworst\s+performing\b", r"\blowest\s+performing\b",
    r"\blowest\s+performance\b", r"\blinked\s+to\s+worst\b",
    r"\bla\s+plus\s+mauvaise\s+performance\b",
    r"\bplus\s+mauvaise\s+performance\b",
    r"\bSchlechtest\w*\s+Kursentwicklung\b",
    r"\bMulti\s+Barrier\b",
    r"\bMulti\s+Barriere\b",
]
AVERAGE_KEYWORDS = [
    r"\baveraging\b", r"\bbasket\s+average\b",
    r"\bperformance\s+moyenne\b", r"\bDurchschnitt\b",
]

# -- Excel export styling --
EXCEL_HEADER_COLOR = "4A2D7A"  # BIL purple
EXCEL_HEADER_FONT_COLOR = "FFFFFF"

# -- Streamlit colors --
STREAMLIT_PRIMARY_COLOR = "#4A2D7A"
