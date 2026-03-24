# modules/field_extractor.py
#
# Two-pass extraction:
#   Pass 1: Look up label-value pairs (from coordinate extraction)
#   Pass 2: Regex fallback on the clean reconstructed text
#
# Handles EN, FR, DE via config.LABEL_TO_FIELD and multilingual regex.

import re
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)


class FieldExtractor:

    def __init__(self, pairs: list, clean_text: str, language: str):
        """
        pairs      : list of LabelValuePair from coord_extractor
        clean_text : full reconstructed text for regex fallback
        language   : 'EN', 'FR', or 'DE'
        """
        self.pairs = pairs
        self.text = clean_text
        self.lang = language

    def extract_all(self) -> dict:
        """Return a dict with all extracted fields, normalised and cleaned."""
        all_isins = self._find_all_isins()
        pst_isin, underlying_isins = self._classify_isins(all_isins)
        bloomberg_tickers = self._extract_bloomberg_tickers()

        sspa_type = self._extract_sspa_type()

        result = {
            "PST_ISIN": pst_isin,
            "BIL": self._extract_bil(),
            "CLN": self._extract_cln(),
            "CAPITAL_PROTECTION": self._extract_capital_protection(sspa_type),
            "MATURITY": self._extract_maturity(),
            "WORST_OR_AVERAGE": self._extract_worst_or_average(
                len(underlying_isins), len(bloomberg_tickers)
            ),
            "CURRENCY": self._extract_currency(),
            "ISSUER": self._extract_issuer(),
            "COUPON": self._extract_coupon(),
            "SSPA_TYPE": sspa_type,
            "UNDERLYING_ISINS": underlying_isins,
            "BLOOMBERG_TICKERS": bloomberg_tickers,
        }

        # Post-processing: normalise everything
        result = self._normalise(result)
        return result

    # -- Helper: lookup a field from label-value pairs --
    def _lookup_pair(self, field_name: str) -> Optional[str]:
        """Find the first label-value pair that maps to the given field."""
        for pair in self.pairs:
            label_clean = pair.label.strip().rstrip(":")
            # Exact match in the label map
            if label_clean in config.LABEL_TO_FIELD:
                if config.LABEL_TO_FIELD[label_clean] == field_name:
                    return pair.value
            # Partial match: the pair label starts with a known label
            for known_label, mapped_field in config.LABEL_TO_FIELD.items():
                if mapped_field == field_name and known_label.lower() in label_clean.lower():
                    return pair.value
        return None

    # =====================================================================
    # Underlying zone helper -- used by both ISIN classification and tickers
    # =====================================================================
    def _get_underlying_zone(self) -> str:
        """Return the text between UNDERLYING header and PRODUCT DETAILS header."""
        text = self.text
        start = 0
        for marker in ["UNDERLYING", "SOUS-JACENT", "BASISWERT"]:
            pos = text.find(marker)
            if pos != -1:
                start = pos
                break
        end = len(text)
        for marker in ["PRODUCT DETAILS", "DÉTAILS DU PRODUIT", "PRODUKTDETAILS",
                        "GENERAL INFORMATION", "INFORMATIONS", "GENERELLE INFORMATION"]:
            pos = text.find(marker, start + 10)
            if pos != -1:
                end = pos
                break
        return text[start:end]

    # =====================================================================
    # ISIN extraction
    # =====================================================================
    def _find_all_isins(self) -> list[str]:
        """Find all valid ISINs in the text."""
        candidates = re.findall(r"\b([A-Z]{2}[A-Z0-9]{10})\b", self.text)
        seen = set()
        result = []
        for c in candidates:
            if c[:2] in config.VALID_ISIN_PREFIXES and re.search(r"\d", c):
                if c not in seen:
                    seen.add(c)
                    result.append(c)
        return result

    def _classify_isins(self, all_isins: list[str]) -> tuple:
        """
        Separate PST_ISIN (the product's own ISIN) from underlying ISINs.

        Strategy:
          1. Try label-value pairs for PST_ISIN
          2. Find ISINs that appear in the UNDERLYING zone -> those are underlyings
          3. Fall back to proximity scoring
        """
        if not all_isins:
            return None, []

        # Step 1: try from label-value pairs
        pair_isin = self._lookup_pair("PST_ISIN")
        pst = None
        if pair_isin:
            m = re.search(r"[A-Z]{2}[A-Z0-9]{10}", pair_isin)
            if m:
                pst = m.group(0)

        # Step 2: find ISINs inside the UNDERLYING zone
        underlying_zone = self._get_underlying_zone()
        zone_isins = set()
        for isin in all_isins:
            if isin in underlying_zone:
                zone_isins.add(isin)

        # If we have a PST from pairs, everything else is underlying
        if pst:
            zone_isins.discard(pst)  # PST is not an underlying
            # Underlyings = ISINs found in the zone + other ISINs that are not PST
            underlyings = [i for i in all_isins if i != pst and i in zone_isins]
            # Also add ISINs near "Bloomberg"/"Underlying"/"Ticker" keywords
            for i in all_isins:
                if i != pst and i not in underlyings:
                    pos = self.text.find(i)
                    if pos != -1:
                        ctx = self.text[max(0, pos - 200):pos + 200]
                        if any(kw in ctx for kw in ["Bloomberg", "Underlying", "Ticker",
                                                     "Sous-Jacent", "Basiswert"]):
                            underlyings.append(i)
            return pst, underlyings

        # No PST from pairs -- use scoring
        if len(all_isins) == 1:
            return all_isins[0], []

        # Score by proximity to "ISIN" label
        def score(isin):
            pos = self.text.find(isin)
            if pos == -1:
                return 9999
            best = 9999
            for m in re.finditer(r"\bISIN\b", self.text):
                d = abs(pos - m.start())
                if d < best:
                    best = d
            # Penalise if found in the underlying zone
            if isin in zone_isins:
                best += 800
            # Penalise if near "Bloomberg", "Underlying", "Ticker"
            ctx = self.text[max(0, pos - 150):pos + 150]
            if any(kw in ctx for kw in ["Bloomberg", "Underlying", "Ticker"]):
                best += 800
            return best

        scored = sorted(all_isins, key=score)
        pst = scored[0]
        underlyings = [i for i in scored[1:]]
        return pst, underlyings

    # =====================================================================
    # BIL detection
    # =====================================================================
    def _extract_bil(self) -> bool:
        for kw in config.BIL_KEYWORDS:
            if kw.lower() in self.text.lower():
                return True
        # Also check "BIL" as standalone word near "Banque" or "Luxembourg"
        for m in re.finditer(r"\bBIL\b", self.text):
            ctx = self.text[max(0, m.start() - 100):m.end() + 100]
            if "Luxembourg" in ctx or "Banque" in ctx or "Route" in ctx:
                return True
        return False

    # =====================================================================
    # CLN detection
    # =====================================================================
    def _extract_cln(self) -> bool:
        return bool(re.search(r"(?i)\b(credit[\s\-]?linked\s+note|CLN)\b", self.text))

    # =====================================================================
    # Capital Protection -- 3-step logic
    # Step 1: label-value pairs
    # Step 2: regex on full text
    # Step 3: infer from SSPA_TYPE (medium confidence)
    # =====================================================================
    def _extract_capital_protection(self, sspa_type: Optional[str] = None) -> Optional[str]:
        # Step 1: label-value pairs
        raw = self._lookup_pair("CAPITAL_PROTECTION")
        if raw:
            if "none" in raw.lower() or "kein" in raw.lower() or "aucun" in raw.lower():
                return "0"
            m = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", raw)
            if m:
                return m.group(1).replace(",", ".")

        # Step 2: regex on full text (EN/FR/DE)
        patterns = [
            r"(?i)Capital\s+Protection\s*(?:\(at\s+Expiry\))?\s*[:\-]?\s*(None|\d{1,3}(?:[.,]\d+)?)\s*%?",
            r"(?i)Capital\s+Protection\s*(?:\(at\s+Expiry\))?\s*\n+\s*(None|\d{1,3}(?:[.,]\d+)?)\s*%?",
            r"(?i)Protection\s+du\s+Capital\s*[:\-]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%",
            r"(?i)Kapitalschutz\s*[:\-]?\s*(None|Kein|\d{1,3}(?:[.,]\d+)?)\s*%?",
            r"(?i)Minimum\s+Redemption\s*[:\-]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%",
            r"(?i)Capital\s+Guarantee\s*[:\-]?\s*(\d{1,3}(?:[.,]\d+)?)\s*%",
        ]
        for p in patterns:
            m = re.search(p, self.text)
            if m:
                val = m.group(1)
                if val.lower() in ("none", "kein"):
                    return "0"
                try:
                    return str(float(val.replace(",", ".")))
                except ValueError:
                    pass

        # "No Capital Protection" / "not capital protected"
        if re.search(r"(?i)(no\s+capital\s+protection|not\s+capital\s+protected)", self.text):
            return "0"

        # "100% Capital Protected" in title or body
        m = re.search(r"(?i)(\d{1,3})\s*%\s*(?:Capital\s+)?Protected", self.text[:3000])
        if m:
            return m.group(1)

        # Step 3: infer from SSPA product type (medium confidence, never overwrites)
        if sspa_type and sspa_type in config.SSPA_CAPITAL_PROTECTION:
            inferred = config.SSPA_CAPITAL_PROTECTION[sspa_type]
            logger.info(f"  Capital Protection inferred from SSPA {sspa_type}: {inferred}%")
            return str(inferred)

        return None

    # =====================================================================
    # Maturity
    # =====================================================================
    def _extract_maturity(self) -> Optional[str]:
        # Pass 1: label-value pairs
        for field_label in ["MATURITY"]:
            raw = self._lookup_pair(field_label)
            if raw:
                # Parse date from the value
                date = self._parse_date(raw)
                if date:
                    return date

        # Pass 2: regex on text
        date_patterns = [
            r"(?i)(?:Final\s+Fixing\s+Date|Maturity\s+Date|Redemption\s+Date|Verfall|"
            r"Date\s+de\s+Constatation\s+Finale|Date\s+de\s+Remboursement|Rückzahlungstag)"
            r"\s*[:\-]?\s*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{4})",

            r"(?i)(?:Maturity\s+Date|Redemption\s+Date)\s*[:\-]?\s*(\d{1,2}\s+\w+\s+\d{4})",
        ]
        for p in date_patterns:
            m = re.search(p, self.text)
            if m:
                # Run through _parse_date to normalise to ISO
                normalised = self._parse_date(m.group(1).strip())
                return normalised if normalised else m.group(1).strip()

        # Open End
        if re.search(r"(?i)(no\s+fixed\s+(?:Expiration|Redemption)|Open\s+End)", self.text):
            return "Open End"

        return None

    @staticmethod
    def _parse_date(raw: str) -> Optional[str]:
        """Extract a date from raw string and normalise to YYYY-MM-DD."""
        # Strip noise like "(subject to..."
        cleaned = re.sub(r"\(.*", "", raw).strip()

        # Format "07/09/2027" or "30.10.2029" or "30-10-2029"
        m = re.search(r"(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{4})", cleaned)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
            # Maybe it's MM/DD/YYYY (unlikely in European docs but handle it)
            if 1 <= d <= 12 and 1 <= mo <= 31:
                return f"{y:04d}-{d:02d}-{mo:02d}"

        # Format "04 February 2028" / "30 octobre 2029" / "07 September 2027"
        m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", cleaned)
        if m:
            d, month_name, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            mo = config.MONTH_MAP.get(month_name)
            if mo:
                return f"{y:04d}-{mo:02d}-{d:02d}"
            # Month name not recognized -- return as-is rather than lose the data
            return m.group(0)

        return None

    # =====================================================================
    # Worst-of / Average
    # =====================================================================
    def _extract_worst_or_average(self, n_underlying_isins: int = 0, n_tickers: int = 0) -> str:
        # Single underlying = worst-of by definition
        n_underlyings = max(n_underlying_isins, n_tickers)
        if n_underlyings == 1:
            return "W"

        # Otherwise: fall back to regex patterns
        search_zone = self.text[:5000]

        for pattern in config.WORST_OF_KEYWORDS_EN:
            if re.search(pattern, search_zone, re.IGNORECASE):
                return "W"

        for pattern in config.AVERAGE_KEYWORDS:
            if re.search(pattern, search_zone, re.IGNORECASE):
                return "A"

        # Explicitly return "nan" for homogeneous output
        return "nan"

    # =====================================================================
    # Currency
    # =====================================================================
    def _extract_currency(self) -> Optional[str]:
        # Pass 1: label-value pairs
        raw = self._lookup_pair("CURRENCY")
        if raw:
            m = re.search(r"\b([A-Z]{3})\b", raw)
            if m and m.group(1) in config.VALID_CURRENCIES:
                return m.group(1)

        # Pass 2: regex fallback
        patterns = [
            r"(?i)(?:Settlement|Redemption|Specified)\s+Currency\s*:?\s+([A-Z]{3})",
            r"(?i)(?:Settlement|Redemption)\s+Currency\s*\n+\s*([A-Z]{3})\b",
            r"(?i)Devise\s+de\s+Paiement\s*\n?\s*([A-Z]{3})\b",
            r"(?i)Auszahlungswährung\s*\n?\s*([A-Z]{3})\b",
            r"(?i)Denomination\s*:?\s*\n?\s*([A-Z]{3})\b",
        ]
        for p in patterns:
            m = re.search(p, self.text)
            if m and m.group(1) in config.VALID_CURRENCIES:
                return m.group(1)

        return None

    # =====================================================================
    # Issuer
    # =====================================================================
    def _extract_issuer(self) -> Optional[str]:
        # Pass 1: label-value pairs
        raw = self._lookup_pair("ISSUER")
        if raw:
            # Clean up: take until comma or newline, remove parentheses
            cleaned = re.split(r"[,\n]", raw)[0].strip()
            cleaned = re.sub(r'\s*\(.*?\)\s*$', '', cleaned).strip()
            if 3 < len(cleaned) < 100 and cleaned[0].isupper():
                # Check it's not a false positive
                if not any(fp.lower() in cleaned.lower() for fp in config.ISSUER_FALSE_POSITIVES):
                    return cleaned

        # Pass 2: known issuer names in text near "Issuer" / "Emetteur" / "Emittentin"
        issuer_labels = r"(?i)\b(Issuer|Émetteur|Emetteur|Emittentin)\b"
        for known in config.KNOWN_ISSUERS:
            pos = self.text.find(known)
            if pos != -1:
                # Check if near an issuer label
                for m in re.finditer(issuer_labels, self.text):
                    if abs(pos - m.start()) < 400:
                        return known
        return None

    # =====================================================================
    # Coupon
    # =====================================================================
    def _extract_coupon(self) -> Optional[str]:
        # Strategy 1: Look for "X.XX% p.a." in title (first 500 chars)
        title = self.text[:500]
        m = re.search(r"(\d+[.,]\d+)\s*%\s*(?:p\.?\s*a\.?)", title)
        if m:
            return m.group(1).replace(",", ".") + "% p.a."

        # Strategy 2: Look for percentage near "Coupon" keyword in label-value pairs
        for pair in self.pairs:
            combined = pair.label + " " + pair.value
            if re.search(r"(?i)(coupon|couponzahlung)", combined):
                pct = re.search(r"(\d+[.,]\d+)\s*%", combined)
                if pct:
                    return pct.group(1).replace(",", ".") + "%"

        # Strategy 3: Title area percentage (without "p.a.")
        m = re.search(r"(\d+[.,]\d+)\s*%", title)
        if m:
            return m.group(1).replace(",", ".") + "%"

        return None

    # =====================================================================
    # Bloomberg Tickers -- extract from underlying table
    # =====================================================================
    def _extract_bloomberg_tickers(self) -> list[str]:
        """
        Extract Bloomberg tickers from the underlying assets table.
        """
        tickers = []
        zone = self._get_underlying_zone()

        exchange_names = [
            "NASDAQ", "NYSE", "SIX Swiss", "SIX", "OMX Nordic", "OMX",
            "Euronext", "LSE", "XETRA", "TSE", "HKEX",
            "STOXX Limited", "STOXX", "S&P Dow Jones", "Indices LLC",
        ]
        for ex in exchange_names:
            for m in re.finditer(re.escape(ex) + r"[^\n]{0,30}", zone):
                chunk = m.group(0)
                after_ex = chunk[len(ex):].strip()
                after_ex = re.sub(r"^(?:Exchange\s+AG|AG|Limited|LLC)\s*", "", after_ex).strip()
                tm = re.match(r"([A-Z][A-Z0-9]{0,5})\s+([A-Z]{2})\b", after_ex)
                if tm:
                    tickers.append(f"{tm.group(1)} {tm.group(2)}")
                else:
                    tm = re.match(r"([A-Z][A-Z0-9]{1,5})\b", after_ex)
                    if tm and tm.group(1) not in ("USD","EUR","CHF","GBP","JPY","DKK","TBA","FOR","THE"):
                        tickers.append(tm.group(1))

        for line in zone.split("\n"):
            for tm in re.finditer(r"\b([A-Z][A-Z0-9]{1,5})\s+([A-Z]{2})\s+(?:USD|EUR|CHF|GBP|DKK|JPY|NOK|SEK)\s+[\d.,]+", line):
                candidate = f"{tm.group(1)} {tm.group(2)}"
                if candidate not in tickers:
                    tickers.append(candidate)
            for tm in re.finditer(r"\b([A-Z][A-Z0-9]{2,5})\s+(?:USD|EUR|CHF|GBP|DKK|JPY)\s+[\d.,]+", line):
                candidate = tm.group(1)
                if candidate not in tickers and candidate not in ("USD","EUR","CHF","GBP","JPY","DKK","TBA"):
                    tickers.append(candidate)

        # Deduplicate preserving order
        seen = set()
        unique = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

    # =====================================================================
    # Post-processing: normalise all extracted values
    # =====================================================================
    def _normalise(self, result: dict) -> dict:
        """Clean and standardise all extracted values for homogeneous output."""

        # ISSUER: remove trailing noise, standardise whitespace
        issuer = result.get("ISSUER")
        if issuer:
            issuer = re.sub(r"\s+", " ", issuer).strip()
            issuer = issuer.rstrip(" ,;:-")
            issuer = re.sub(r'\s*\(.*?\)\s*$', '', issuer).strip()
            result["ISSUER"] = issuer

        # CURRENCY: force uppercase ISO 4217
        ccy = result.get("CURRENCY")
        if ccy:
            result["CURRENCY"] = ccy.upper().strip()

        # COUPON: trim whitespace
        coupon = result.get("COUPON")
        if coupon:
            result["COUPON"] = coupon.strip()

        # PST_ISIN: trim whitespace
        isin = result.get("PST_ISIN")
        if isin:
            result["PST_ISIN"] = isin.strip()

        # Strip all string values
        for key, val in result.items():
            if isinstance(val, str):
                result[key] = val.strip()

        return result

    # =====================================================================
    # SSPA Product Type
    # =====================================================================
    def _extract_sspa_type(self) -> Optional[str]:
        raw = self._lookup_pair("SSPA_TYPE")
        if raw:
            m = re.search(r"(\d{4})", raw)
            if m:
                return m.group(1)

        # Regex fallback -- search in first 800 chars, allow newlines
        header = self.text[:800]
        m = re.search(r"(?i)SSPA\s+Product\s+Type\s*:?\s*(\d{4})", header)
        if m:
            return m.group(1)
        m = re.search(r"(?i)Produktetyp\s+nach\s+SSPA\s*:?\s*(\d{4})", header)
        if m:
            return m.group(1)
        # FR: "Gamme de Produits ... SSPA:\nTermsheet 1230"
        m = re.search(r"(?i)SSPA\s*:\s*\n?\s*(?:Termsheet\s+)?(\d{4})", header)
        if m:
            return m.group(1)
        # Last resort: any 4-digit number near "SSPA" within 50 chars
        for sm in re.finditer(r"SSPA", header):
            chunk = header[sm.start():sm.start() + 60]
            dm = re.search(r"(\d{4})", chunk)
            if dm:
                return dm.group(1)

        return None
