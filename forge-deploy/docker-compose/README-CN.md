# Forge — docker-compose 部署指南（中文）

适合**单机 / 一体机 / 内网私有化**部署。**开箱即用**：数据库（PostgreSQL）、缓存（Redis）、对象存储（本地卷）已全部内置，`docker compose up -d` 直接起全套——你只需在 `.env` 里填好 Secret / 密码。要改用外部数据库/缓存，改 `.env` 指过去并移除内置服务即可（见第 4.2）。

> 5 个组件：`forge-api`（签发核心）/ `forge-edge`（公网校验，唯一对外端口 8081）/ `forge-worker` / `forge-scheduler` / `forge-web`（控制台，80 端口）。

---

## 0. 前置条件

- 一台装了 **Docker + docker compose（v2）** 的机器。
- **无需自备数据库/缓存**——已内置 PostgreSQL + Redis，`up -d` 即起。要用外部的（PostgreSQL/MySQL/达梦… + Redis/Valkey），见第 4.2。
- 镜像仓库（内网 Harbor 或阿里云 ACR）里有 `forge-api:v1.0.0`、`forge-web:v1.0.0`。

---

## 1. 登录私有镜像仓库（私有 Harbor 必做）

compose 直接用主机的 docker 登录态拉镜像（不像 k8s 用 Secret）。用脚本登录：

```bash
cd Scripts
./generate-image-repo-secret.sh <仓库用户名> <仓库密码> <仓库地址>
# 例：./generate-image-repo-secret.sh robot$forge 'S3cr3t' harbor.intra.example.com
```

登录态会存在 `~/.docker/config.json`。公开仓库可跳过这步。

---

## 2. 准备 .env

```bash
cp .env.example .env
```

用编辑器打开 `.env`，**重点改这几项**（每个 `#REPLACE_ME#` 都要换成真值）：

```ini
# 镜像仓库（私有 Harbor 就改成你的地址）
REGISTRY=harbor.intra.example.com/forge
FORGE_TAG=v1.0.0

# 域名（用于 CORS / 控制台）
APP_BASE_URL=https://forge.your-company.com
EDGE_BASE_URL=https://edge.forge.your-company.com

# 两把 KEK（必须不同）：openssl rand -base64 32 生成
FORGE_FIELD_ENCRYPTION_KEY=<第一条 openssl 输出>   # 主密钥，给 api/worker/scheduler
FORGE_EDGE_KEK=<第二条 openssl 输出>               # 边缘密钥，给 edge（解不开主私钥）
EDGE_INTERNAL_TOKEN=<第三条 openssl 输出>

# 数据库密码（内置 PostgreSQL 用这个初始化；host/账号/库名默认 postgres/forge_app/forge_main，无需改）
DATABASE_PASSWORD=<数据库密码>
# 给 edge 的受限账号密码（内置库会用它自动创建 forge_edge 角色）
EDGE_DATABASE_PASSWORD=<受限账号密码>

# 缓存密码（内置 Redis 用这个；host 默认 redis，无需改）
CACHE_PASSWORD=<redis 密码>
```

> 生成 KEK：连续跑三次 `openssl rand -base64 32`，把三个输出分别填上面三行。
> **用内置数据库/缓存（默认）时，上面填密码即可**——`DATABASE_HOST/USERNAME/NAME`、`CACHE_HOST` 都有默认值无需设。要用外部库见第 4.2。

对象存储（`OBJECT_STORAGE_TYPE`）默认 `local`（存容器卷）。要用 S3/OSS 等就改 type + 填 endpoint/accessKey/secretKey。邮件、搜索默认关，按需开。

---

## 3. 受限数据库账号（edge 用）

edge 是公网组件，用受限账号 `forge_edge` 连库——读不到主私钥密文列，且 `audit_log` 只能追加（收回 UPDATE/DELETE）。

> **用内置 PostgreSQL（默认）时无需手动建**：首次启动会自动执行 `init/01-roles-and-audit.sh`，用你在 `.env` 设的 `EDGE_DATABASE_PASSWORD` 创建 `forge_edge` 角色并授权。用外部库时，参照该脚本在你的库里建好这个角色。

---

## 4. 启动

### 4.1 默认：开箱即用（内置 PostgreSQL + Redis）
填好 `.env` 的 Secret/密码后，一行起全套（含内置数据库 + 缓存 + 本地存储）：
```bash
docker compose up -d
```
首次启动会自动建库、跑迁移、创建 `forge_edge` 受限角色、初始化超管账号。

### 4.2 改用外部数据库/缓存
在 `.env` 把数据库/缓存指向你的外部服务，并加上 type/host 等：
```ini
DATABASE_TYPE=postgres        # postgres|mysql|tidb|dameng|opengauss|kingbase|oceanbase|polardb-pg|polardb-x
DATABASE_HOST=pg.intra.example.com
DATABASE_PORT=5432
DATABASE_USERNAME=forge_app
DATABASE_NAME=forge_main
CACHE_TYPE=redis              # 或 valkey
CACHE_HOST=redis.intra.example.com
```
然后在 `docker-compose.yaml` 里**删除/注释掉内置的 `postgres`、`redis` 服务**，再 `docker compose up -d`。
其它内置数据库可用 profile 顺带起：`docker compose --profile mysql up -d`（或 `dameng | valkey | seaweedfs | search`）。

---

## 5. 私有 CA 证书（自签名 https 必做）

如果数据库/对象存储等用的是**自签名或企业私有 CA 的证书**，要让 Forge 信任它，否则连接报证书错误。

只需在 `.env` 里把 CA bundle 的路径填上，然后正常 `up` 即可（已合并进主 compose，无需第二个文件）：
```ini
FORGE_CA_FILE=/etc/pki/your-company-ca.crt
```
```bash
docker compose up -d
```
这会把 CA 只读挂进 4 个后端容器并自动设好 `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `AWS_CA_BUNDLE` / `CURL_CA_BUNDLE`（覆盖 Python httpx/requests/boto3/数据库 TLS）。不填 `FORGE_CA_FILE` 时这些变量为空、挂载指向 `/dev/null`，完全无副作用。

---

## 6. 验证

```bash
docker compose ps
docker compose logs forge-api | grep "Application startup complete"
```

浏览器打开 `http://<本机IP>` 或你的域名，用**初始超管账号**登录：

- 邮箱：`forge@navtra.ai`
- 密码：`forge@navtra.ai`（密码 = 邮箱，**首次登录后请到「个人信息」页立即修改**）

> **HTTP 访问登不进去？** 会话 Cookie 默认带 `Secure`（只在 HTTPS 下发送）。用纯 HTTP（IP 直连、无证书）时，`.env` 里必须 `SESSION_COOKIE_SECURE=false`（`.env.example` 已默认 false），否则浏览器丢弃 Cookie、登录无法保持。配好 HTTPS 后再改回 `true`。

---

## 7. 常用命令

```bash
docker compose pull        # 拉新镜像
docker compose up -d        # 应用变更
docker compose down         # 停止（数据卷保留）
docker compose logs -f forge-api
```

---

## 常见问题
- **拉不到镜像**：第 1 步没 `docker login`，或 `.env` 里 `REGISTRY` 不对。
- **api 起不来**：数据库连不通——核对 `DATABASE_*`；自签证书要走第 5 步。
- **证书错误**：按第 5 步开启 customCA 叠加文件。
- **edge 报权限**：第 3 步的受限账号没建好/没授权。
