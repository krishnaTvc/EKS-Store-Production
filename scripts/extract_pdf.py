"""
PDF Extraction and Normalization Pipeline
Reads dataset/dataset_for_eks.pdf, normalizes rows, validates records,
and produces:
  - data/normalized_catalog.csv
  - data/extraction_report.json
  - data/rejected_rows.csv
"""

import os
import re
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import pypdf

SEGMENT_MAPPING = {
    "WHISKY SEGMENT": ("whisky", None),
    "BRANDY SEGMENT": ("brandy", None),
    "RUM SEGMENT": ("rum", None),
    "VODKA SEGMENT": ("vodka", None),
    "WINE SEGMENT": ("wine", None),
    "GIN SEGMENT": ("gin", None),
    "BREEZER SEGMENT": ("ready-to-drink", "breezer"),
    "STRONG BEER SEGMENT": ("beer", "strong"),
    "LAGER BEER SEGMENT": ("beer", "lager"),
}

HEADER_TOKENS = {"o", "Supplie", "Size", "S.N", "Code MRP"}
IGNORE_PATTERNS = ["MRP RATES IN ANDHRA PRADESH", "Date :", "r Code Brand Code Product Code Size"]


def extract_pdf_data(pdf_path: str, output_dir: str):
    pdf_file = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    reader = pypdf.PdfReader(str(pdf_file))
    accepted_records = []
    rejected_records = []

    current_category = None
    current_subcategory = None
    source_date = "2024-10-15"

    seen_product_codes = {}

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        text = page.extract_text() or ""
        lines = text.splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line in HEADER_TOKENS:
                continue

            if any(ign in line for ign in IGNORE_PATTERNS):
                continue

            # Check if this line is a segment header
            if line in SEGMENT_MAPPING:
                current_category, current_subcategory = SEGMENT_MAPPING[line]
                continue

            # Match standard data line
            # Format: S.No (int) Supplier_Code (4-digits) Brand_Code-Brand_Name Product_Code Size (int) Size_Code (2-chars) MRP (decimal)
            m = re.match(r"^(\d+)\s+(\d{4})\s+(\d{4}-.+?)\s+([0-9A-Z]{9,16}(?:\s+[A-Z])?)\s+(\d+)\s+([A-Z]{2})\s+(\d+(?:\.\d+)?)$", line)
            if not m:
                rejected_records.append({
                    "raw_line": line,
                    "page": page_num,
                    "reason": "Line format does not match expected row structure"
                })
                continue

            s_no, supp_code, brand_full, raw_prod_code, raw_size_ml, size_code, raw_mrp = m.groups()
            prod_code = raw_prod_code.replace(" ", "")

            # Reconstruct brand code and name
            if "-" in brand_full:
                b_code, b_name = brand_full.split("-", 1)
            else:
                b_code, b_name = "", brand_full

            b_code = b_code.strip()
            b_name = b_name.strip()

            # Validation
            reasons = []
            if not current_category:
                reasons.append("Missing category context for row")

            try:
                size_ml = int(raw_size_ml)
                if size_ml <= 0:
                    reasons.append(f"Invalid bottle size: {size_ml} <= 0")
            except ValueError:
                reasons.append(f"Bottle size not an integer: {raw_size_ml}")
                size_ml = None

            try:
                mrp = Decimal(raw_mrp)
                if mrp < 0:
                    reasons.append(f"Negative MRP price: {mrp}")
            except (ValueError, InvalidOperation):
                reasons.append(f"MRP not a valid decimal: {raw_mrp}")
                mrp = None

            if prod_code in seen_product_codes:
                prev_loc = seen_product_codes[prod_code]
                reasons.append(f"Duplicate product_code '{prod_code}' already seen at page {prev_loc}")

            if reasons:
                rejected_records.append({
                    "raw_line": line,
                    "page": page_num,
                    "reason": "; ".join(reasons)
                })
            else:
                seen_product_codes[prod_code] = page_num
                accepted_records.append({
                    "product_code": prod_code,
                    "supplier_code": supp_code,
                    "brand_code": b_code,
                    "product_name": b_name,
                    "category": current_category,
                    "subcategory": current_subcategory or "",
                    "size_ml": size_ml,
                    "size_code": size_code,
                    "mrp": str(mrp),
                    "currency": "INR",
                    "source_date": source_date,
                    "source_page": page_num,
                    "active": True
                })

    # Output CSV
    csv_path = out_dir / "normalized_catalog.csv"
    fieldnames = [
        "product_code", "supplier_code", "brand_code", "product_name",
        "category", "subcategory", "size_ml", "size_code", "mrp",
        "currency", "source_date", "source_page", "active"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(accepted_records)

    # Output Rejected CSV
    rejected_csv_path = out_dir / "rejected_rows.csv"
    with open(rejected_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["raw_line", "page", "reason"])
        writer.writeheader()
        writer.writerows(rejected_records)

    # Generate Summary Report
    category_counts = {}
    for r in accepted_records:
        cat = r["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    report = {
        "source_file": str(pdf_path),
        "source_date": source_date,
        "total_pages_scanned": len(reader.pages),
        "total_records_accepted": len(accepted_records),
        "total_records_rejected": len(rejected_records),
        "category_distribution": category_counts,
        "validation_summary": {
            "all_product_codes_unique": len(accepted_records) == len(seen_product_codes),
            "all_sizes_positive": all(r["size_ml"] > 0 for r in accepted_records),
            "all_prices_non_negative": all(Decimal(r["mrp"]) >= 0 for r in accepted_records),
            "source_date": source_date
        }
    }

    report_path = out_dir / "extraction_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Extraction Complete!")
    print(f"  Accepted: {len(accepted_records)}")
    print(f"  Rejected: {len(rejected_records)}")
    print(f"  Category breakdown: {category_counts}")
    print(f"  Files written:")
    print(f"    - {csv_path}")
    print(f"    - {report_path}")
    print(f"    - {rejected_csv_path}")

    return report


if __name__ == "__main__":
    extract_pdf_data("dataset/dataset_for_eks.pdf", "data")

