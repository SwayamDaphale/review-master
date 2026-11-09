"""Marketplace and page-type registry with URL security validation.

Enforces allowed marketplaces, page types, and strict domain validation
to prevent SSRF, deceptive hostnames, and arbitrary URL ingestion.
"""

import re
from typing import ClassVar
from urllib.parse import urlparse

from app.contracts.extraction.base import ContractValidationError


class MarketplaceRegistry:
    """Central registry defining supported marketplaces, page types, and URL policies."""

    SUPPORTED_MARKETPLACES: ClassVar[set[str]] = {"amazon.in"}
    SUPPORTED_PAGE_TYPES: ClassVar[set[str]] = {"product_detail"}

    # Allowed domains strictly anchored
    ALLOWED_DOMAINS: ClassVar[dict[str, set[str]]] = {
        "amazon.in": {"www.amazon.in", "amazon.in"},
    }

    # Allowed path patterns for product detail pages
    PRODUCT_PATH_PATTERNS: ClassVar[dict[str, list[re.Pattern]]] = {
        "amazon.in": [
            re.compile(r"^/dp/[A-Z0-9]{10}(?:/.*)?$", re.IGNORECASE),
            re.compile(r"^/gp/product/[A-Z0-9]{10}(?:/.*)?$", re.IGNORECASE),
            re.compile(r"^/.+/dp/[A-Z0-9]{10}(?:/.*)?$", re.IGNORECASE),
        ],
    }

    @classmethod
    def validate_marketplace(cls, marketplace: str | None) -> str:
        """Validate that marketplace identifier is supported."""
        if not marketplace or marketplace not in cls.SUPPORTED_MARKETPLACES:
            raise ContractValidationError(
                f"Unsupported marketplace '{marketplace}'. Supported: {sorted(cls.SUPPORTED_MARKETPLACES)}",
                errors=[{
                    "loc": ["source", "marketplace"],
                    "code": "unsupported_marketplace",
                    "msg": f"Marketplace '{marketplace}' is not supported. Supported: {sorted(cls.SUPPORTED_MARKETPLACES)}",
                }],
            )
        return marketplace

    @classmethod
    def validate_page_type(cls, page_type: str | None) -> str:
        """Validate that page type is supported."""
        if not page_type or page_type not in cls.SUPPORTED_PAGE_TYPES:
            raise ContractValidationError(
                f"Unsupported page type '{page_type}'. Supported: {sorted(cls.SUPPORTED_PAGE_TYPES)}",
                errors=[{
                    "loc": ["source", "page_type"],
                    "code": "unsupported_page_type",
                    "msg": f"Page type '{page_type}' is not supported. Supported: {sorted(cls.SUPPORTED_PAGE_TYPES)}",
                }],
            )
        return page_type

    @classmethod
    def validate_product_url(cls, url: str | None, marketplace: str = "amazon.in") -> str:
        """Strictly validate product URL for scheme, hostname, credentials, and path structure."""
        if not url:
            raise ContractValidationError(
                "Product URL is required.",
                errors=[{"loc": ["source", "product_url"], "code": "missing_url", "msg": "Product URL cannot be empty."}],
            )

        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ContractValidationError(
                f"Malformed product URL: {e}",
                errors=[{"loc": ["source", "product_url"], "code": "malformed_url", "msg": "Could not parse product URL."}],
            ) from e

        # 1. Enforce HTTPS only
        if parsed.scheme.lower() != "https":
            raise ContractValidationError(
                f"Insecure or invalid URL scheme '{parsed.scheme}'. Only 'https' is permitted.",
                errors=[{"loc": ["source", "product_url"], "code": "invalid_scheme", "msg": "Only HTTPS URLs are allowed."}],
            )

        # 2. Reject credentials in URL (user:pass@host)
        if parsed.username or parsed.password:
            raise ContractValidationError(
                "URLs containing embedded credentials are forbidden.",
                errors=[{"loc": ["source", "product_url"], "code": "credentials_in_url", "msg": "Credentials in URL are strictly forbidden."}],
            )

        # 3. Validate exact hostname against allowlist
        hostname = (parsed.hostname or "").lower()
        allowed_hosts = cls.ALLOWED_DOMAINS.get(marketplace, set())
        if hostname not in allowed_hosts:
            raise ContractValidationError(
                f"Hostname '{hostname}' does not match allowed domains for marketplace '{marketplace}': {sorted(allowed_hosts)}",
                errors=[{"loc": ["source", "product_url"], "code": "invalid_domain", "msg": f"Domain '{hostname}' is not authorized for {marketplace}."}],
            )

        # 4. Reject non-standard ports
        if parsed.port and parsed.port not in (443,):
            raise ContractValidationError(
                f"Non-standard port '{parsed.port}' is not permitted.",
                errors=[{"loc": ["source", "product_url"], "code": "invalid_port", "msg": "Custom port numbers are forbidden."}],
            )

        # 5. Validate path pattern
        patterns = cls.PRODUCT_PATH_PATTERNS.get(marketplace, [])
        path = parsed.path
        if patterns and not any(p.match(path) for p in patterns):
            raise ContractValidationError(
                f"URL path '{path}' does not match supported product listing patterns for {marketplace}.",
                errors=[{"loc": ["source", "product_url"], "code": "invalid_product_path", "msg": "URL does not point to a valid single product listing page."}],
            )

        return url

    @classmethod
    def validate_ingestion_scope(
        cls,
        marketplace: str | None,
        page_type: str | None,
        product_url: str | None,
    ) -> None:
        """Validate marketplace, page type, and URL together."""
        valid_mkt = cls.validate_marketplace(marketplace)
        cls.validate_page_type(page_type)
        cls.validate_product_url(product_url, marketplace=valid_mkt)
