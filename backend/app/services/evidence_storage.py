"""Evidence storage service using SeaweedFS S3-compatible object storage.

Handles immutable evidence artifact persistence, SHA-256 verification,
and authorized retrieval.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.core.config import settings

logger = logging.getLogger("review_master.evidence_storage")


class StorageException(Exception):
    """Base exception for object storage operations."""


class StorageUnavailableError(StorageException):
    """Raised when the object storage service is unreachable."""


class EvidenceNotFoundError(StorageException):
    """Raised when requested evidence object does not exist in storage."""


class IntegrityMismatchError(StorageException):
    """Raised when retrieved evidence content does not match expected SHA-256."""


class EvidenceStorageService:
    """Service interfacing with SeaweedFS S3 API for immutable evidence storage."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ):
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.bucket_name = bucket_name or settings.S3_BUCKET_EVIDENCE
        self.access_key = access_key or settings.S3_ACCESS_KEY
        self.secret_key = secret_key or settings.S3_SECRET_KEY
        self.region = region or settings.S3_REGION

        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazily initialize boto3 S3 client."""
        if self._client is None:
            try:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
            except Exception as e:
                logger.error("Failed to initialize S3 client: %s", e)
                raise StorageUnavailableError(f"Could not initialize object storage: {e}") from e
        return self._client

    def ensure_bucket(self) -> None:
        """Ensure the target evidence bucket exists."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                try:
                    self.client.create_bucket(Bucket=self.bucket_name)
                    logger.info("Created object storage bucket '%s'", self.bucket_name)
                except Exception as ce:
                    raise StorageUnavailableError(f"Failed to create bucket '{self.bucket_name}': {ce}") from ce
            else:
                logger.warning("Bucket verification returned error %s: %s", error_code, e)

    def store_evidence(
        self,
        content_bytes: bytes,
        *,
        custom_key: str | None = None,
        content_type: str = "application/json",
    ) -> tuple[str, str, int]:
        """Store immutable evidence artifact and return (object_key, sha256_digest, byte_size).

        Raises:
            StorageUnavailableError: On network or S3 API failures.
        """
        if not content_bytes:
            raise StorageException("Evidence content bytes cannot be empty.")

        sha256_digest = hashlib.sha256(content_bytes).hexdigest()
        byte_size = len(content_bytes)

        if custom_key:
            object_key = custom_key
        else:
            now = datetime.now()
            object_key = f"extractions/{now.year}/{now.month:02d}/{sha256_digest}.json"

        # Ensure bucket exists
        self.ensure_bucket()

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=content_bytes,
                ContentType=content_type,
                Metadata={
                    "sha256": sha256_digest,
                    "byte_size": str(byte_size),
                },
            )
            logger.info("Stored evidence object '%s' (%d bytes, sha256=%s)", object_key, byte_size, sha256_digest)
            return (object_key, sha256_digest, byte_size)
        except Exception as e:
            logger.error("Failed to store evidence object '%s' in S3: %s", object_key, e)
            raise StorageUnavailableError(f"Evidence object storage failed: {e}") from e

    def retrieve_evidence(
        self,
        object_key: str,
        expected_sha256: str | None = None,
    ) -> tuple[bytes, str, str]:
        """Retrieve evidence artifact and return (content_bytes, content_type, sha256_digest).

        Raises:
            EvidenceNotFoundError: If object does not exist.
            IntegrityMismatchError: If retrieved bytes do not match expected_sha256.
            StorageUnavailableError: If storage service is unreachable.
        """
        try:
            resp = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            content_bytes = resp["Body"].read()
            content_type = resp.get("ContentType", "application/json")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise EvidenceNotFoundError(f"Evidence object '{object_key}' not found.") from e
            raise StorageUnavailableError(f"Failed to retrieve evidence from storage: {e}") from e
        except Exception as e:
            raise StorageUnavailableError(f"Storage communication error: {e}") from e

        actual_sha256 = hashlib.sha256(content_bytes).hexdigest()
        if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
            raise IntegrityMismatchError(
                f"Evidence integrity mismatch for '{object_key}'. "
                f"Expected {expected_sha256}, got {actual_sha256}."
            )

        return (content_bytes, content_type, actual_sha256)

    def object_exists(self, object_key: str) -> bool:
        """Check if an object exists in storage."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey"):
                return False
            return False
        except Exception:  # noqa: BLE001
            return False
