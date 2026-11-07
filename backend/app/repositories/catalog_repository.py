"""Catalog database repository executing optimized queries on products, variants, and categories."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.category import Category
from app.models.product import Product


class CatalogRepository:
    """Repository handling all catalog SQL persistence and retrieval operations."""

    @staticmethod
    def get_category_by_key(db: Session, key: str) -> Category | None:
        """Find category by unique key identifier."""
        return db.execute(
            select(Category).where(Category.key == key)
        ).scalar_one_or_none()

    @staticmethod
    def list_products(
        db: Session,
        *,
        category_key: str | None = None,
        search_query: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Product], str | None]:
        """Query canonical products with optional category filtering, deterministic search, and cursor pagination."""
        query = (
            select(Product)
            .join(Product.category)
            .options(joinedload(Product.category))
            .where(Product.status == "active")
        )

        # Category filter
        if category_key:
            query = query.where(Category.key == category_key)

        # Search query matching product name or manufacturer
        if search_query and search_query.strip():
            tokens = search_query.strip().split()
            for token in tokens:
                pattern = f"%{token}%"
                query = query.where(
                    or_(
                        Product.name.ilike(pattern),
                        Product.manufacturer.ilike(pattern),
                        Product.mpn.ilike(pattern),
                    )
                )

        # Deterministic ordering for pagination
        query = query.order_by(Product.name.asc(), Product.id.asc())

        # Cursor pagination (based on offset-compatible or ID sequence)
        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
                # Find the reference product to paginate after
                ref_product = db.get(Product, cursor_uuid)
                if ref_product:
                    query = query.where(
                        or_(
                            Product.name > ref_product.name,
                            (Product.name == ref_product.name)
                            & (Product.id > ref_product.id),
                        )
                    )
            except (ValueError, TypeError):
                # Ignore invalid cursor format and start from beginning
                pass

        # Fetch limit + 1 to determine if next page exists
        items = list(db.execute(query.limit(limit + 1)).scalars().all())

        next_cursor = None
        if len(items) > limit:
            items = items[:limit]
            next_cursor = str(items[-1].id)

        return items, next_cursor

    @staticmethod
    def get_product_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
        """Retrieve canonical product with variants and category eagerly loaded."""
        stmt = (
            select(Product)
            .where(Product.id == product_id, Product.status == "active")
            .options(
                joinedload(Product.category),
                selectinload(Product.variants),
            )
        )
        return db.execute(stmt).scalar_one_or_none()
