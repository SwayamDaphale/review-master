"""Catalog specification search service."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.attribute import VariantAttributeValue
from app.models.category import Category
from app.models.product import Product
from app.models.variant import Variant


@dataclass
class SearchFilters:
    """Specification filter parameters for product & variant search."""

    category_key: str | None = None
    brand: str | None = None
    query: str | None = None
    min_ram_gb: Decimal | float | None = None
    max_ram_gb: Decimal | float | None = None
    min_storage_gb: Decimal | float | None = None
    max_storage_gb: Decimal | float | None = None
    min_display_inch: Decimal | float | None = None
    max_display_inch: Decimal | float | None = None
    limit: int = 50
    offset: int = 0


@dataclass
class SearchResultItem:
    """Search result item containing product and matching variants."""

    product_id: uuid.UUID
    product_name: str
    manufacturer: str
    category_key: str
    generation: str | None
    variants: list[dict[str, Any]] = field(default_factory=list)


class CatalogSearchService:
    """Service executing specification-aware catalog search on PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def search(self, filters: SearchFilters) -> tuple[list[SearchResultItem], int]:
        """Search products and variants matching criteria."""
        stmt = (
            select(Product)
            .join(Product.category)
            .options(
                joinedload(Product.category),
                selectinload(Product.variants)
                .selectinload(Variant.attribute_values)
                .joinedload(VariantAttributeValue.attribute_definition),
            )
            .where(Product.status == "active")
        )

        if filters.category_key:
            stmt = stmt.where(Category.key == filters.category_key)

        if filters.brand and filters.brand.strip():
            stmt = stmt.where(Product.manufacturer.ilike(f"%{filters.brand.strip()}%"))

        if filters.query and filters.query.strip():
            tokens = filters.query.strip().split()
            for token in tokens:
                pattern = f"%{token}%"
                stmt = stmt.where(
                    or_(
                        Product.name.ilike(pattern),
                        Product.manufacturer.ilike(pattern),
                        Product.mpn.ilike(pattern),
                    )
                )

        # Ordering
        stmt = stmt.order_by(Product.name.asc(), Product.id.asc())

        # Retrieve candidate products
        candidates = list(self.db.execute(stmt).scalars().unique().all())

        results: list[SearchResultItem] = []
        for prod in candidates:
            matching_variants: list[dict[str, Any]] = []

            for var in prod.variants:
                if not self._variant_matches_spec_filters(var, filters):
                    continue

                matching_variants.append(
                    {
                        "id": str(var.id),
                        "sku_label": var.sku_label,
                        "configuration": var.configuration,
                        "config_hash": var.config_hash,
                        "attributes": {
                            vav.attribute_definition.key: {
                                "value": vav.value_numeric
                                if vav.value_numeric is not None
                                else vav.value_text,
                                "unit": vav.canonical_unit
                                or vav.attribute_definition.canonical_unit,
                            }
                            for vav in var.attribute_values
                            if vav.attribute_definition
                        },
                    }
                )

            # Include product if it has matching variants (or if no variant-specific filters were requested)
            has_var_filters = any(
                [
                    filters.min_ram_gb is not None,
                    filters.max_ram_gb is not None,
                    filters.min_storage_gb is not None,
                    filters.max_storage_gb is not None,
                    filters.min_display_inch is not None,
                    filters.max_display_inch is not None,
                ]
            )

            if (has_var_filters and matching_variants) or not has_var_filters:
                results.append(
                    SearchResultItem(
                        product_id=prod.id,
                        product_name=prod.name,
                        manufacturer=prod.manufacturer,
                        category_key=prod.category.key if prod.category else "unknown",
                        generation=prod.generation,
                        variants=matching_variants
                        if has_var_filters
                        else [
                            {
                                "id": str(v.id),
                                "sku_label": v.sku_label,
                                "configuration": v.configuration,
                            }
                            for v in prod.variants
                        ],
                    )
                )

        total_count = len(results)
        paginated = results[filters.offset : filters.offset + filters.limit]
        return paginated, total_count

    def _variant_matches_spec_filters(
        self, variant: Variant, filters: SearchFilters
    ) -> bool:
        """Evaluate if variant satisfies numeric specification bounds without converting null to 0."""
        attr_dict: dict[str, Decimal] = {}
        for vav in variant.attribute_values:
            if vav.attribute_definition and vav.value_numeric is not None:
                attr_dict[vav.attribute_definition.key] = vav.value_numeric

        # Also inspect variant configuration json for RAM/storage fallbacks
        cfg = variant.configuration or {}

        # 1. RAM filter
        ram_val = attr_dict.get("ram") or (
            Decimal(str(cfg["ram_gb"]))
            if "ram_gb" in cfg and cfg["ram_gb"] is not None
            else None
        )
        if filters.min_ram_gb is not None and (
            ram_val is None or ram_val < Decimal(str(filters.min_ram_gb))
        ):
            return False
        if filters.max_ram_gb is not None and (
            ram_val is None or ram_val > Decimal(str(filters.max_ram_gb))
        ):
            return False

        # 2. Storage filter
        storage_val = attr_dict.get("storage") or (
            Decimal(str(cfg["storage_gb"]))
            if "storage_gb" in cfg and cfg["storage_gb"] is not None
            else None
        )
        if filters.min_storage_gb is not None and (
            storage_val is None or storage_val < Decimal(str(filters.min_storage_gb))
        ):
            return False
        if filters.max_storage_gb is not None and (
            storage_val is None or storage_val > Decimal(str(filters.max_storage_gb))
        ):
            return False

        # 3. Display size filter
        display_val = attr_dict.get("display_size") or (
            Decimal(str(cfg["display_size_inches"]))
            if "display_size_inches" in cfg and cfg["display_size_inches"] is not None
            else None
        )
        if filters.min_display_inch is not None and (
            display_val is None or display_val < Decimal(str(filters.min_display_inch))
        ):
            return False
        return not (
            filters.max_display_inch is not None
            and (
                display_val is None
                or display_val > Decimal(str(filters.max_display_inch))
            )
        )
