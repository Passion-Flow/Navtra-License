# Forge — GitLab CI/CD Guide (English)

`.gitlab-ci.yml` provides 5 stages: `lint → test → build (multi-arch) → push (MANUAL) → deploy
(MANUAL, Helm to Kubernetes)`. Images are **never pushed automatically** — a human triggers
`push:images`.

---

## 1. CI variables (Settings → CI/CD → Variables — never hard-code them)

| Variable | Meaning | Example |
|---|---|---|
| `REGISTRY` | private registry (internal Harbor or Aliyun ACR) | `harbor.intra.example.com` |
| `REGISTRY_NAMESPACE` | namespace | `forge` |
| `REGISTRY_USER` | registry user / robot account | `robot$forge` |
| `REGISTRY_PASSWORD` | registry password (**mark Masked**) | `••••••` |

For the deploy stage (Helm to K8s), also add:

| Variable | Meaning |
|---|---|
| `KUBECONFIG` | type **File**, the target cluster kubeconfig |
| `KUBE_NAMESPACE` | deploy namespace, e.g. `forge` |
| `FORGE_MASTER_KEK` / `FORGE_EDGE_KEK` / `FORGE_EDGE_INTERNAL_TOKEN` | three keys (Masked), `openssl rand -base64 32`; the first two MUST differ |

---

## 2. Two helper scripts (`Scripts/`, pick by runner/target)

GitLab can be **docker-based** or **k8s-based**, so two scripts are provided:

- **docker-based runner** (CI builds/pushes inside docker):
  ```bash
  ./Scripts/generate-image-repo-secret-docker.sh <user> <pass> <registry-url>
  ```
  This is `docker login`, storing creds in `~/.docker/config.json`.

- **k8s deploy target** (CI deploys with Helm):
  ```bash
  ./Scripts/generate-image-repo-secret-k8s.sh <user> <pass> <namespace> <registry-url>
  ```
  Creates the pull secret `forge-image-repo-secret` (named after the project). The deploy stage
  calls it automatically.

---

## 3. Stages

- **lint** — backend `ruff`, frontend `eslint` (`allow_failure: true`).
- **test** — postgres+redis services, `forge migrate up` + `bootstrap` + `pytest`.
- **build** — `docker buildx` multi-arch (amd64+arm64) images — build only, no push.
- **push (manual)** — human-triggered; `docker login` then `buildx --push`. Run only after full verification.
- **deploy (manual)** — `helm upgrade --install` to K8s; creates the pull secret first, installs with
  the KEK CI variables. **Edit the `--set` lines to point at your external DB/cache** (see `helm/README-EN.md`).

---

## 4. Customisation

- Image version: CI var `VERSION` (default `v1.0.0`).
- Architectures: `PLATFORMS` (default `linux/amd64,linux/arm64`; add `linux/loong64` for LoongArch).
- deploy `--set`: complete the database/cache/storage fields from `helm/values.yaml`.

> Security: registry password and KEKs all come from Masked CI variables, never committed. Push is
> always manual — consistent with the "push only after full testing + audit" rule.
