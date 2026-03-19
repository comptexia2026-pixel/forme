import pdfplumber
from pathlib import Path
import re


def clean_word(text):
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', text)
    return text


def extract_words(pdf_path):

    words_all = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):

            print(f"\n PAGE {page_num} ---------------------")

            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=2
            )

            print(f" Nb mots extraits: {len(words)}")

            for i, w in enumerate(words[:20]):  # preview
                print(f"RAW WORD {i}: {w['text']}")

            for w in words:
                cleaned = clean_word(w["text"])

                words_all.append({
                    "text": cleaned,
                    "x": w["x0"],
                    "y": w["top"],
                    "page": page_num
                })

    return words_all


def group_lines(words, y_threshold=5):

    lines = {}

    for w in words:
        y_key = round(w["y"] / y_threshold) * y_threshold
        lines.setdefault((w["page"], y_key), []).append(w)

    print(f"\n Nb lignes détectées: {len(lines)}")

    grouped = []

    for key in sorted(lines.keys()):
        line = sorted(lines[key], key=lambda x: x["x"])

        # debug preview
        preview = " ".join(w["text"] for w in line[:10])
        print(f"LINE PREVIEW: {preview}")

        grouped.append(line)

    return grouped


def reconstruct_text(lines):

    result = []

    for i, line in enumerate(lines):

        line_text = ""
        prev_x = None

        for w in line:
            if prev_x is not None:
                gap = w["x"] - prev_x
                spaces = max(1, int(gap / 5))
                line_text += " " * spaces

            line_text += w["text"]
            prev_x = w["x"]

        if i < 20:
            print(f"\n🧾 RECONSTRUCTED LINE {i}:")
            print(line_text)

        result.append(line_text)

    return "\n".join(result)


def process_pdf(pdf_path, output_path):

    print("\n START PROCESS\n")

    words = extract_words(pdf_path)

    print("\n================ WORDS OK ================\n")

    lines = group_lines(words)

    print("\n================ LINES OK ================\n")

    text = reconstruct_text(lines)

    print("\n================ TEXT OK ================\n")

    Path(output_path).write_text(text, encoding="utf-8")

    print(f"\n TXT créé : {output_path}")


# ================= TEST =================

pdf_file = r"C:\Users\kassi\Downloads\TS_Extractor_V1\TS_Extractor_V1.1\data\input\Input_BIL_en\termsheet-ch1284250102-en.pdf"
output_txt = r"C:\Users\kassi\Downloads\output_debug.txt"

process_pdf(pdf_file, output_txt)
