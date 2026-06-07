# Forge — GitLab CI/CD 指南（中文）

`.gitlab-ci.yml` 提供 5 个阶段：`lint → test → build（多架构镜像）→ push（手动）→ deploy（手动，Helm 部署到 K8s）`。镜像**绝不自动推送**，必须人工触发 `push:images`。

---

## 1. 配置 CI 变量（Settings → CI/CD → Variables，切勿写进文件）

| 变量 | 说明 | 示例 |
|---|---|---|
| `REGISTRY` | 私有仓库地址（内网 Harbor 或阿里云 ACR）| `harbor.intra.example.com` |
| `REGISTRY_NAMESPACE` | 命名空间 | `forge` |
| `REGISTRY_USER` | 仓库用户名/机器人账号 | `robot$forge` |
| `REGISTRY_PASSWORD` | 仓库密码（**勾选 Masked**）| `••••••` |

如果要用 deploy 阶段（Helm 部署到 K8s），再加：

| 变量 | 说明 |
|---|---|
| `KUBECONFIG` | 类型选 **File**，内容是目标集群的 kubeconfig |
| `KUBE_NAMESPACE` | 部署命名空间，如 `forge` |
| `FORGE_MASTER_KEK` / `FORGE_EDGE_KEK` / `FORGE_EDGE_INTERNAL_TOKEN` | 三把密钥（Masked），`openssl rand -base64 32` 生成，前两把必须不同 |

---

## 2. 两个辅助脚本（`Scripts/`，按你的 runner/目标二选一）

GitLab 可能基于 **docker** 或 **k8s** 搭建，对应两个脚本：

- **docker-based runner**（CI 在 docker 里 build/push）：
  ```bash
  ./Scripts/generate-image-repo-secret-docker.sh <用户名> <密码> <仓库地址>
  ```
  本质是 `docker login`，把登录态写到 `~/.docker/config.json`。

- **部署目标是 k8s**（CI 用 Helm 部署到集群）：
  ```bash
  ./Scripts/generate-image-repo-secret-k8s.sh <用户名> <密码> <命名空间> <仓库地址>
  ```
  在集群里创建拉取密钥 `forge-image-repo-secret`（名字跟项目走）。deploy 阶段已自动调用它。

---

## 3. 各阶段说明

- **lint**：后端 `ruff`、前端 `eslint`（`allow_failure: true`，不卡流水线）。
- **test**：起 postgres+redis service，跑 `forge migrate up` + `bootstrap` + `pytest`。
- **build**：`docker buildx` 构建多架构（amd64+arm64）镜像——**只构建不推送**。
- **push（手动）**：人工点触发，`docker login` 后 `buildx --push` 推到仓库。**所有验证通过后再点**。
- **deploy（手动）**：`helm upgrade --install` 部署到 K8s；会先建拉取密钥，再用 CI 里的 KEK 变量安装。**记得改 `--set` 把数据库/缓存指向你的外部服务**（见 `helm/README-CN.md`）。

---

## 4. 自定义

- 改镜像版本：CI 变量 `VERSION`（默认 `v1.0.0`）。
- 改架构：`PLATFORMS`（默认 `linux/amd64,linux/arm64`；要龙芯加 `linux/loong64`）。
- deploy 的 `--set`：照 `helm/values.yaml` 的字段补全数据库/缓存/存储等。

> 安全：仓库密码、KEK 全部走 Masked CI 变量，绝不写进仓库。push 永远手动，符合"全部深测 + 审计通过后才推"的铁律。
