# forge-deploy

Production delivery artifacts for **Forge** (vendor License Authority), built for **private / on-prem
(私有化)** deployment. Three independent paths — pick one. Each has detailed bilingual guides.

> 5 components, 2 images: `forge-api` (signing core, internal) / `forge-edge` (public validation) /
> `forge-worker` / `forge-scheduler` share the `forge-api` image; `forge-web` (admin console) uses
> `forge-web`. Images: multi-arch amd64+arm64, tag `v1.0.0`.

## Pick your path / 选择部署方式

| Artifact | Use when / 适用 | Guides 文档 |
|---|---|---|
| **Helm** (`helm/`) | Kubernetes (incl. 信创 K8s) | [README-CN](helm/README-CN.md) · [README-EN](helm/README-EN.md) |
| **docker-compose** (`docker-compose/`) | single host / appliance / air-gapped | [README-CN](docker-compose/README-CN.md) · [README-EN](docker-compose/README-EN.md) |
| **GitLab CI/CD** (`gitlab/`) | build + test + (manual) push + deploy | [README-CN](gitlab/README-CN.md) · [README-EN](gitlab/README-EN.md) |

## Directory layout

```
forge-deploy/
├── helm/
│   ├── forge/                     # the chart (values.yaml + templates/{api,edge,worker,scheduler,web,shared})
│   ├── Scripts/generate-image-repo-secret.sh   # k8s imagePullSecret → forge-image-repo-secret
│   └── README-CN.md / README-EN.md
├── docker-compose/
│   ├── docker-compose.yaml        # x-shared-env anchor + 5 services + DB/cache/storage profiles
│   ├── .env.example               # every var documented, #REPLACE_ME# secrets, FORGE_CA_FILE
│   ├── init/01-roles-and-audit.sql# restricted edge DB role + audit_log REVOKE
│   ├── Scripts/generate-image-repo-secret.sh   # docker login (compose ≠ k8s)
│   └── README-CN.md / README-EN.md
└── gitlab/
    ├── .gitlab-ci.yml             # lint → test → build(multi-arch) → push(manual) → deploy(manual)
    ├── Scripts/generate-image-repo-secret-docker.sh   # docker-based runner
    ├── Scripts/generate-image-repo-secret-k8s.sh      # k8s deploy target
    └── README-CN.md / README-EN.md
```

## Common conventions (all three artifacts)

- **Private deployment** — every backing service (DB / cache / object storage / mail / search) is
  customer-managed; bundled subcharts are **off by default**, you fill the matching `external<Provider>`
  block (just set `type` + host / account / password / database).
- **Image pull secret** — named `forge-image-repo-secret` (follows the project), created by the
  `Scripts/` helper; for a private internal Harbor / Aliyun ACR.
- **Private CA (`customCA` / `FORGE_CA_FILE`)** — trust a self-signed / private-CA https certificate;
  sets `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `AWS_CA_BUNDLE` / `CURL_CA_BUNDLE` on the backend pods.
- **Key isolation** — `forge-edge` (public) gets **only** the edge KEK + a restricted DB account; it
  can never decrypt the master signing key. KEKs are `#REPLACE_ME#` placeholders; the app fails closed.
- **Manual publish** — CI builds images but only a human triggers the registry push.

## 信创 / domestic stack

Switch providers via values/env (no rebuild): `DATABASE_TYPE` (dameng/opengauss/kingbase/oceanbase/…),
`CACHE_TYPE` (redis/valkey), `OBJECT_STORAGE_TYPE`, `EMAIL_TYPE`, `SEARCH_TYPE`. **达梦** additionally
needs the DM native client libs baked into a `forge-api` image variant. Details:
`Project-Docs/03-Services/xinchuang.md`.

---

Start with the guide for your chosen path above. 先打开上表中对应方式的 README-CN / README-EN。
