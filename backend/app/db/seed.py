"""Idempotent database seeding script for development and integration testing.

Populates categories (smartphones, laptops, external SSDs) and reference catalog
products/variants without inventing fake evaluation scores, prices, or evidence.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.models.product_family import ProductFamily
from app.models.variant import Variant, compute_config_hash

logger = logging.getLogger("review_master.seed")

SEED_CATEGORIES: list[dict[str, Any]] = [
    {
        "key": "smartphone",
        "name": "Smartphones",
        "schema_version": "1.0.0",
        "spec_schema": {
            "type": "object",
            "properties": {
                "ram_gb": {"type": "integer"},
                "storage_gb": {"type": "integer"},
            },
        },
        "status": "active",
    },
    {
        "key": "laptop",
        "name": "Laptops",
        "schema_version": "1.0.0",
        "spec_schema": {
            "type": "object",
            "properties": {
                "processor": {"type": "string"},
                "ram_gb": {"type": "integer"},
            },
        },
        "status": "active",
    },
    {
        "key": "external_ssd",
        "name": "External SSDs",
        "schema_version": "1.0.0",
        "spec_schema": {
            "type": "object",
            "properties": {
                "capacity_tb": {"type": "number"},
                "interface": {"type": "string"},
            },
        },
        "status": "active",
    },
]

SEED_CATALOG: list[dict[str, Any]] = [
    # --- Smartphones ---
    {
        "category_key": "smartphone",
        "family_name": "Galaxy S Series",
        "manufacturer": "Samsung",
        "product_name": "Samsung Galaxy S24 Ultra",
        "mpn": "SM-S928B",
        "gtin": "8806095300000",
        "generation": "2024",
        "variants": [
            {
                "sku_label": "Samsung Galaxy S24 Ultra (12GB RAM, 256GB, Titanium Black)",
                "configuration": {
                    "ram_gb": 12,
                    "storage_gb": 256,
                    "color": "Titanium Black",
                },
            },
            {
                "sku_label": "Samsung Galaxy S24 Ultra (12GB RAM, 512GB, Titanium Gray)",
                "configuration": {
                    "ram_gb": 12,
                    "storage_gb": 512,
                    "color": "Titanium Gray",
                },
            },
        ],
    },
    {
        "category_key": "smartphone",
        "family_name": "iPhone",
        "manufacturer": "Apple",
        "product_name": "Apple iPhone 16 Pro",
        "mpn": "MYNE3HN/A",
        "gtin": "195949000000",
        "generation": "16",
        "variants": [
            {
                "sku_label": "Apple iPhone 16 Pro (128GB, Natural Titanium)",
                "configuration": {"storage_gb": 128, "color": "Natural Titanium"},
            },
            {
                "sku_label": "Apple iPhone 16 Pro (256GB, Desert Titanium)",
                "configuration": {"storage_gb": 256, "color": "Desert Titanium"},
            },
        ],
    },
    # --- Laptops ---
    {
        "category_key": "laptop",
        "family_name": "ThinkPad X1",
        "manufacturer": "Lenovo",
        "product_name": "Lenovo ThinkPad X1 Carbon Gen 12",
        "mpn": "21KC005VUS",
        "gtin": "197532000000",
        "generation": "Gen 12",
        "variants": [
            {
                "sku_label": "ThinkPad X1 Carbon Gen 12 (Core Ultra 7 155H, 32GB RAM, 1TB SSD)",
                "configuration": {
                    "processor": "Intel Core Ultra 7 155H",
                    "ram_gb": 32,
                    "storage_gb": 1024,
                },
            },
        ],
    },
    # --- External SSDs ---
    {
        "category_key": "external_ssd",
        "family_name": "Portable SSD T-Series",
        "manufacturer": "Samsung",
        "product_name": "Samsung T7 Shield Portable SSD",
        "mpn": "MU-PE1T0S",
        "gtin": "887276630000",
        "generation": "T7 Shield",
        "variants": [
            {
                "sku_label": "Samsung T7 Shield 1TB (USB 3.2 Gen 2, Black)",
                "configuration": {
                    "capacity_tb": 1,
                    "interface": "USB 3.2 Gen 2",
                    "color": "Black",
                },
            },
            {
                "sku_label": "Samsung T7 Shield 2TB (USB 3.2 Gen 2, Blue)",
                "configuration": {
                    "capacity_tb": 2,
                    "interface": "USB 3.2 Gen 2",
                    "color": "Blue",
                },
            },
        ],
    },
]


def seed_database(db: Session) -> dict[str, int]:
    """Execute idempotent seed operations on categories, families, products, and variants."""
    counts = {"categories": 0, "families": 0, "products": 0, "variants": 0}

    # 1. Categories
    category_map: dict[str, Category] = {}
    for cat_data in SEED_CATEGORIES:
        cat = db.execute(
            select(Category).where(Category.key == cat_data["key"])
        ).scalar_one_or_none()
        if not cat:
            cat = Category(
                key=cat_data["key"],
                name=cat_data["name"],
                schema_version=cat_data["schema_version"],
                spec_schema=cat_data["spec_schema"],
                status=cat_data["status"],
            )
            db.add(cat)
            db.flush()
            counts["categories"] += 1
        category_map[cat.key] = cat

    # 2. Families, Products, Variants
    for entry in SEED_CATALOG:
        cat = category_map[entry["category_key"]]

        # Family
        family = db.execute(
            select(ProductFamily).where(
                ProductFamily.category_id == cat.id,
                ProductFamily.name == entry["family_name"],
            )
        ).scalar_one_or_none()
        if not family:
            family = ProductFamily(
                category_id=cat.id,
                name=entry["family_name"],
                manufacturer=entry["manufacturer"],
            )
            db.add(family)
            db.flush()
            counts["families"] += 1

        # Product
        product = db.execute(
            select(Product).where(
                Product.category_id == cat.id,
                Product.name == entry["product_name"],
            )
        ).scalar_one_or_none()
        if not product:
            product = Product(
                category_id=cat.id,
                family_id=family.id,
                name=entry["product_name"],
                manufacturer=entry["manufacturer"],
                mpn=entry.get("mpn"),
                gtin=entry.get("gtin"),
                generation=entry.get("generation"),
                status="active",
            )
            db.add(product)
            db.flush()
            counts["products"] += 1

        # Variants
        for var_data in entry["variants"]:
            config = var_data["configuration"]
            config_hash = compute_config_hash(config)
            variant = db.execute(
                select(Variant).where(
                    Variant.product_id == product.id,
                    Variant.config_hash == config_hash,
                )
            ).scalar_one_or_none()
            if not variant:
                variant = Variant(
                    product_id=product.id,
                    configuration=config,
                    config_hash=config_hash,
                    sku_label=var_data["sku_label"],
                )
                db.add(variant)
                db.flush()
                counts["variants"] += 1

    db.commit()
    logger.info(
        "Seeding completed. New rows added: categories=%d, families=%d, products=%d, variants=%d",
        counts["categories"],
        counts["families"],
        counts["products"],
        counts["variants"],
    )
    return counts


if __name__ == "__main__":
    db = SessionLocal()
    try:
        res = seed_database(db)
        print(f"Seed successfully executed: {res}")
    finally:
        db.close()
