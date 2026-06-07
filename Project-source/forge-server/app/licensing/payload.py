"""License validity terms + payload assembly."""

from __future__ import annotations

import datetime

from dateutil.relativedelta import relativedelta

from app.core.errors import BizError
from app.settings import get_settings

# term_preset -> relativedelta offset (perpetual handled separately).
_TERMS: dict[str, relativedelta] = {
    "1m": relativedelta(months=1),
    "3m": relativedelta(months=3),
    "6m": relativedelta(months=6),
    "1y": relativedelta(years=1),
    "3y": relativedelta(years=3),
    "5y": relativedelta(years=5),
}


def compute_active_until(
    term_preset: str, active_from: datetime.datetime, mode: str
) -> datetime.datetime | None:
    """Resolve active_until from the term preset.

    perpetual: online -> None (truly unlimited, server-revocable); offline -> +99y backstop
    (every offline envelope keeps an expiry so CRL isn't the only recall). See PRD §5.
    """
    if term_preset == "perpetual":
        if mode == "online":
            return None
        return active_from + relativedelta(years=get_settings().OFFLINE_PERPETUAL_YEARS)
    if term_preset not in _TERMS:
        raise BizError("ISSUE_INVALID_TERM", {"term_preset": term_preset})
    return active_from + _TERMS[term_preset]


def build_payload(*, license_obj, customer, product, issuer_key_id: str) -> dict:
    """Assemble the canonical license payload that gets signed into a `.forge` file."""
    lic = license_obj
    return {
        "version": 1,
        "license_id": str(lic.license_id),
        "cluster_id": lic.cluster_id,
        "customer": customer.name,
        "product": product.slug,
        "active_from": lic.active_from.astimezone(datetime.timezone.utc).isoformat(),
        "active_until": (
            lic.active_until.astimezone(datetime.timezone.utc).isoformat()
            if lic.active_until else None
        ),
        "subscription": lic.subscription,
        "quotas": lic.quotas,
        "features": lic.features,
        "mode": lic.mode,
        "scope": lic.scope,
        "binding": lic.binding,
        "bound_fingerprint": lic.bound_fingerprint,
        "alg": lic.alg,
        "issuer": issuer_key_id,
        "issued_at": lic.issued_at.astimezone(datetime.timezone.utc).isoformat(),
    }
