from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


PDF_PATH = Path("/Users/azrilhilmi/Downloads/PHARMACY - Quotation 22052025_LH.pdf")
OUT_PATH = Path("/Users/azrilhilmi/Documents/New project/outputs/pdf_extract/quotation_data.json")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def to_number(value: str | None):
    if value is None or value == "":
        return None
    if re.fullmatch(r"\d+", value):
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def extract_page_items(page):
    items = []

    def visitor(text, cm, tm, font_dict, font_size):
        text = clean_text(text)
        if text:
            items.append(
                {
                    "x": round(float(tm[4]), 1),
                    "y": round(float(tm[5]), 1),
                    "text": text,
                }
            )

    page.extract_text(visitor_text=visitor)
    return sorted(items, key=lambda d: (-d["y"], d["x"]))


def join_fragments(parts):
    by_y = {}
    for part in parts:
        by_y.setdefault(part["y"], []).append(part)

    lines = []
    for y in sorted(by_y, reverse=True):
        line_parts = sorted(by_y[y], key=lambda d: d["x"])
        line = " ".join(part["text"] for part in line_parts)
        line = re.sub(r"\s*-\s*", "-", line)
        lines.append(clean_text(line))
    return clean_text(" ".join(lines))


def parse_products(reader):
    parsed_by_key = {}

    for page_index, page in enumerate(reader.pages, 1):
        items = extract_page_items(page)
        product_marks = [
            item
            for item in items
            if 70 <= item["x"] <= 90 and re.fullmatch(r"CP\d{5}", item["text"])
        ]
        product_marks.sort(key=lambda d: -d["y"])

        for idx, mark in enumerate(product_marks):
            y = mark["y"]
            top = y + 8 if idx == 0 else (product_marks[idx - 1]["y"] + y) / 2
            bottom = y - 8 if idx == len(product_marks) - 1 else (product_marks[idx + 1]["y"] + y) / 2

            desc_parts = [
                item
                for item in items
                if bottom < item["y"] < top and 190 <= item["x"] < 360
            ]
            desc_full = join_fragments(desc_parts)

            dcha_code = ""
            description = desc_full
            first = re.match(r"^(\S+)\s+(.*)$", desc_full)
            if first:
                dcha_code = first.group(1)
                description = first.group(2)

            ea_text = next(
                (
                    item["text"]
                    for item in items
                    if abs(item["y"] - y) < 1 and 365 <= item["x"] <= 390
                ),
                "",
            )
            ea = to_number(ea_text)

            trailing_number = re.match(r"^(.*)\s+(\d+)$", description)
            if trailing_number and to_number(trailing_number.group(2)) == ea:
                description = trailing_number.group(1)

            material_code = next(
                (
                    item["text"]
                    for item in items
                    if abs(item["y"] - y) < 1 and 120 <= item["x"] <= 170
                ),
                "",
            )

            price_1_14 = next(
                (
                    item["text"]
                    for item in items
                    if abs(item["y"] - y) < 1 and 400 <= item["x"] <= 435
                ),
                "",
            )
            price_15_plus = next(
                (
                    item["text"]
                    for item in items
                    if abs(item["y"] - y) < 1 and 440 <= item["x"] <= 475
                ),
                "",
            )
            rsp = next(
                (
                    item["text"]
                    for item in items
                    if abs(item["y"] - y) < 1 and 480 <= item["x"] <= 525
                ),
                "",
            )

            parsed_by_key[(page_index, y)] = {
                "page": page_index,
                "y": y,
                "code_number": mark["text"],
                "material_code": material_code,
                "dcha_material_code": dcha_code,
                "item_description": clean_text(description),
                "ea": ea,
                "price_1_14_boxes": to_number(price_1_14),
                "price_15_plus_boxes": to_number(price_15_plus),
                "retail_rsp_price": to_number(rsp),
            }

    return parsed_by_key


def assign_sections(reader, products_by_key):
    rows = []
    section = ""
    subsection = ""

    for page_index, page in enumerate(reader.pages, 1):
        items = extract_page_items(page)
        events = []
        for item in items:
            if 70 <= item["x"] <= 90:
                text = item["text"]
                if re.fullmatch(r"CP\d{5}", text):
                    events.append(("product", item["y"], item))
                elif (
                    text.startswith("COLOPLAST")
                    or text.startswith("THE ")
                    or text in {"SENSURA", "ALTERNA"}
                    or text.startswith("BRAVA")
                ):
                    events.append(("category", item["y"], item))

        for kind, y, item in sorted(events, key=lambda e: -e[1]):
            text = item["text"].rstrip(":")
            if kind == "category":
                if text.startswith("COLOPLAST") or text.startswith("THE "):
                    section = text
                    subsection = ""
                else:
                    subsection = text
            else:
                row = dict(products_by_key[(page_index, y)])
                row["section"] = section
                row["subsection"] = subsection
                rows.append(row)

    return rows


def extract_notes(reader):
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    notes = {
        "Date": next((line for line in lines if re.fullmatch(r"\d{1,2} [A-Za-z]+ \d{4}", line)), ""),
        "Subject": "QUOTATION FOR COLOPLAST OSTOMY CARE PRODUCTS",
        "Manufacturer": "Coloplast Denmark",
        "Delivery": "Ex-stock within 7-14 days (Subject to stock availability upon order confirmation)",
        "Validity": "30 days",
        "Minimum order value": "RM 250.00 (WM) / RM 500.00 (EM)",
        "Source file": str(PDF_PATH),
    }
    return notes


def main():
    reader = PdfReader(str(PDF_PATH))
    products = parse_products(reader)
    rows = assign_sections(reader, products)
    payload = {
        "notes": extract_notes(reader),
        "items": rows,
        "row_count": len(rows),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} with {len(rows)} product rows")


if __name__ == "__main__":
    main()
