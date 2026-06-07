"""Import all ORM models so every table is registered in Base.metadata regardless of which
app role (api/edge/worker) starts — FK resolution at flush time needs all tables present.
"""

from app.models import (  # noqa: F401
    audit,
    binding,
    customer,
    license,
    product,
    revocation,
    signing_key,
    user,
)
