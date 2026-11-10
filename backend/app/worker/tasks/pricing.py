"""Background tasks for price refresh, seller offer tracking, and history persistence."""

import logging
import uuid
from decimal import Decimal
from typing import Any

from celery import Celery, Task  # type: ignore[import-untyped]
from sqlalchemy import select

import app.worker.celery_app as ca
from app.db.base import utc_now
from app.models.listing import MarketplaceListing
from app.models.offer import PriceRecord, SellerOffer
from app.worker.services.job_service import DurableJobService

logger = logging.getLogger("review_master.tasks.pricing")


def register_pricing_tasks(celery_app: Celery) -> None:
    """Register commercial price refresh and offer tracking tasks."""

    @celery_app.task(
        bind=True,
        name="price.refresh",
        max_retries=3,
        default_retry_delay=5,
    )
    def refresh_price(
        self: Task,
        listing_id_str: str | None = None,
        new_price: float | None = None,
        currency: str = "INR",
        seller: str | None = None,
        job_id_str: str | None = None,
    ) -> dict[str, Any]:
        """Refresh seller offer and append to historical price records."""
        job_id = uuid.UUID(job_id_str) if job_id_str else None
        db = ca.SessionLocal()
        try:
            job_service = DurableJobService(db)
            if job_id:
                job_service.start_job(job_id, worker_id=getattr(self.request, "hostname", None))
                db.commit()

            refreshed_count = 0
            now = utc_now()

            if listing_id_str:
                listing_id = uuid.UUID(listing_id_str)
                listing = db.get(MarketplaceListing, listing_id)
                if listing:
                    dec_price = Decimal(str(new_price)) if new_price is not None else None
                    # 1. Update or create current SellerOffer
                    offer = db.execute(
                        select(SellerOffer).where(SellerOffer.listing_id == listing_id)
                    ).scalar_one_or_none()
                    if not offer:
                        offer = SellerOffer(
                            listing_id=listing_id,
                            seller=seller or "Default Seller",
                            current_price=dec_price,
                            currency=currency,
                            observed_at=now,
                            source="background_price_refresh",
                            provenance={"task": "price.refresh"},
                        )
                        db.add(offer)
                        db.flush()
                    else:
                        if dec_price is not None:
                            offer.current_price = dec_price
                        if seller:
                            offer.seller = seller
                        offer.observed_at = now

                    # 2. Append to immutable PriceRecord
                    if dec_price is not None:
                        price_rec = PriceRecord(
                            offer_id=offer.id,
                            price=dec_price,
                            currency=currency,
                            observed_at=now,
                            source="background_price_refresh",
                            provenance={"task": "price.refresh"},
                        )
                        db.add(price_rec)

                    refreshed_count = 1
            else:
                # Scheduled sweep: touch active listings to ensure offer consistency
                listings = db.execute(select(MarketplaceListing).limit(50)).scalars().all()
                for lst in listings:
                    offer = db.execute(
                        select(SellerOffer).where(SellerOffer.listing_id == lst.id)
                    ).scalar_one_or_none()
                    if offer:
                        offer.observed_at = now
                        refreshed_count += 1

            db.commit()
            result_payload = {
                "refreshed_count": refreshed_count,
                "status": "completed",
            }

            if job_id:
                job_service.complete_job(job_id, result_payload=result_payload)
                db.commit()

            return result_payload

        except Exception as exc:
            from celery.exceptions import Retry  # type: ignore[import-untyped]

            if isinstance(exc, Retry):
                raise
            logger.error("Error refreshing prices: %s", exc)
            if job_id:
                job_service.fail_job(job_id, error_message=str(exc))
                db.commit()
            raise
        finally:
            db.close()
