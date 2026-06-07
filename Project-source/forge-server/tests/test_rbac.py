"""Unit tests for the RBAC registry + role map."""

from app.permissions.registry import ALL_PERMISSIONS, P
from app.permissions.roles import PLATFORM_ROLES, assert_registry_consistent, role_has


def test_registry_is_consistent():
    assert_registry_consistent()  # raises if a role references an unknown permission


def test_super_admin_has_everything():
    assert role_has("super_admin", P.LICENSE_REVOKE)
    assert role_has("super_admin", P.KEY_MANAGE)


def test_admin_can_issue_but_not_revoke_or_manage_keys():
    assert role_has("admin", P.LICENSE_ISSUE)
    assert not role_has("admin", P.LICENSE_REVOKE)
    assert not role_has("admin", P.LICENSE_DELETE)
    assert not role_has("admin", P.KEY_MANAGE)
    assert not role_has("admin", P.AUDIT_READ)


def test_auditor_read_only():
    assert role_has("auditor", P.AUDIT_READ)
    assert role_has("auditor", P.LICENSE_READ)
    assert not role_has("auditor", P.LICENSE_ISSUE)
    assert not role_has("auditor", P.PRODUCT_WRITE)


def test_all_permissions_naming_convention():
    for perm in ALL_PERMISSIONS:
        parts = perm.split(".")
        assert len(parts) == 3, perm
        assert parts[0] in ("platform", "system"), perm
