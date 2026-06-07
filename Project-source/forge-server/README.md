# forge-server

Forge License Authority backend — one codebase, four runtime roles selected by `APP_ROLE`:
`api` (signing core + admin backend, holds the Ed25519 private key, internal-only),
`edge` (public validation relay, no private key), `worker`, `scheduler`.

## Local development (no docker build needed)

### 1. Bring up the service dependencies
```sh
cd ../../services/database/postgres && docker compose up -d
cd ../../cache/redis && docker compose up -d
```

### 2. Install + configure
```sh
cd Project-source/forge-server
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e .            # or: pip install -e '.[dev]'
cp .env.example .env
# generate a real field-encryption KEK and put it in .env:
python -c "import os,base64;print('FORGE_FIELD_ENCRYPTION_KEY='+base64.b64encode(os.urandom(32)).decode())"
```

### 3. Migrate + seed the default super-admin
```sh
forge migrate up          # advisory-lock guarded; applies 000001_users + 000002_audit_log
forge bootstrap           # seeds Admin / forge@navtra.ai (login password = email, vendor-internal)
```

### 4. Run the admin/signing API
```sh
python main.py            # APP_ROLE=api by default -> http://localhost:13001
# health: curl http://localhost:13001/healthz
```

## Tests

```sh
pip install -e '.[dev]'
pytest -q                                   # unit tests (no services needed)
FORGE_INTEGRATION=1 pytest tests/test_auth_flow.py   # end-to-end login (needs pg+redis+migrate+bootstrap)
```

Unit suites: `test_crypto` (KEK/DEK + Ed25519 sign/verify/tamper), `test_security`
(argon2id + password policy), `test_errors` (error dictionary + envelope),
`test_rbac` (role/permission map). Integration: `test_auth_flow` (login/logout/me).

## Provider switching (field-ized, no connection strings)

`DATABASE_TYPE` ∈ postgres|mysql|oracle|tidb · `CACHE_TYPE`=redis ·
`OBJECT_STORAGE_TYPE` ∈ local|s3|… · `EMAIL_TYPE` ∈ smtp|aws_ses|…
The adapter layer assembles the SDK connection from the discrete `*_HOST/PORT/USERNAME/...` fields.
