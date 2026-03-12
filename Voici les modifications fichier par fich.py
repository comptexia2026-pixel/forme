# =============================================================================
# modules/pdf_highlighter.py
# Surligne les champs trouves directement dans le PDF.
# Approche simple : cherche le texte exact dans chaque page.
# =============================================================================

import logging
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject

logger = logging.getLogger(__name__)

# Couleurs par champ (R, G, B) entre 0 et 1
FIELD_COLORS = {
    "PST_ISIN":            (0.2, 0.4, 1.0),
    "ISSUER":              (0.6, 0.2, 0.8),
    "MATURITY":            (0.2, 0.7, 0.3),
    "CAPITAL_PROTECTION":  (1.0, 0.6, 0.0),
    "WORST_OR_AVERAGE":    (0.9, 0.2, 0.2),
    "BIL":                 (0.9, 0.8, 0.0),
}


def value_to_search_terms(field_name: str, value) -> list:
    """
    Convertit une valeur extraite en liste de textes a chercher
    dans le PDF.

    On cherche plusieurs variantes pour maximiser les chances
    de trouver le texte exact tel qu'il apparait dans le document.

    Args:
        field_name: nom du champ (PST_ISIN, ISSUER, etc.)
        value: valeur extraite

    Returns:
        Liste de chaines a chercher dans le PDF.
    """
    if value is None:
        return []

    terms = []

    if field_name == "PST_ISIN":
        # ISIN : chercher le code exact
        terms.append(str(value))

    elif field_name == "BIL":
        if value is True:
            terms.append("BIL")
            terms.append("Banque Internationale")
        else:
            return []

    elif field_name == "CAPITAL_PROTECTION":
        # Chercher "100%", "100 %", "100"
        v = value
        if isinstance(v, float) and v == int(v):
            v = int(v)
        terms.append(f"{v}%")
        terms.append(f"{v} %")
        terms.append(str(v))

    elif field_name == "MATURITY":
        # La date dans le PDF est au format original, pas normalise
        # On cherche les composants : jour, mois, annee
        # Ex: "2029-03-01" -> chercher "01/03/2029", "01-03-2029", "2029"
        date_str = str(value)
        terms.append(date_str)
        if "-" in date_str:
            parts = date_str.split("-")
            if len(parts) == 3:
                year, month, day = parts
                terms.append(f"{day}/{month}/{year}")
                terms.append(f"{day}-{month}-{year}")
                terms.append(f"{day}.{month}.{year}")

    elif field_name == "WORST_OR_AVERAGE":
        if value == "W":
            terms.append("worst")
            terms.append("Worst")
            terms.append("worst-of")
            terms.append("Worst-of")
        elif value == "A":
            terms.append("average")
            terms.append("Average")
            terms.append("averaging")

    elif field_name == "ISSUER":
        # Chercher le nom complet et le premier mot
        terms.append(str(value))
        first_word = str(value).split()[0] if value else ""
        if len(first_word) > 3:
            terms.append(first_word)

    return terms


def find_words_on_page(page_words: list, search_text: str) -> list:
    """
    Cherche un texte dans les mots d'une page et retourne les
    positions des mots correspondants.

    Deux strategies :
      1. Match exact sur un seul mot
      2. Match sur une sequence de mots consecutifs

    Args:
        page_words: liste de mots pdfplumber (avec x0, top, x1, bottom).
        search_text: texte a chercher.

    Returns:
        Liste de dicts avec les coordonnees des mots trouves.
    """
    results = []

    # Strategie 1 : un seul mot contient le texte cherche
    for w in page_words:
        w_text = w["text"].strip()
        if search_text.lower() in w_text.lower() and len(search_text) >= 3:
            results.append({
                "x0": float(w["x0"]),
                "y0": float(w["top"]),
                "x1": float(w["x1"]),
                "y1": float(w["bottom"]),
            })
            return results

    # Strategie 2 : sequence de mots
    search_parts = search_text.lower().split()
    if len(search_parts) < 2:
        return results

    for i in range(len(page_words) - len(search_parts) + 1):
        match = True
        for j, part in enumerate(search_parts):
            w_text = page_words[i + j]["text"].strip().lower()
            if part not in w_text and w_text not in part:
                match = False
                break

        if match:
            # Fusionner les coordonnees de tous les mots de la sequence
            matched_words = page_words[i:i + len(search_parts)]
            results.append({
                "x0": min(float(w["x0"]) for w in matched_words),
                "y0": min(float(w["top"]) for w in matched_words),
                "x1": max(float(w["x1"]) for w in matched_words),
                "y1": max(float(w["bottom"]) for w in matched_words),
            })
            return results

    return results


