"""Customers admin API — full CRUD (incl. soft delete)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, audit_ctx, get_db_session
from app.core.errors import BizError
from app.models.customer import Customer
from app.permissions.deps import require_perm
from app.permissions.registry import P
from app.repositories.license import CustomerRepository
from app.schemas.catalog import CustomerCreate, CustomerOut, CustomerUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/customers", tags=["customers"])


def _out(c: Customer) -> CustomerOut:
    return CustomerOut(id=str(c.id), name=c.name, contact_name=c.contact_name,
                       contact_email=c.contact_email, notes=c.notes)


@router.get("")
async def list_customers(page: int = 1, page_size: int = 50,
                         user: CurrentUser = Depends(require_perm(P.CUSTOMER_READ)),
                         db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = CustomerRepository(db)
    items = await repo.list(limit=min(page_size, 100), offset=(max(page, 1) - 1) * page_size)
    return {"data": [_out(c).model_dump() for c in items], "total": await repo.count()}


@router.post("", status_code=201)
async def create_customer(body: CustomerCreate, request: Request,
                          user: CurrentUser = Depends(require_perm(P.CUSTOMER_WRITE)),
                          db: AsyncSession = Depends(get_db_session)) -> CustomerOut:
    c = Customer(name=body.name, contact_name=body.contact_name,
                 contact_email=body.contact_email, notes=body.notes,
                 created_by=uuid.UUID(user.user_id))
    CustomerRepository(db).add(c)
    AuditService(db).log(action="customer.create", result="success", actor_id=user.user_id,
                         resource_type="customer", resource_id=body.name, **audit_ctx(request))
    await db.commit()
    return _out(c)


@router.patch("/{customer_id}")
async def update_customer(customer_id: str, body: CustomerUpdate, request: Request,
                          user: CurrentUser = Depends(require_perm(P.CUSTOMER_WRITE)),
                          db: AsyncSession = Depends(get_db_session)) -> CustomerOut:
    repo = CustomerRepository(db)
    c = await repo.get(uuid.UUID(customer_id))
    if not c:
        raise BizError("RESOURCE_NOT_FOUND")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    c.updated_by = uuid.UUID(user.user_id)
    AuditService(db).log(action="customer.update", result="success", actor_id=user.user_id,
                         resource_type="customer", resource_id=c.name, **audit_ctx(request))
    await db.commit()
    return _out(c)


@router.delete("/{customer_id}", status_code=200)
async def delete_customer(customer_id: str, request: Request,
                          user: CurrentUser = Depends(require_perm(P.CUSTOMER_DELETE)),
                          db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = CustomerRepository(db)
    c = await repo.get(uuid.UUID(customer_id))
    if not c:
        raise BizError("RESOURCE_NOT_FOUND")
    await repo.soft_delete(c, actor_id=uuid.UUID(user.user_id))
    AuditService(db).log(action="customer.delete", result="success", actor_id=user.user_id,
                         resource_type="customer", resource_id=c.name, **audit_ctx(request))
    await db.commit()
    return {"data": {"deleted": True}, "request_id": request.state.request_id}
