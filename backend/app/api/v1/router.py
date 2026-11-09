"""API version 1 root router assembling all v1 modular domain routers."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.comparisons import router as comparisons_router
from app.api.v1.corrections import router as corrections_router
from app.api.v1.evaluations import router as evaluations_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.listings import router as listings_router
from app.api.v1.products import router as products_router
from app.api.v1.reviews import router as reviews_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(comparisons_router)
api_v1_router.include_router(products_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(corrections_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(extractions_router)
api_v1_router.include_router(ingestion_router)
api_v1_router.include_router(listings_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(evaluations_router)
