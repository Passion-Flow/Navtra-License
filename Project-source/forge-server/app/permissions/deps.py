"""@require_perm dependency factory (rbac.md). Backend authority — never trust the UI."""

from __future__ import annotations

from fastapi import Depends

from app.api.deps import CurrentUser, get_current_user
from app.core.errors import BizError
from app.permissions.roles import role_has


def require_perm(permission: str):
    """Return a dependency that enforces `permission` for the current operator's role."""

    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "*" in user.permissions or permission in user.permissions:
            return user
        # Defence in depth: also verify against the authoritative role map, not just the
        # snapshot baked into the session.
        if role_has(user.role, permission):
            return user
        raise BizError("PERM_DENIED", {"required": permission})

    return _checker
