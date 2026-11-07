"""API version 1 root router assembling all v1 modular domain routers."""

from fastapi import APIRouter

from app.api.v1.products import router as products_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(products_router)
