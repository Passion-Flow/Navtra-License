# Forge — docker-compose Deployment Guide (English)

For single-host / appliance / on-prem private deployments. You provide the backing services
**Batteries included**: PostgreSQL, Redis and object storage (a local volume) are all bundled, so
`docker compose up -d` brings up the whole stack — you only fill the secrets/passwords in `.env`.
To use an EXTERNAL database/cache instead, point `.env` at it and drop the bundled services (§4.2).

> 5 components: `forge-api` (signing core) / `forge-edge` (public validation, the only exposed port
> 8081) / `forge-worker` / `forge-scheduler` / `forge-web` (console, port 80).

---

## 0. Prerequisites
- A host with **Docker + docker compose (v2)**.
- **No external database/cache needed** — PostgreSQL + Redis are bundled and start with `up -d`.
  To use external ones (PostgreSQL/MySQL/Dameng… + Redis/Valkey), see §4.2.
- A registry (internal Harbor or Aliyun ACR) holding `forge-api:v1.0.0` and `forge-web:v1.0.0`.

---

## 1. Log in to your private registry (required for a private Harbor)
compose pulls images using the host's docker login (not a k8s Secret):
```bash
cd Scripts
./generate-image-repo-secret.sh <registry-user> <registry-pass> <registry-url>
# e.g. ./generate-image-repo-secret.sh robot$forge 'S3cr3t' harbor.intra.example.com
```
Skip this for a public registry.

---

## 2. Prepare .env
```bash
cp .env.example .env
```
Edit `.env` and replace every `#REPLACE_ME#`. Key items:
```ini
REGISTRY=harbor.intra.example.com/forge        # your private registry
FORGE_TAG=v1.0.0
APP_BASE_URL=https://forge.your-company.com
EDGE_BASE_URL=https://edge.forge.your-company.com

# two KEKs (MUST differ): openssl rand -base64 32
FORGE_FIELD_ENCRYPTION_KEY=<first openssl output>    # master KEK (api/worker/scheduler)
FORGE_EDGE_KEK=<second openssl output>               # edge KEK (cannot decrypt the master key)
EDGE_INTERNAL_TOKEN=<third openssl output>

# database password (the bundled PostgreSQL is initialised with it; host/account/db default to
# postgres/forge_app/forge_main — no need to set them)
DATABASE_PASSWORD=<db password>
# restricted edge account password (the bundled DB auto-creates the forge_edge role with it)
EDGE_DATABASE_PASSWORD=<restricted password>

# cache password (the bundled Redis uses it; host defaults to redis)
CACHE_PASSWORD=<redis password>
```
> Using the bundled DB/cache (default), just fill the passwords above — `DATABASE_HOST/USERNAME/NAME`
> and `CACHE_HOST` all have defaults. For an external DB see §4.2.
Object storage (`OBJECT_STORAGE_TYPE`) defaults to `local`. Mail/Search default off.

---

## 3. Restricted DB account (for edge)
edge is public and connects with a restricted `forge_edge` account — it cannot read the master key
ciphertext column, and `audit_log` is append-only (UPDATE/DELETE revoked).
> With the bundled PostgreSQL (default) you need NOT create it by hand: on first start
> `init/01-roles-and-audit.sh` runs automatically and creates `forge_edge` using the
> `EDGE_DATABASE_PASSWORD` from your `.env`. For an external DB, create the role per that script.

---

## 4. Start
### 4.1 Default: batteries included (bundled PostgreSQL + Redis)
After filling the secrets/passwords in `.env`, one command brings up everything (bundled DB + cache
+ local storage):
```bash
docker compose up -d
```
First start auto-creates the schema, runs migrations, creates the `forge_edge` role, and seeds the
super-admin.
### 4.2 Use an external DB/cache instead
Point `.env` at your service and add type/host:
```ini
DATABASE_TYPE=postgres        # postgres|mysql|tidb|dameng|opengauss|kingbase|oceanbase|polardb-pg|polardb-x
DATABASE_HOST=pg.intra.example.com
DATABASE_PORT=5432
DATABASE_USERNAME=forge_app
DATABASE_NAME=forge_main
CACHE_TYPE=redis              # or valkey
CACHE_HOST=redis.intra.example.com
```
then **remove/comment the bundled `postgres` and `redis` services** in `docker-compose.yaml` and
`docker compose up -d`. Other bundled databases via profiles:
`docker compose --profile mysql up -d` (or `dameng | valkey | seaweedfs | search`).

---

## 5. Private CA (required for self-signed https)
If your DB / object storage endpoints use a self-signed or private-CA certificate, set the CA path
in `.env` and start normally (merged into the main compose — no second file needed):
```ini
FORGE_CA_FILE=/etc/pki/your-company-ca.crt
```
```bash
docker compose up -d
```
The CA is mounted read-only into the 4 backend containers and `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE`
/ `AWS_CA_BUNDLE` / `CURL_CA_BUNDLE` are set automatically. When `FORGE_CA_FILE` is empty these are
blank and the mount points at `/dev/null` — completely harmless.

---

## 6. Verify
```bash
docker compose ps
docker compose logs forge-api | grep "Application startup complete"
```
Open `http://<host-ip>` (or your domain) and sign in with the **initial super-admin**:

- Email: `forge@navtra.ai`
- Password: `forge@navtra.ai` (password = email — **change it on the Profile page right after first login**).

> **Can't stay signed in over HTTP?** The session cookie is `Secure` by default (sent only over
> HTTPS). For a plain-HTTP trial (IP, no certificate) you must set `SESSION_COOKIE_SECURE=false` in
> `.env` (already the default in `.env.example`), otherwise the browser drops the cookie. Switch it
> back to `true` once you serve the console over HTTPS.

---

## 7. Common commands
```bash
docker compose pull
docker compose up -d
docker compose down
docker compose logs -f forge-api
```

---

## Troubleshooting
- **Image pull fails** — `docker login` (step 1) not done, or wrong `REGISTRY` in `.env`.
- **api won't start** — DB unreachable: check `DATABASE_*`; self-signed certs need step 5.
- **certificate errors** — enable customCA (step 5).
- **edge permission errors** — the restricted account (step 3) isn't created/granted.
