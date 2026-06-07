# Forge — Helm Deployment Guide (English)

Forge is a vendor-only License Authority. This chart targets **private / on-prem** deployments: you
provide every backing service (database, cache, object storage, mail, search) yourself, and the chart
only runs Forge's own 5 components.

> 5 components, 2 images: `forge-api` (signing core, internal) / `forge-edge` (public validation) /
> `forge-worker` (async tasks) / `forge-scheduler` (cron) — these 4 share the `forge-api` image;
> `forge-web` (admin console) uses the `forge-web` image.

---

## 0. Prerequisites

- A Kubernetes cluster (1.23+) with `kubectl` and `helm` (3.10+).
- The following **external services** already deployed (pick one type per category):
  - Database: PostgreSQL / MySQL / Dameng / KingbaseES / openGauss / OceanBase … (Dameng for 信创)
  - Cache: Redis or Valkey
  - (optional) Object storage: S3-compatible / Aliyun OSS / Tencent COS / SeaweedFS …; else a local PVC is used
  - (optional) Mail, Search
- A container registry (internal **Harbor** or Aliyun ACR) holding `forge-api:v1.0.0` and
  `forge-web:v1.0.0` (multi-arch amd64+arm64).

---

## 1. Create the image-pull secret (required for a private Harbor)

If your images live in a registry that requires login, create the Kubernetes pull secret with the
helper. The secret is always named **`forge-image-repo-secret`** (it follows the project name).

```bash
cd Scripts
./generate-image-repo-secret.sh <registry-user> <registry-pass> <namespace> <registry-url>
# e.g. internal Harbor:
./generate-image-repo-secret.sh robot$forge 'S3cr3t' forge https://harbor.intra.example.com
```

Then enable it at the bottom of `values.yaml`:

```yaml
imagePullSecrets:
  - name: forge-image-repo-secret
```

> For a public registry, skip this and leave `imagePullSecrets: []`.

---

## 2. Generate the two KEKs

Forge encrypts its private keys with two 32-byte keys. **They MUST differ**:

```bash
openssl rand -base64 32   # this is masterKek
openssl rand -base64 32   # this is edgeKek
openssl rand -base64 32   # this is edgeInternalToken
```

Put them into `values.yaml` under `secret.masterKek` / `secret.edgeKek` / `secret.edgeInternalToken`.
- `masterKek` encrypts the **master signing key** — given only to api/worker/scheduler.
- `edgeKek` encrypts the **online-lease key** — given to edge. Even a breached public edge cannot
  decrypt the master key. That is the system's security floor, so the two KEKs must differ.

---

## 3. Edit `values.yaml` (fill block by block)

Open `forge/values.yaml` and change only the items below; leave the rest at defaults.

### 3.1 Domains (global)
```yaml
global:
  useTLS: true
  adminDomain: "forge.your-company.com"
  edgeDomain:  "edge.forge.your-company.com"
```

### 3.2 Secrets
Paste the three values from step 2 into `secret.masterKek` / `edgeKek` / `edgeInternalToken`.

### 3.3 Database — set `type`, fill the matching block
`database.type` supports: `postgres, mysql, tidb, oracle, dameng, opengauss, kingbase, oceanbase,
polardb-pg, polardb-x`. Fill **only** the `external<Type>` block for the type you chose.

Example (PostgreSQL):
```yaml
database:
  type: "postgres"
  edgeUsername: "forge_edge"        # restricted account for edge (cannot read the master key ciphertext)
  edgePassword: "<edge db password>"
  externalPostgres:
    host: "pg.intra.example.com"
    port: 5432
    username: "forge_app"
    password: "<pg password>"
    database: "forge_main"
    sslMode: "require"
```

> **About `edgeUsername`/`edgePassword`**: edge is public, so it must connect with a **restricted DB
> account** (can read licenses, cannot read the master private-key column). Create + grant this account
> in your DB beforehand — see `docker-compose/init/01-roles-and-audit.sql` and run it on your database.

### 3.4 Cache (externalRedis)
```yaml
externalRedis:
  enabled: true
  type: "redis"          # or valkey
  host: "redis.intra.example.com"
  port: 6379
  password: "<redis password>"
```

### 3.5 Object storage (persistence) — defaults to local PVC
```yaml
persistence:
  type: "local"          # keep local if you have no object store
  # or S3-compatible:
  # type: "s3"
  # s3: { endpoint: "...", accessKey: "...", secretKey: "..." }
```

### 3.6 Mail / Search (optional, off by default)
Set `mail.enabled: true` (and fill the block) for expiry reminders; `search.enabled: true` for search.

### 3.7 Image pull secret (bottom)
See step 1.

---

## 4. Private CA (MOST IMPORTANT for private / 信创 intranets) — `global.customCA`

If your database / object storage / mail endpoints present **self-signed or private-CA https
certificates**, Forge must trust that CA or connections fail with a certificate error.

**Step 1** — put your CA cert into a Secret:
```bash
kubectl -n forge create secret generic forge-custom-ca \
  --from-file=ca.crt=/path/to/your-ca.crt
```

**Step 2** — enable it in `values.yaml`:
```yaml
global:
  customCA:
    enabled: true
    existingSecret: "forge-custom-ca"
    key: ca.crt
```

Each backend pod then runs an initContainer that merges the system CA bundle with your CA and sets
`SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `AWS_CA_BUNDLE` / `CURL_CA_BUNDLE` — covering Python httpx,
requests, boto3 (S3), and database TLS.
> Changing the CA requires a pod restart (the bundle is built once at startup).

---

## 5. Install

```bash
helm dependency build ./forge      # subcharts are vendored; works offline
helm install forge ./forge -n forge --create-namespace
```

Or pass the KEKs on the command line instead of editing values:
```bash
helm install forge ./forge -n forge --create-namespace \
  --set secret.masterKek=$(openssl rand -base64 32) \
  --set secret.edgeKek=$(openssl rand -base64 32) \
  --set secret.edgeInternalToken=$(openssl rand -base64 32)
```

---

## 6. Verify

```bash
kubectl -n forge get pods
kubectl -n forge logs deploy/forge-api | grep "Application startup complete"
```

Open `https://forge.your-company.com` and sign in with the initial super-admin account.

---

## 7. Upgrade / Uninstall

```bash
helm upgrade forge ./forge -n forge
helm uninstall forge -n forge        # external data / PVCs are not deleted
```

---

## Troubleshooting

- **ImagePullBackOff** — `forge-image-repo-secret` not created or not referenced in `imagePullSecrets` (step 1).
- **api never Ready** — usually the DB is unreachable: check the `database` block and the private CA (step 4).
- **SSL / certificate verify failed** — enable `global.customCA` (step 4).
- **edge permission errors** — the `edgeUsername` account isn't created/granted; run the grants in
  `docker-compose/init/01-roles-and-audit.sql`.

Security model and per-provider details: `Project-Docs/03-Services/xinchuang.md`.
