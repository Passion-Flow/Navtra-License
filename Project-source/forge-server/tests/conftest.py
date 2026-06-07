"""Shared test fixtures. Pure-unit tests need no services; integration tests are guarded
by FORGE_INTEGRATION=1 and require a live postgres + redis (see README)."""

import base64
import os
import uuid

import pytest
import pytest_asyncio

# A throwaway KEK so crypto/2FA code paths can run in unit tests (real KEK wins if set).
os.environ.setdefault("FORGE_FIELD_ENCRYPTION_KEY", base64.b64encode(b"0" * 32).decode())


def pytest_collection_modifyitems(config, items):
    if os.environ.get("FORGE_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="integration test — set FORGE_INTEGRATION=1 with live postgres+redis")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _fresh_engine():
    """Rebind the async engine to each test's own event loop (pytest-asyncio uses a fresh
    loop per test). Clearing the singleton before each test forces a fresh engine in the
    current loop, avoiding 'Event loop is closed' from reusing a prior loop's connections."""
    from app.db import session as s
    s.reset_engine()
    yield
    s.reset_engine()


@pytest_asyncio.fixture
async def db():
    """A DB session bound to the live (dev) database — integration tests only."""
    from app.db.session import get_sessionmaker
    async with get_sessionmaker()() as session:
        yield session


@pytest_asyncio.fixture
async def keys_ready(db):
    """Ensure master + edge_lease signing keys exist before licensing operations."""
    from app.licensing.keys import KeyManager
    await KeyManager(db).ensure_keys()
    await db.commit()


@pytest_asyncio.fixture
async def product_and_customer(db):
    """Fresh product + customer with unique identifiers (safe to run the suite repeatedly)."""
    from app.models.customer import Customer
    from app.models.product import Product
    sfx = uuid.uuid4().hex[:10]
    product = Product(slug=f"TEST_{sfx}", name=f"Test Product {sfx}", is_active=True)
    customer = Customer(name=f"Test Customer {sfx}")
    db.add(product)
    db.add(customer)
    await db.flush()
    return product, customer


CTX = {"ip": None, "user_agent": "pytest", "request_id": "test"}
