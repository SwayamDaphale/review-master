"""Role-Based Access Control (RBAC) permission definitions and mappings."""

from enum import Enum


class Permission(str, Enum):
    """Fine-grained system permissions."""

    # Catalog
    CATALOG_READ = "catalog:read"
    CATALOG_MANAGE = "catalog:manage"

    # Comparison
    COMPARISON_READ = "comparison:read"
    COMPARISON_WRITE = "comparison:write"

    # Ingestion / Extractions
    INGESTION_SUBMIT = "ingestion:submit"
    INGESTION_READ = "ingestion:read"

    # Evidence
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_MANAGE = "evidence:manage"

    # Evaluations
    EVALUATION_READ = "evaluation:read"
    EVALUATION_MANAGE = "evaluation:manage"

    # Users & Administration
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    ROLES_MANAGE = "roles:manage"
    AUDIT_READ = "audit:read"


class RoleName(str, Enum):
    """Canonical system roles."""

    ADMIN = "admin"
    EXPERT_REVIEWER = "expert_reviewer"
    PUBLIC_REVIEWER = "public_reviewer"
    CONSUMER = "consumer"
    API_CONSUMER = "api_consumer"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    RoleName.ADMIN: {
        Permission.CATALOG_READ,
        Permission.CATALOG_MANAGE,
        Permission.COMPARISON_READ,
        Permission.COMPARISON_WRITE,
        Permission.INGESTION_SUBMIT,
        Permission.INGESTION_READ,
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_MANAGE,
        Permission.EVALUATION_READ,
        Permission.EVALUATION_MANAGE,
        Permission.USERS_READ,
        Permission.USERS_MANAGE,
        Permission.ROLES_MANAGE,
        Permission.AUDIT_READ,
    },
    RoleName.EXPERT_REVIEWER: {
        Permission.CATALOG_READ,
        Permission.COMPARISON_READ,
        Permission.COMPARISON_WRITE,
        Permission.INGESTION_SUBMIT,
        Permission.INGESTION_READ,
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_MANAGE,
        Permission.EVALUATION_READ,
        Permission.EVALUATION_MANAGE,
    },
    RoleName.PUBLIC_REVIEWER: {
        Permission.CATALOG_READ,
        Permission.COMPARISON_READ,
        Permission.COMPARISON_WRITE,
        Permission.INGESTION_SUBMIT,
        Permission.INGESTION_READ,
        Permission.EVIDENCE_READ,
        Permission.EVALUATION_READ,
    },
    RoleName.CONSUMER: {
        Permission.CATALOG_READ,
        Permission.COMPARISON_READ,
        Permission.COMPARISON_WRITE,
        Permission.EVIDENCE_READ,
        Permission.EVALUATION_READ,
    },
    RoleName.API_CONSUMER: {
        Permission.CATALOG_READ,
        Permission.INGESTION_SUBMIT,
        Permission.INGESTION_READ,
        Permission.EVIDENCE_READ,
        Permission.EVALUATION_READ,
    },
}


def get_permissions_for_roles(roles: list[str]) -> set[str]:
    """Resolve aggregate effective permissions for a set of assigned roles."""
    effective: set[str] = set()
    for role in roles:
        effective.update(ROLE_PERMISSIONS.get(role, set()))
    return effective

