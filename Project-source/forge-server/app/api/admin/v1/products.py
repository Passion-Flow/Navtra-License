"""Products admin API — full CRUD (incl. soft delete)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, audit_ctx, get_db_session
from app.core.errors import BizError
from app.models.product import Product
from app.permissions.deps import require_perm
from app.permissions.registry import P
from app.repositories.license import ProductRepository
from app.schemas.catalog import ProductCreate, ProductOut, ProductUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/products", tags=["products"])


def _out(p: Product) -> ProductOut:
    return ProductOut(id=str(p.id), slug=p.slug, name=p.name, description=p.description,
                      features_template=p.features_template, quotas_template=p.quotas_template,
                      default_alg=p.default_alg, is_active=p.is_active)


@router.get("")
async def list_products(page: int = 1, page_size: int = 50,
                        user: CurrentUser = Depends(require_perm(P.PRODUCT_READ)),
                        db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = ProductRepository(db)
    items = await repo.list(limit=min(page_size, 100), offset=(max(page, 1) - 1) * page_size)
    return {"data": [_out(p).model_dump() for p in items], "total": await repo.count()}


@router.post("", status_code=201)
async def create_product(body: ProductCreate, request: Request,
                         user: CurrentUser = Depends(require_perm(P.PRODUCT_WRITE)),
                         db: AsyncSession = Depends(get_db_session)) -> ProductOut:
    repo = ProductRepository(db)
    if await repo.get_by_slug(body.slug):
        raise BizError("RESOURCE_CONFLICT", {"field": "slug"})
    p = Product(slug=body.slug, name=body.name, description=body.description,
                features_template=body.features_template, quotas_template=body.quotas_template,
                default_alg=body.default_alg, created_by=uuid.UUID(user.user_id))
    repo.add(p)
    AuditService(db).log(action="product.create", result="success", actor_id=user.user_id,
                         resource_type="product", resource_id=body.slug, **audit_ctx(request))
    await db.commit()
    return _out(p)


@router.patch("/{product_id}")
async def update_product(product_id: str, body: ProductUpdate, request: Request,
                         user: CurrentUser = Depends(require_perm(P.PRODUCT_WRITE)),
                         db: AsyncSession = Depends(get_db_session)) -> ProductOut:
    repo = ProductRepository(db)
    p = await repo.get(uuid.UUID(product_id))
    if not p:
        raise BizError("RESOURCE_NOT_FOUND")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    p.updated_by = uuid.UUID(user.user_id)
    AuditService(db).log(action="product.update", result="success", actor_id=user.user_id,
                         resource_type="product", resource_id=p.slug, **audit_ctx(request))
    await db.commit()
    return _out(p)


@router.delete("/{product_id}", status_code=200)
async def delete_product(product_id: str, request: Request,
                         user: CurrentUser = Depends(require_perm(P.PRODUCT_DELETE)),
                         db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = ProductRepository(db)
    p = await repo.get(uuid.UUID(product_id))
    if not p:
        raise BizError("RESOURCE_NOT_FOUND")
    await repo.soft_delete(p, actor_id=uuid.UUID(user.user_id))
    AuditService(db).log(action="product.delete", result="success", actor_id=user.user_id,
                         resource_type="product", resource_id=p.slug, **audit_ctx(request))
    await db.commit()
    return {"data": {"deleted": True}, "request_id": request.state.request_id}
