# Forge backend image — one image for all 4 roles (api / edge / worker / scheduler);
# the role is chosen at runtime via APP_ROLE + command. Build context = Project-source/.
# Multi-arch (amd64 + arm64). Single-stage slim: every pinned dep ships cp314 wheels for both
# arches, so no compiler/toolchain is needed (keeps the image slim AND the cross-arch build light).
#   docker buildx build -f forge-server/Dockerfile -t forge-api:v1.0.0 .
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORGE_ERROR_CODES_PATH=/forge-shared/error-codes.yaml \
    APP_ROLE=api

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini \
    && rm -rf /var/lib/apt/lists/*

# Shared error-code dictionary (mounted in dev; baked into the image for delivery).
COPY forge-shared/ /forge-shared/

# App source + all provider extras so any storage/email/search provider works.
# (DATABASE_TYPE=dameng additionally needs the 达梦 native client libs baked in — a separate
#  image variant; see app/adapters/database/dameng/adapter.py.)
COPY forge-server/ /app/
WORKDIR /app
RUN pip install --no-cache-dir -e ".[storage,email,search]" \
    && chmod +x entrypoint.sh \
    && rm -rf tests

# Non-root runtime (signing core: least privilege).
RUN useradd -r -u 10001 forge && chown -R forge:forge /app /forge-shared
USER forge

EXPOSE 8080 8081
ENTRYPOINT ["tini", "--", "./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
