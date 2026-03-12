Voici les modifications fichier par fichier. Je vous donne exactement quoi ajouter et ou.

---

**FICHIER 1 : `modules/pdf_extractor.py`**

Ajoutez cette methode **a la fin de la classe PDFExtractor**, juste avant le dernier `get_metadata` :

```python
    def extract_words_with_positions(self) -> list:
        """
        Extrait chaque mot avec sa position sur la page.
        Retourne une liste de dicts :
        [{"text": "XS123...", "page": 1, "x0": 100, "y0": 200, "x1": 180, "y1": 215}, ...]
        """
        words = []
        try:
            with pdfplumber.open(str(self.filepath)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_words = page.extract_words()
                    for w in page_words:
                        words.append({
                            "text": w["text"],
                            "page": page_num,
                            "x0": float(w["x0"]),
                            "y0": float(w["top"]),
                            "x1": float(w["x1"]),
                            "y1": float(w["bottom"]),
                        })
        except Exception as error:
            logger.error(f"Erreur extraction des positions : {error}")
        return words
```

---

**FICHIER 2 : Nouveau fichier `modules/pdf_highlighter.py`**

Creez ce fichier dans le dossier `modules/` :

```python
# =============================================================================
# modules/pdf_highlighter.py
# Surligne les champs trouves directement dans le PDF.
# Utilise pdfplumber pour localiser et pypdf pour dessiner.
# =============================================================================

import logging
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject

logger = logging.getLogger(__name__)

# Couleurs par champ (R, G, B) entre 0 et 1
FIELD_COLORS = {
    "PST_ISIN":            (0.2, 0.4, 1.0),   # bleu
    "ISSUER":              (0.6, 0.2, 0.8),   # violet
    "MATURITY":            (0.2, 0.7, 0.3),   # vert
    "CAPITAL_PROTECTION":  (1.0, 0.6, 0.0),   # orange
    "WORST_OR_AVERAGE":    (0.9, 0.2, 0.2),   # rouge
    "BIL":                 (0.9, 0.8, 0.0),   # jaune
}


def find_value_positions(words: list, value: str, field_name: str) -> list:
    """
    Cherche la valeur extraite dans la liste des mots positionnes.

    Pour les valeurs multi-mots (ex: "BNP Paribas SA"), on cherche
    la sequence de mots consecutifs sur la meme page.

    Args:
        words: liste des mots avec positions (depuis PDFExtractor).
        value: la valeur a chercher (ex: "XS1234567890").
        field_name: nom du champ (pour le log).

    Returns:
        Liste de dicts avec page, x0, y0, x1, y1 pour chaque
        mot correspondant.
    """
    if value is None:
        return []

    value_str = str(value)

    # Cas booleen BIL
    if field_name == "BIL":
        if value is True:
            value_str = "BIL"
        else:
            return []

    # Cas float (ex: 90.0 -> chercher "90")
    if field_name == "CAPITAL_PROTECTION" and isinstance(value, float):
        if value == int(value):
            value_str = str(int(value))

    # Cas simple : valeur en un seul mot
    matches = []
    for w in words:
        if value_str in w["text"] or w["text"] in value_str:
            # Verification plus stricte pour eviter les faux positifs
            if (value_str == w["text"]
                or value_str.startswith(w["text"])
                or w["text"].startswith(value_str)):
                matches.append(w)

    if matches:
        return matches

    # Cas multi-mots : chercher la sequence
    value_parts = value_str.split()
    if len(value_parts) > 1:
        for i in range(len(words) - len(value_parts) + 1):
            found = True
            for j, part in enumerate(value_parts):
                if part.lower() not in words[i + j]["text"].lower():
                    found = False
                    break
            if found and all(
                words[i + k]["page"] == words[i]["page"]
                for k in range(len(value_parts))
            ):
                return [words[i + k] for k in range(len(value_parts))]

    return []


def highlight_pdf(original_pdf_path: str, output_pdf_path: str,
                  words: list, extracted_values: dict) -> bool:
    """
    Cree une copie du PDF avec les champs surlignees en couleur.

    Args:
        original_pdf_path: chemin du PDF original.
        output_pdf_path: chemin du PDF annote en sortie.
        words: liste des mots avec positions.
        extracted_values: dict des valeurs extraites
            (ex: {"PST_ISIN": "XS123...", "ISSUER": "BNP Paribas"}).

    Returns:
        True si le PDF a ete cree, False sinon.
    """
    try:
        reader = PdfReader(original_pdf_path)
        writer = PdfWriter()

        # Copie de toutes les pages
        for page in reader.pages:
            writer.add_page(page)

        # Pour chaque champ, trouver les positions et surligner
        highlights_count = 0

        for field_name, value in extracted_values.items():
            if value is None:
                continue

            color = FIELD_COLORS.get(field_name, (0.5, 0.5, 0.5))
            positions = find_value_positions(words, value, field_name)

            for pos in positions:
                page_index = pos["page"] - 1  # pypdf utilise index 0

                if page_index < 0 or page_index >= len(writer.pages):
                    continue

                # Coordonnees du rectangle de surlignage
                # pdfplumber et pypdf utilisent le meme systeme de
                # coordonnees PDF (origine en bas a gauche)
                # Mais pdfplumber donne "top" depuis le haut de la page
                # Il faut convertir : y_pdf = hauteur_page - y_pdfplumber
                page_height = float(
                    writer.pages[page_index].mediabox.height
                )

                x0 = pos["x0"] - 2
                x1 = pos["x1"] + 2
                y0_pdf = page_height - pos["y1"] - 2
                y1_pdf = page_height - pos["y0"] + 2

                # Creation de l'annotation highlight
                try:
                    highlight = Highlight(
                        rect=(x0, y0_pdf, x1, y1_pdf),
                        quad_points=ArrayObject([
                            FloatObject(x0), FloatObject(y1_pdf),
                            FloatObject(x1), FloatObject(y1_pdf),
                            FloatObject(x0), FloatObject(y0_pdf),
                            FloatObject(x1), FloatObject(y0_pdf),
                        ]),
                    )
                    highlight["/C"] = ArrayObject([
                        FloatObject(color[0]),
                        FloatObject(color[1]),
                        FloatObject(color[2]),
                    ])
                    highlight["/T"] = field_name
                    highlight["/Contents"] = f"{field_name}: {value}"

                    writer.add_annotation(
                        page_number=page_index,
                        annotation=highlight,
                    )
                    highlights_count += 1

                except Exception as ann_error:
                    logger.debug(
                        f"Annotation echouee pour {field_name}: {ann_error}"
                    )

        if highlights_count > 0:
            output_path = Path(output_pdf_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                writer.write(f)

            logger.info(
                f"PDF annote cree : {output_path.name} "
                f"({highlights_count} surlignage(s))"
            )
            return True
        else:
            logger.warning("Aucun surlignage a ajouter.")
            return False

    except Exception as error:
        logger.error(f"Erreur creation PDF annote : {error}")
        return False
```

