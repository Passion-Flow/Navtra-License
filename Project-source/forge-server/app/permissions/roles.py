"""Role → permission mapping (rbac.md). Forge simplified 3-role model (b2b §11.1)."""

from __future__ import annotations

from app.permissions.registry import ALL_PERMISSIONS, P

# super_admin holds the wildcard; admin/auditor enumerate explicitly.
PLATFORM_ROLES: dict[str, set[str]] = {
    "super_admin": {"*"},
    "admin": {
        P.LICENSE_READ, P.LICENSE_ISSUE, P.LICENSE_UPDATE,
        P.PRODUCT_READ, P.PRODUCT_WRITE,
        P.CUSTOMER_READ, P.CUSTOMER_WRITE,
        P.CRL_GENERATE,
        # NOT: revoke/delete license, user mgmt, key mgmt, settings, audit
    },
    "auditor": {
        P.AUDIT_READ, P.AUDIT_EXPORT,
        P.LICENSE_READ,  # read-only license status
    },
}


def role_has(role: str, permission: str) -> bool:
    perms = PLATFORM_ROLES.get(role, set())
    return "*" in perms or permission in perms


def assert_registry_consistent() -> None:
    """Startup self-check: every permission listed in roles must exist in the registry."""
    for role, perms in PLATFORM_ROLES.items():
        for perm in perms:
            if perm != "*" and perm not in ALL_PERMISSIONS:
                raise RuntimeError(f"role '{role}' references unregistered permission '{perm}'")
