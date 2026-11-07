"""Catalog service orchestrating product search, listing, and detail retrieval."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.variant import Variant
from app.repositories.catalog_repository import CatalogRepository
from app.schemas.product import (
    ProductDetailResponse,
    ProductResponse,
    ProductSearchResult,
)
from app.schemas.variant import VariantResponse


class CatalogService:
    """Service providing business logic and schema transformation for catalog operations."""

    def __init__(self, repository: type[CatalogRepository] = CatalogRepository):
        self.repository = repository

    def _to_product_response(self, product: Product) -> ProductResponse:
        """Transform SQLAlchemy Product model to Pydantic ProductResponse."""
        category_key = product.category.key if product.category else "unknown"
        return ProductResponse(
            id=product.id,
            name=product.name,
            manufacturer=product.manufacturer,
            category=category_key,
            generation=product.generation,
            mpn=product.mpn,
        )

    def _to_variant_response(self, variant: Variant) -> VariantResponse:
        """Transform SQLAlchemy Variant model to Pydantic VariantResponse."""
        return VariantResponse(
            id=variant.id,
            product_id=variant.product_id,
            configuration=variant.configuration or {},
            label=variant.sku_label,
        )

    def search_products(
        self,
        db: Session,
        *,
        query: str | None = None,
        category: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ProductSearchResult:
        """List and search canonical products."""
        # Bounded pagination limit
        bounded_limit = max(1, min(limit, 100))

        # Validate category if explicitly provided
        if category:
            cat = self.repository.get_category_by_key(db, category)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Category '{category}' not found",
                )

        products, next_cursor = self.repository.list_products(
            db,
            category_key=category,
            search_query=query,
            limit=bounded_limit,
            cursor=cursor,
        )

        items = [self._to_product_response(p) for p in products]
        return ProductSearchResult(items=items, next_cursor=next_cursor)

    def get_product_detail(
        self, db: Session, product_id: uuid.UUID
    ) -> ProductDetailResponse:
        """Retrieve canonical product with all associated variants."""
        product = self.repository.get_product_by_id(db, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id '{product_id}' was not found",
            )

        product_resp = self._to_product_response(product)
        variants_resp = [self._to_variant_response(v) for v in product.variants]
        return ProductDetailResponse(product=product_resp, variants=variants_resp)