---

**FICHIER 3 : `main.py`**

**Modification 1** -- Ajoutez l'import en haut, apres les autres imports de modules :

```python
from modules.pdf_highlighter import highlight_pdf
```

**Modification 2** -- Dans la fonction `process_single_pdf`, apres la ligne `extraction_results = field_extractor.extract_all()` et avant le `return`, ajoutez :

```python
    # Etape 3 : extraction des positions des mots pour le surlignage
    word_positions = pdf_extractor.extract_words_with_positions()

    # Etape 4 : creation du PDF surligne
    annotated_dir = config.OUTPUT_DIR / "annotated"
    annotated_pdf_path = annotated_dir / f"annotated_{filepath.name}"

    highlight_pdf(
        original_pdf_path=str(filepath),
        output_pdf_path=str(annotated_pdf_path),
        words=word_positions,
        extracted_values=extraction_results["values"],
    )
```

**Modification 3** -- Toujours dans `process_single_pdf`, dans le dictionnaire `record` retourne a la fin, ajoutez une cle :

```python
    record = {
        "source_file": filepath.name,
        "values": extraction_results["values"],
        "confidence": extraction_results["confidence"],
        "metadata": pdf_extractor.get_metadata(),
        "annotated_pdf": str(annotated_pdf_path),  # <- ajoutez cette ligne
    }
```

---

**FICHIER 4 : `app.py` (Streamlit)**

**Modification 1** -- Dans la fonction `process_uploaded_pdf`, apres `results = field_extractor.extract_all()` et avant le `return`, ajoutez :

```python
        # Surlignage du PDF
        from modules.pdf_highlighter import highlight_pdf

        word_positions = pdf_extractor.extract_words_with_positions()

        annotated_dir = Path(tempfile.mkdtemp())
        annotated_path = annotated_dir / f"annotated_{uploaded_file.name}"

        highlight_pdf(
            original_pdf_path=str(temp_path),
            output_pdf_path=str(annotated_path),
            words=word_positions,
            extracted_values=results["values"],
        )

        # Lire les bytes du PDF annote
        annotated_bytes = None
        if annotated_path.exists():
            with open(annotated_path, "rb") as f:
                annotated_bytes = f.read()
```

**Modification 2** -- Dans le `return` de cette meme fonction, ajoutez :

```python
        return {
            "source_file": uploaded_file.name,
            "values": results["values"],
            "confidence": results["confidence"],
            "annotated_pdf": annotated_bytes,  # <- ajoutez cette ligne
        }
```

**Modification 3** -- Dans la section "Detail par document", apres la boucle des champs et avant la fermeture du `with st.expander`, ajoutez :

```python
                # Bouton de telechargement du PDF annote
                if record.get("annotated_pdf"):
                    st.download_button(
                        label="Telecharger le PDF surligne",
                        data=record["annotated_pdf"],
                        file_name=f"annotated_{record['source_file']}",
                        mime="application/pdf",
                        key=f"pdf_{record['source_file']}",
                    )
```

---

**Resume des modifications :**

| Fichier | Action |
|---|---|
| `modules/pdf_extractor.py` | Ajouter 1 methode `extract_words_with_positions` |
| `modules/pdf_highlighter.py` | Nouveau fichier (a creer) |
| `main.py` | Ajouter 1 import + 8 lignes dans `process_single_pdf` |
| `app.py` | Ajouter ~15 lignes dans `process_uploaded_pdf` + 1 bouton download |

Zero nouvelle dependance. Ca utilise pdfplumber + pypdf que vous avez deja.