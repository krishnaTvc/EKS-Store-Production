"""
Image Discovery, Ingestion, and Manifest Builder
Copies supplied local images, downloads verified open/manufacturer bottle images,
validates image integrity with Pillow, creates fallback placeholder,
and generates:
  - config/image_manifest.json
  - config/image_mappings.yaml
"""

import os
import shutil
from pathlib import Path
import json
import yaml
import requests
from PIL import Image, ImageDraw, ImageFont

IMAGES_SPEC = [
    # 1. Supplied user images (from catalog-db-images/)
    {
        "category": "whisky",
        "product_name": "SEAGRAM'S BLENDERS PRIDE EXCLUSIVE PREMIUM WHISKY",
        "brand_code": "1139",
        "relative_path": "catalog/whisky/blenders-pride.jpeg",
        "source_type": "supplied",
        "source_path": "catalog-db-images/Blenders.jpeg",
        "source_url": "User Supplied (catalog-db-images/Blenders.jpeg)",
        "license": "Supplied demo asset",
        "product_code_overrides": []
    },
    {
        "category": "whisky",
        "product_name": "SEAGRAM'S ROYAL STAG CLASSIC WHISKY",
        "brand_code": "1138",
        "relative_path": "catalog/whisky/royal-stag.jpg",
        "source_type": "supplied",
        "source_path": "catalog-db-images/stag.jpg",
        "source_url": "User Supplied (catalog-db-images/stag.jpg)",
        "license": "Supplied demo asset",
        "product_code_overrides": []
    },
    {
        "category": "whisky",
        "product_name": "STERLING RESERVE B10 ORIGINAL BLENDED WHISKY",
        "brand_code": "0277",
        "relative_path": "catalog/whisky/sterling-reserve-b10.jpeg",
        "source_type": "supplied",
        "source_path": "catalog-db-images/sterling.jpeg",
        "source_url": "User Supplied (catalog-db-images/sterling.jpeg)",
        "license": "Supplied demo asset",
        "product_code_overrides": []
    },
    # 2. Downloaded category images
    {
        "category": "whisky",
        "product_name": "JOHNNIE WALKER RED LABEL BLENDED SCOTCH WHISKY",
        "brand_code": "1119",
        "relative_path": "catalog/whisky/johnnie-walker-red-label.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Johnnie_Walker_Red_Label.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "whisky",
        "product_name": "JAMESON IRISH WHISKY",
        "brand_code": "1127",
        "relative_path": "catalog/whisky/jameson-irish.png",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Jameson_Irish_Whiskey.PNG?width=600",
        "license": "CC BY-SA 2.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "whisky",
        "product_name": "BALLANTINE'S FINEST BLENDED SCOTCH WHISKY",
        "brand_code": "1126",
        "relative_path": "catalog/whisky/ballantines-finest.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Ballantines_Scotch_Whisky_PL.JPG?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "whisky",
        "product_name": "Dewar's Blended Scotch Whisky White Label",
        "brand_code": "1092",
        "relative_path": "catalog/whisky/dewars-white-label.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Dewar%27s_White_Label_Scotch_Whisky.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "brandy",
        "product_name": "TI MANSION HOUSE RAREST SPIRIT FRENCH BRANDY",
        "brand_code": "1109",
        "relative_path": "catalog/brandy/mansion-house.jpg",
        "source_type": "remote",
        "source_url": "https://tilind.com/wp-content/uploads/2025/05/MH-Core-600-x-600px.jpg",
        "license": "Official Brand Visual (Tilaknagar Industries)",
        "product_code_overrides": []
    },
    {
        "category": "brandy",
        "product_name": "MORPHEUS XO BLENDED RESERVE BRANDY",
        "brand_code": "0519",
        "relative_path": "catalog/brandy/morpheus-xo.jpg",
        "source_type": "remote",
        "source_url": "https://radicokhaitan.com/wp-content/uploads/2019/03/Morpheus-XO-1.jpg",
        "license": "Official Brand Visual (Radico Khaitan)",
        "product_code_overrides": []
    },
    {
        "category": "rum",
        "product_name": "OLD MONK EXTRA SPECIAL XXX RARE RUM",
        "brand_code": "1038",
        "relative_path": "catalog/rum/old-monk.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Old_monk_rum_bottle.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "rum",
        "product_name": "Bacardi Carta Blanca Ultra Platinum Superior White Rum",
        "brand_code": "1101",
        "relative_path": "catalog/rum/bacardi-carta-blanca.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Bacardi_%28on_white%29.jpg?width=600",
        "license": "CC BY-SA 2.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "vodka",
        "product_name": "MAGIC MOMENTS REMIX GREEN APPLE PREMIUM FLAVOURED VODKA",
        "brand_code": "1151",
        "relative_path": "catalog/vodka/magic-moments-green-apple.jpg",
        "source_type": "remote",
        "source_url": "https://radicokhaitan.com/wp-content/uploads/2019/03/MM-normal.jpg",
        "license": "Official Brand Visual (Radico Khaitan)",
        "product_code_overrides": []
    },
    {
        "category": "vodka",
        "product_name": "ABSOLUT VODKA",
        "brand_code": "1122",
        "relative_path": "catalog/vodka/absolut-vodka.png",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Absolut_vodka_bottle.png?width=600",
        "license": "CC BY 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "wine",
        "product_name": "FRATELLI SHIRAZ",
        "brand_code": "0901",
        "relative_path": "catalog/wine/fratelli-shiraz.png",
        "source_type": "remote",
        "source_url": "http://fratelliwines.in/cdn/shop/files/Classic_Shiraz.png",
        "license": "Official Brand Visual (Fratelli Wines)",
        "product_code_overrides": []
    },
    {
        "category": "gin",
        "product_name": "BEEFEATER LONDON DRY GIN",
        "brand_code": "1128",
        "relative_path": "catalog/gin/beefeater-london-dry.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Beefeater_Gin.jpg?width=600",
        "license": "Public Domain (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "beer",
        "product_name": "KINGFISHER ULTRA SUPER PREMIUM LAGER BEER",
        "brand_code": "5118",
        "relative_path": "catalog/beer/kingfisher-ultra.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Kingfisher_beer_bottle.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "beer",
        "product_name": "CARLSBERG PREMIUM ELEPHANT STRONG PILSNER BEER",
        "brand_code": "5120",
        "relative_path": "catalog/beer/carlsberg-elephant.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Carlsberg_beer.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    },
    {
        "category": "ready-to-drink",
        "product_name": "Breezer Platinum Tangy Cranberry",
        "brand_code": "1014",
        "relative_path": "catalog/ready-to-drink/bacardi-breezer.jpg",
        "source_type": "remote",
        "source_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Bacardi_Breezer_Bottles.jpg?width=600",
        "license": "CC BY-SA 3.0 (Wikimedia Commons)",
        "product_code_overrides": []
    }
]


def create_placeholder(output_path: Path):
    """Generates a clean, modern placeholder image for unmapped catalog items."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (400, 400), color=(240, 243, 246, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple beverage bottle outline
    draw.rounded_rectangle([150, 60, 250, 320], radius=15, fill=(220, 226, 232, 255), outline=(180, 190, 200, 255), width=3)
    draw.rectangle([180, 30, 220, 70], fill=(160, 175, 190, 255), outline=(140, 155, 170, 255), width=2)
    draw.text((200, 200), "NO IMAGE", fill=(120, 130, 140, 255), anchor="mm")
    img.save(output_path, "PNG")
    print(f"Created generic placeholder at {output_path}")


def process_images():
    base_assets_dir = Path("assets")
    base_assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create Placeholder
    placeholder_path = base_assets_dir / "catalog" / "placeholder.png"
    create_placeholder(placeholder_path)

    manifest_entries = []
    brand_mappings = {}
    product_overrides = {}

    headers = {"User-Agent": "EksStoreApp/1.0 (dev@eks-store.internal; https://github.com/eks-store)"}

    for spec in IMAGES_SPEC:
        s3_key = spec["relative_path"]
        local_dest = base_assets_dir / s3_key
        local_dest.parent.mkdir(parents=True, exist_ok=True)

        if spec["source_type"] == "supplied":
            src = Path(spec["source_path"])
            if src.exists():
                shutil.copy2(src, local_dest)
                print(f"Copied user supplied: {src} -> {local_dest}")
            else:
                print(f"WARNING: Supplied image not found: {src}")
        elif spec["source_type"] == "remote":
            if not local_dest.exists() or local_dest.stat().st_size == 0:
                print(f"Downloading: {spec['source_url']} -> {local_dest}")
                try:
                    resp = requests.get(spec["source_url"], headers=headers, timeout=15)
                    resp.raise_for_status()
                    with open(local_dest, "wb") as f:
                        f.write(resp.content)
                except Exception as e:
                    print(f"Error downloading {spec['source_url']}: {e}")

        # Validate with Pillow
        is_valid = False
        img_info = {}
        if local_dest.exists() and local_dest.stat().st_size > 0:
            try:
                with Image.open(local_dest) as im:
                    im.verify()
                # Reopen to read dimensions
                with Image.open(local_dest) as im:
                    img_info = {"format": im.format, "width": im.width, "height": im.height}
                is_valid = True
            except Exception as e:
                print(f"Validation failed for {local_dest}: {e}")

        manifest_entry = {
            "local_path": str(local_dest.as_posix()),
            "s3_object_key": s3_key,
            "category": spec["category"],
            "brand_code": spec["brand_code"],
            "product_name": spec["product_name"],
            "source_url": spec["source_url"],
            "license": spec["license"],
            "is_valid_image": is_valid,
            "image_details": img_info
        }
        manifest_entries.append(manifest_entry)

        # Mapping config
        brand_mappings[spec["brand_code"]] = {
            "category": spec["category"],
            "brand_code": spec["brand_code"],
            "product_name": spec["product_name"],
            "s3_key": s3_key
        }

        for override_code in spec["product_code_overrides"]:
            product_overrides[override_code] = s3_key

    # Save manifest
    config_dir = Path("config")
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = config_dir / "image_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, indent=2)

    # Save mappings YAML
    mappings_data = {
        "placeholder_key": "catalog/placeholder.png",
        "brand_mappings": brand_mappings,
        "product_overrides": product_overrides
    }
    mappings_file = config_dir / "image_mappings.yaml"
    with open(mappings_file, "w", encoding="utf-8") as f:
        yaml.dump(mappings_data, f, default_flow_style=False, sort_keys=False)

    print(f"\nImage processing complete!")
    print(f"Total curated images: {len(manifest_entries)}")
    valid_count = sum(1 for m in manifest_entries if m['is_valid_image'])
    print(f"Validated readable images: {valid_count}/{len(manifest_entries)}")
    print(f"Saved manifest: {manifest_file}")
    print(f"Saved mappings YAML: {mappings_file}")


if __name__ == "__main__":
    process_images()
