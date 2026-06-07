# Navtra License — Forge

**Forge** is a self-hostable **License Authority** for software vendors: issue, manage, and validate
software licenses for your customers from one signing core. It supports both **online activation
codes** and **offline `.forge` license files**, with Ed25519 signatures, envelope-encrypted secrets,
hardware binding, seat limits, and a signed revocation list (CRL) — all behind an admin console.

It is built for **private / on-prem deployment**: every backing service (database, cache, object
storage, mail, search) is pluggable, and the whole stack ships as docker-compose, a Helm chart, and a
GitLab CI pipeline.

---

## Architecture

Forge runs as five cooperating components (the backend is a single image driven by `APP_ROLE`):

| Component | Role |
| --- | --- |
| **forge-api** | Signing core — issues/manages licenses, holds the master signing key, admin API. |
| **forge-edge** | Public license validation. The only internet-facing service; uses a restricted DB account and never holds the master key. |
| **forge-worker** | Background jobs (Celery) — CRL refresh, license-expiry sweeps. |
| **forge-scheduler** | Periodic scheduler (Celery beat). |
| **forge-web** | Admin console (React) — issuance, customers, products, licenses, users, audit. |

The **api/edge split** is the core of the security model: only `forge-api` can sign and read the
master private key; `forge-edge` is exposed publicly but is cryptographically and database-wise
isolated, so compromising the public edge cannot leak signing material.

---

## Features

- **Online + offline licensing** — short activation codes for connected products, signed `.forge`
  blobs for air-gapped ones.
- **Strong cryptography** — Ed25519 signing, AES-256-GCM envelope encryption (KEK/DEK), argon2id
  password hashing. Separate master and edge key-encryption keys.
- **Hardware binding & seats** — bind licenses to a device fingerprint; enforce seat limits online.
- **Revocation** — a versioned, signed CRL that propagates to edge and offline verifiers.
- **Admin console** — products, customers, issuance, license lifecycle, self-service profile, audit
  log, operator management with RBAC, and TOTP two-factor auth.
- **Pluggable infrastructure** — PostgreSQL / MySQL / TiDB / Oracle / Dameng / OpenGauss / Kingbase /
  OceanBase / PolarDB; Redis / Valkey; local / S3 / OSS / COS / TOS / OBS / Azure Blob / GCS object
  storage; multiple SMTP and cloud email providers; OpenSearch.
- **Private CA support** — trust self-signed / enterprise CA certificates for every outbound TLS.

---

## Repository layout

```
Project-source/
  forge-server/      FastAPI backend (api / edge / worker / scheduler), SQLAlchemy, Alembic, Celery
  forge-admin/       React + TypeScript admin console (Vite, Tailwind, TanStack Query)
  forge-shared/      Shared error-code dictionary
forge-deploy/
  docker-compose/    Self-contained compose stack (batteries included)
  helm/              Helm chart (external services by default; bundled trial optional)
  gitlab/            GitLab CI pipeline
verifier-sdk/
  python/  node/  go/   Client SDKs to verify licenses inside your product
```

---

## Quick start (docker-compose)

The compose stack is **batteries-included** — PostgreSQL, Redis and local object storage are bundled,
so you only fill the secrets in `.env`:

```bash
cd forge-deploy/docker-compose
cp .env.example .env
# edit .env: set the three KEKs (openssl rand -base64 32) and the database/cache passwords
docker compose up -d
```

That brings up the full stack. The first start auto-creates the schema, runs migrations, creates the
restricted edge database role, and seeds the super-admin. Open the console at `http://<host>` and sign
in with the seeded account — email `forge@navtra.ai`, password `forge@navtra.ai` (change it on the
Profile page right after first login). Over plain HTTP keep `SESSION_COOKIE_SECURE=false` in `.env`
(the default) so the session cookie is not dropped; set it `true` once you serve over HTTPS.

To use an **external** database/cache instead, point `DATABASE_*` / `CACHE_*` in `.env` at your
services and remove the bundled `postgres` / `redis` services — see
[`forge-deploy/docker-compose/README-EN.md`](forge-deploy/docker-compose/README-EN.md).

---

## Deployment

| Target | Path | Default model |
| --- | --- | --- |
| **docker-compose** | `forge-deploy/docker-compose/` | Batteries included — `docker compose up -d`. |
| **Helm / Kubernetes** | `forge-deploy/helm/` | External services — you deploy the database/cache and fill the connection details in `values.yaml`. A bundled-trial path (`postgresql.enabled=true`) is available for throwaway clusters. |
| **GitLab CI** | `forge-deploy/gitlab/` | Lint → test → build → push → deploy pipeline. |

Each deliverable has bilingual `README-CN.md` / `README-EN.md` with step-by-step instructions,
private-image-registry login scripts, and private-CA configuration.

---

## Client verification SDKs

Embed license verification directly in your product. The SDKs verify the Ed25519 signature, check
hardware binding and expiry, consult the CRL, and harden against clock-rollback offline:

- **Python** — `verifier-sdk/python`
- **Node.js** — `verifier-sdk/node`
- **Go** — `verifier-sdk/go`

All three share the same compact signed-token format and return a uniform verdict
(`active` / `expiring` / `expired` / `revoked` / `binding_mismatch` / `invalid_signature` / `locked`).

---

## Security model

- **Key isolation** — the master KEK is held only by `forge-api` / `forge-worker` / `forge-scheduler`.
  `forge-edge` gets a separate edge KEK and cannot decrypt the master private key.
- **Restricted edge DB role** — the public edge connects with an account that cannot read the master
  key ciphertext column; the audit log is append-only.
- **Defense in depth** — argon2id passwords, TOTP 2FA, RBAC, session invalidation on privilege
  change, HSTS, and HTTP→HTTPS enforcement at the edge when TLS is enabled.

---

## Requirements

- Backend: Python 3.14, PostgreSQL/MySQL (or a supported alternative), Redis/Valkey.
- Console: Node.js 20+ to build the React app (or use the prebuilt `forge-web` image).
- Container images: `forge-api` and `forge-web` (multi-arch amd64/arm64).
