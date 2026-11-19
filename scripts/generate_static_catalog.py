import csv
import json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config" / "image_mappings.yaml", "r", encoding="utf-8") as f:
    mappings = yaml.safe_load(f)

brand_map = {str(k).strip(): v.get("s3_key") for k, v in mappings.get("brand_mappings", {}).items()}
prod_map = {str(k).strip(): v for k, v in mappings.get("product_overrides", {}).items()}

with open(ROOT / "data" / "normalized_catalog.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

items = []
for r in rows:
    p_code = r["product_code"].strip()
    b_code = r["brand_code"].strip()
    img_key = prod_map.get(p_code) or brand_map.get(b_code) or "catalog/placeholder.png"
    items.append({
        "id": p_code,
        "product_code": p_code,
        "supplier_code": r["supplier_code"].strip(),
        "brand_code": b_code,
        "product_name": r["product_name"].strip(),
        "category": r["category"].strip(),
        "subcategory": r["subcategory"].strip() if r["subcategory"] else None,
        "size_ml": int(r["size_ml"]),
        "size_code": r["size_code"].strip(),
        "mrp": f"{float(r['mrp']):.2f}",
        "currency": "INR",
        "origin_group": r.get("origin_group", "domestic"),
        "country_of_origin": r.get("country_of_origin", "India"),
        "image_url": f"assets/{img_key}",
        "active": True
    })

out_file = ROOT / "frontend" / "public" / "js" / "catalog_data.js"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("// Embedded static catalog data for offline and instant preview\n")
    f.write("window.EMBEDDED_CATALOG = ")
    json.dump(items, f, indent=2)
    f.write(";\n")

print(f"Wrote {len(items)} items to {out_file}")