def highlight_pdf(original_pdf_path: str, output_pdf_path: str,
                  extracted_values: dict) -> bool:
    """
    Cree une copie du PDF avec les champs surlignees en couleur.

    Pour chaque champ extrait, on cherche le texte correspondant
    page par page dans le PDF original, puis on ajoute un
    rectangle de surlignage colore par-dessus.

    Args:
        original_pdf_path: chemin du PDF original.
        output_pdf_path: chemin du PDF annote en sortie.
        extracted_values: dict des valeurs extraites.

    Returns:
        True si le PDF annote a ete cree, False sinon.
    """
    try:
        # Lecture du PDF avec pypdf (pour ecrire les annotations)
        reader = PdfReader(original_pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        highlights_count = 0

        # Lecture du PDF avec pdfplumber (pour localiser les mots)
        with pdfplumber.open(original_pdf_path) as pdf:

            for field_name, value in extracted_values.items():
                search_terms = value_to_search_terms(field_name, value)

                if not search_terms:
                    continue

                color = FIELD_COLORS.get(field_name, (0.5, 0.5, 0.5))
                found = False

                # Chercher page par page
                for page_num, page in enumerate(pdf.pages):
                    if found:
                        break

                    page_words = page.extract_words()
                    if not page_words:
                        continue

                    page_height = float(page.height)

                    # Essayer chaque terme de recherche
                    for term in search_terms:
                        positions = find_words_on_page(page_words, term)

                        if not positions:
                            continue

                        for pos in positions:
                            # Conversion des coordonnees
                            # pdfplumber : y depuis le haut
                            # pypdf : y depuis le bas
                            x0 = pos["x0"] - 1
                            x1 = pos["x1"] + 1
                            y0_pdf = page_height - pos["y1"] - 1
                            y1_pdf = page_height - pos["y0"] + 1

                            try:
                                highlight = Highlight(
                                    rect=(x0, y0_pdf, x1, y1_pdf),
                                    quad_points=ArrayObject([
                                        FloatObject(x0),
                                        FloatObject(y1_pdf),
                                        FloatObject(x1),
                                        FloatObject(y1_pdf),
                                        FloatObject(x0),
                                        FloatObject(y0_pdf),
                                        FloatObject(x1),
                                        FloatObject(y0_pdf),
                                    ]),
                                )
                                highlight["/C"] = ArrayObject([
                                    FloatObject(color[0]),
                                    FloatObject(color[1]),
                                    FloatObject(color[2]),
                                ])
                                highlight["/T"] = field_name
                                highlight["/Contents"] = (
                                    f"{field_name}: {value}"
                                )

                                writer.add_annotation(
                                    page_number=page_num,
                                    annotation=highlight,
                                )
                                highlights_count += 1
                                found = True

                            except Exception as e:
                                logger.debug(
                                    f"Annotation echouee {field_name}: {e}"
                                )

                        if found:
                            break

                if found:
                    logger.info(f"  {field_name} surligne : {value}")
                else:
                    logger.warning(f"  {field_name} non localise dans le PDF")

        # Sauvegarde
        if highlights_count > 0:
            output_path = Path(output_pdf_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                writer.write(f)

            logger.info(
                f"PDF annote : {output_path.name} "
                f"({highlights_count} surlignage(s))"
            )
            return True
        else:
            logger.warning("Aucun surlignage effectue.")
            return False

    except Exception as error:
        logger.error(f"Erreur PDF annote : {error}")
        return False
