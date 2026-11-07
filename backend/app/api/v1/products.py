"""Product catalog endpoints for searching and retrieving canonical products."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.product import ProductDetailResponse, ProductSearchResult
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/products", tags=["Products"])
catalog_service = CatalogService()


@router.get(
    "",
    response_model=ProductSearchResult,
    status_code=status.HTTP_200_OK,
    summary="Search canonical products",
    description="Retrieve canonical products with optional category filtering and keyword search.",
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[
        str | None,
        Query(description="Search keyword matching product name or manufacturer"),
    ] = None,
    category: Annotated[
        str | None,
        Query(description="Category filter key: smartphone, laptop, external_ssd"),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum number of items to return")
    ] = 50,
    cursor: Annotated[
        str | None, Query(description="Opaque pagination cursor from previous page")
    ] = None,
) -> ProductSearchResult:
    """Retrieve canonical products matching query filters."""
    return catalog_service.search_products(
        db,
        query=q,
        category=category,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get canonical product with variants",
    description="Retrieve a canonical product and all of its hardware configuration variants.",
)
def get_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ProductDetailResponse:
    """Retrieve canonical product detail and associated variants."""
    return catalog_service.get_product_detail(db, product_id)
