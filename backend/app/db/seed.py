"""Idempotent database seeding script for development and integration testing.

Populates categories (smartphones, laptops, external SSDs), marketplaces (Amazon India),
draft evaluation models, and reference catalog products/variants without inventing
fake evaluation scores, prices, or evidence.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.evaluation import EvaluationModel, EvaluationModelVersion
from app.models.identity import Role
from app.models.marketplace import Marketplace
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

SEED_MARKETPLACES: list[dict[str, Any]] = [
    {
        "key": "amazon.in",
        "name": "Amazon India",
        "adapter": "amazon_in_scraper_v1",
        "status": "active",
        "permitted_sources": {
            "allowed_domains": ["amazon.in", "www.amazon.in"],
            "category_scopes": ["smartphone"],
        },
    }
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

SMARTPHONE_EVAL_DEFINITION: dict[str, Any] = {
    "model": "smartphone",
    "version": "1-draft",
    "status": "draft",
    "quality_parameters": [
        {
            "key": "performance",
            "name": "Performance",
            "weight": 0.25,
            "critical": True,
            "inputs": ["chipset", "ram_gb", "storage_type", "benchmark_score"],
            "scoring_rule": {"type": "linear_range"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
        {
            "key": "battery_charging",
            "name": "Battery and charging",
            "weight": 0.20,
            "critical": True,
            "inputs": [
                "battery_capacity_mah",
                "charging_wattage",
                "tested_battery_life_hours",
            ],
            "scoring_rule": {"type": "linear_range"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
        {
            "key": "camera",
            "name": "Camera",
            "weight": 0.20,
            "critical": True,
            "inputs": ["main_sensor_mp", "camera_test_score"],
            "scoring_rule": {"type": "linear_range"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
        {
            "key": "display",
            "name": "Display",
            "weight": 0.15,
            "critical": False,
            "inputs": ["panel_type", "display_size_inches", "refresh_rate_hz"],
            "scoring_rule": {"type": "piecewise"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
        {
            "key": "software_updates",
            "name": "Software and updates",
            "weight": 0.10,
            "critical": False,
            "inputs": ["operating_system"],
            "scoring_rule": {"type": "ordinal"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
        {
            "key": "connectivity_features",
            "name": "Connectivity and features",
            "weight": 0.10,
            "critical": False,
            "inputs": ["supports_5g"],
            "scoring_rule": {"type": "ordinal"},
            "evidence_requirements": {"min_trust_tier_to_score": 2},
        },
    ],
}


SEED_ROLES: list[dict[str, str]] = [
    {
        "name": "admin",
        "description": "System Administrator with full access",
    },
    {
        "name": "expert_reviewer",
        "description": "Expert reviewer with evaluation and evidence authoring capabilities",
    },
    {
        "name": "public_reviewer",
        "description": "Verified public reviewer capable of submitting reviews and evidence",
    },
    {
        "name": "consumer",
        "description": "Default consumer user role for browsing, comparing, and reading reviews",
    },
    {
        "name": "api_consumer",
        "description": "Programmatic API consumer for data ingestion and integration",
    },
]


def seed_database(db: Session) -> dict[str, int]:
    """Execute idempotent seed operations on categories, families, products, variants, and marketplaces."""
    counts = {
        "roles": 0,
        "categories": 0,
        "marketplaces": 0,
        "families": 0,
        "products": 0,
        "variants": 0,
        "evaluation_models": 0,
    }

    # 0. Roles
    for role_data in SEED_ROLES:
        existing_role = db.execute(
            select(Role).where(Role.name == role_data["name"])
        ).scalar_one_or_none()
        if not existing_role:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
            )
            db.add(role)
            db.flush()
            counts["roles"] += 1

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

    # 2. Marketplaces
    for mkt_data in SEED_MARKETPLACES:
        mkt = db.execute(
            select(Marketplace).where(Marketplace.key == mkt_data["key"])
        ).scalar_one_or_none()
        if not mkt:
            mkt = Marketplace(
                key=mkt_data["key"],
                name=mkt_data["name"],
                adapter=mkt_data["adapter"],
                status=mkt_data["status"],
                permitted_sources=mkt_data["permitted_sources"],
            )
            db.add(mkt)
            db.flush()
            counts["marketplaces"] += 1

    # 3. Families, Products, Variants
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

    # 4. Evaluation model for smartphone
    phone_cat = category_map.get("smartphone")
    if phone_cat:
        eval_model = db.execute(
            select(EvaluationModel).where(
                EvaluationModel.category_id == phone_cat.id,
                EvaluationModel.name == "smartphone",
            )
        ).scalar_one_or_none()
        if not eval_model:
            eval_model = EvaluationModel(
                category_id=phone_cat.id,
                name="smartphone",
            )
            db.add(eval_model)
            db.flush()
            counts["evaluation_models"] += 1

        model_version = db.execute(
            select(EvaluationModelVersion).where(
                EvaluationModelVersion.model_id == eval_model.id,
                EvaluationModelVersion.version == "1-draft",
            )
        ).scalar_one_or_none()
        if not model_version:
            model_version = EvaluationModelVersion(
                model_id=eval_model.id,
                version="1-draft",
                status="draft",
                definition=SMARTPHONE_EVAL_DEFINITION,
            )
            db.add(model_version)
            db.flush()

    # 5. Core attribute definitions & variant attribute values
    from app.repositories.attribute_repository import AttributeRepository

    CORE_ATTRIBUTES: list[dict[str, Any]] = [
        {"key": "ram", "name": "RAM", "data_type": "numeric", "unit": "GB", "canonical_unit": "GB", "validation_rules": {"min": 1, "max": 128}, "is_required": True, "is_filterable": True, "is_searchable": True},
        {"key": "storage", "name": "Storage", "data_type": "numeric", "unit": "GB", "canonical_unit": "GB", "validation_rules": {"min": 16, "max": 4096}, "is_required": True, "is_filterable": True, "is_searchable": True},
        {"key": "display_size", "name": "Display Size", "data_type": "numeric", "unit": "inch", "canonical_unit": "inch", "validation_rules": {"min": 4.0, "max": 12.0}, "is_required": False, "is_filterable": True, "is_searchable": False},
        {"key": "battery", "name": "Battery Capacity", "data_type": "numeric", "unit": "mAh", "canonical_unit": "mAh", "validation_rules": {"min": 1000, "max": 10000}, "is_required": False, "is_filterable": True, "is_searchable": False},
        {"key": "color", "name": "Color", "data_type": "string", "unit": None, "canonical_unit": None, "validation_rules": {}, "is_required": False, "is_filterable": True, "is_searchable": True},
    ]

    attr_map = {}
    for attr_spec in CORE_ATTRIBUTES:
        existing_attr = AttributeRepository.get_definition_by_key(db, attr_spec["key"])
        if not existing_attr:
            existing_attr = AttributeRepository.create_definition(
                db,
                key=attr_spec["key"],
                name=attr_spec["name"],
                category_id=phone_cat.id if phone_cat else None,
                data_type=attr_spec["data_type"],
                unit=attr_spec["unit"],
                canonical_unit=attr_spec["canonical_unit"],
                validation_rules=attr_spec["validation_rules"],
                is_required=attr_spec["is_required"],
                is_filterable=attr_spec["is_filterable"],
                is_searchable=attr_spec["is_searchable"],
            )
        attr_map[attr_spec["key"]] = existing_attr

    # Populate variant attribute values from configuration dictionaries
    all_variants = db.execute(select(Variant)).scalars().all()
    for var in all_variants:
        cfg = var.configuration or {}
        if "ram_gb" in cfg and "ram" in attr_map:
            AttributeRepository.set_variant_value(
                db,
                variant_id=var.id,
                attribute_id=attr_map["ram"].id,
                value_numeric=cfg["ram_gb"],
                original_unit="GB",
                canonical_unit="GB",
            )
        if "storage_gb" in cfg and "storage" in attr_map:
            AttributeRepository.set_variant_value(
                db,
                variant_id=var.id,
                attribute_id=attr_map["storage"].id,
                value_numeric=cfg["storage_gb"],
                original_unit="GB",
                canonical_unit="GB",
            )
        if "color" in cfg and "color" in attr_map:
            AttributeRepository.set_variant_value(
                db,
                variant_id=var.id,
                attribute_id=attr_map["color"].id,
                value_text=str(cfg["color"]),
            )

    db.commit()
    logger.info(
        "Seeding completed. New rows added: roles=%d, categories=%d, marketplaces=%d, families=%d, products=%d, variants=%d, models=%d",
        counts["roles"],
        counts["categories"],
        counts["marketplaces"],
        counts["families"],
        counts["products"],
        counts["variants"],
        counts["evaluation_models"],
    )
    return counts


if __name__ == "__main__":
    db = SessionLocal()
    try:
        res = seed_database(db)
        print(f"Seed successfully executed: {res}")
    finally:
        db.close()
