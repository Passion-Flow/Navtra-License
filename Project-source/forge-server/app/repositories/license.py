"""Product / Customer / License / Revocation repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.customer import Customer
from app.models.license import License
from app.models.product import Product
from app.models.revocation import Revocation
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug, Product.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()


class CustomerRepository(BaseRepository[Customer]):
    model = Customer


class LicenseRepository(BaseRepository[License]):
    model = License

    async def get_by_online_code(self, code: str) -> License | None:
        stmt = select(License).where(License.online_code == code, License.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()


class RevocationRepository(BaseRepository[Revocation]):
    model = Revocation

    async def get_by_license(self, license_id) -> Revocation | None:  # noqa: ANN001
        stmt = select(Revocation).where(Revocation.license_id == license_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
