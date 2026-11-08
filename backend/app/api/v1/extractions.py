"""API routes for ingesting and inspecting marketplace extraction snapshots."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.db.dependencies import get_db
from app.models.extraction import ExtractionRecord
from app.schemas.contract_validator import ContractValidationError
from app.schemas.extraction import (
    ExtractionIngestionResponse,
    SmartphoneExtractionPayload,
)
from app.services.ingestion_service import IngestionService

logger = logging.getLogger("review_master.api.extractions")

router = APIRouter(prefix="/extractions", tags=["Extractions"])
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2 Megabytes


@router.post(
    "/smartphones",
    response_model=ExtractionIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit user-initiated Amazon India smartphone extraction",
    description="Validates snapshot against frozen JSON Schema Draft 2020-12, upserts listing, resolves canonical product and persists evidence.",
)
async def submit_smartphone_extraction(
    payload: SmartphoneExtractionPayload,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional unique idempotency key to prevent duplicate processing",
        ),
    ] = None,
) -> ExtractionIngestionResponse:
    """Ingest user-initiated Amazon India smartphone extraction."""
    # Enforce request payload size limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Extraction payload exceeds maximum allowed size of {MAX_PAYLOAD_BYTES} bytes.",
        )

    ingestion_service = IngestionService(db)

    try:
        (
            rec,
            listing,
            resolution,
            evidence_count,
            created,
        ) = ingestion_service.ingest_smartphone_extraction(
            payload, idempotency_key=idempotency_key
        )
    except ContractValidationError as err:
        logger.warning("Contract validation failed: %s", err.errors)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Payload violated frozen smartphone extraction contract.",
                "errors": err.errors,
            },
        )

    if not created:
        response.status_code = status.HTTP_200_OK

    return ExtractionIngestionResponse(
        status="success" if resolution.match_state == "confirmed" else "needs_review",
        record_id=rec.record_id,
        listing_id=listing.id,
        asin=rec.asin,
        match_state=resolution.match_state,
        product_id=resolution.product_id,
        variant_id=resolution.variant_id,
        product_name=resolution.product_name,
        variant_label=resolution.variant_label,
        evidence_count=evidence_count,
        created=created,
        message="Extraction snapshot successfully ingested and processed.",
    )


@router.get(
    "/{record_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve extraction snapshot by record ID",
    description="Returns the stored raw, normalized, and validation payload of an extraction.",
)
def get_extraction_record(
    record_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict:
    """Retrieve extraction snapshot record."""
    rec = db.execute(
        select(ExtractionRecord).where(ExtractionRecord.record_id == record_id)
    ).scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction record '{record_id}' not found.",
        )

    return {
        "record_id": rec.record_id,
        "schema_version": rec.schema_version,
        "asin": rec.asin,
        "product_url": rec.product_url,
        "extraction_method": rec.extraction_method,
        "extension_version": rec.extension_version,
        "status": rec.status,
        "raw_payload": rec.raw_payload,
        "normalized_payload": rec.normalized_payload,
        "validation_payload": rec.validation_payload,
        "storage_object_key": rec.storage_object_key,
        "extracted_at": rec.extracted_at,
    }
