# Forge — Helm 部署指南（中文）

Forge 是厂商专用的 License 签发系统。本 Chart 面向**私有化部署**：数据库、缓存、对象存储、邮件、搜索等所有依赖服务都由你自己提前部署好，Chart 只跑 Forge 自己的 5 个组件。

> 5 个组件、2 个镜像：`forge-api`（签发核心，内网）/ `forge-edge`（公网校验）/ `forge-worker`（异步任务）/ `forge-scheduler`（定时任务）—— 这 4 个共用 `forge-api` 镜像；`forge-web`（管理控制台）用 `forge-web` 镜像。

---

## 0. 前置条件

- 一个 Kubernetes 集群（1.23+）+ 能用 `kubectl`、`helm`（3.10+）。
- 已准备好以下**外部服务**（任选其一类型，私有化常用括号内）：
  - 数据库：PostgreSQL / MySQL / 达梦 / 人大金仓 / openGauss / OceanBase …（信创首选达梦）
  - 缓存：Redis 或 Valkey
  - （可选）对象存储：S3 兼容 / 阿里云 OSS / 腾讯云 COS / SeaweedFS …，不配就用本地 PVC
  - （可选）邮件、搜索
- 一个镜像仓库（内部 **Harbor** 或阿里云 ACR），里面有 `forge-api:v1.0.0` 和 `forge-web:v1.0.0`（多架构 amd64+arm64）。

---

## 1. 创建镜像拉取密钥（私有 Harbor 必做）

如果镜像在需要登录的私有仓库（如内部 Harbor），先用脚本生成 K8s 拉取密钥。密钥名固定叫 **`forge-image-repo-secret`**（跟项目名走）。

```bash
cd Scripts
./generate-image-repo-secret.sh <仓库用户名> <仓库密码> <命名空间> <仓库地址>
# 例：内部 Harbor
./generate-image-repo-secret.sh robot$forge 'S3cr3t' forge https://harbor.intra.example.com
```

执行后会在指定命名空间创建 `forge-image-repo-secret`。然后在 `values.yaml` 最底部启用它：

```yaml
imagePullSecrets:
  - name: forge-image-repo-secret
```

> 如果是公开仓库 / 不需要登录，这一步跳过，`imagePullSecrets` 留空 `[]`。

---

## 2. 生成两把密钥（KEK）

Forge 用两把 32 字节密钥加密私钥。**两把必须不一样**：

```bash
openssl rand -base64 32   # 这是 masterKek（主密钥 KEK）
openssl rand -base64 32   # 这是 edgeKek（边缘 KEK）
```

把这两个值分别填到 `values.yaml` 的 `secret.masterKek` 和 `secret.edgeKek`。
- `masterKek`：加密**主签发私钥**，只发给 api/worker/scheduler。
- `edgeKek`：加密**在线租约私钥**，发给 edge。即使公网 edge 被攻破，也解不开主私钥——这是本系统的安全底线，所以两把一定要不同。

再生成一个内部 token：

```bash
openssl rand -base64 32   # 填到 secret.edgeInternalToken
```

---

## 3. 改 `values.yaml`（核心，按块填）

打开 `forge/values.yaml`，**只改下面这几处**，其余保持默认即可。

### 3.1 域名（global）
```yaml
global:
  useTLS: true                          # 用 https 就改 true
  adminDomain: "forge.your-company.com"      # 管理控制台域名
  edgeDomain:  "edge.forge.your-company.com" # 公网校验域名
```

### 3.2 密钥（secret）
把第 2 步生成的三个值填进去：
```yaml
secret:
  masterKek: "<第一条 openssl 输出>"
  edgeKek:   "<第二条 openssl 输出>"
  edgeInternalToken: "<第三条 openssl 输出>"
```

### 3.3 数据库（database）—— 选 type，填对应那一块
`database.type` 支持：`postgres, mysql, tidb, oracle, dameng, opengauss, kingbase, oceanbase, polardb-pg, polardb-x`。
**只需填你选的那一种对应的 `external<类型>` 块**，其它块不用管。

例：用达梦（信创）
```yaml
database:
  type: "dameng"
  edgeUsername: "FORGE_EDGE"        # 给 edge 用的受限账号（只读，读不到主私钥密文）
  edgePassword: "<受限账号密码>"
  externalDameng:
    host: "dm.intra.example.com"
    port: 5236
    username: "SYSDBA"
    password: "<达梦密码>"
    database: "FORGE"
    sslMode: "disable"
```

例：用 PostgreSQL
```yaml
database:
  type: "postgres"
  edgeUsername: "forge_edge"
  edgePassword: "<受限账号密码>"
  externalPostgres:
    host: "pg.intra.example.com"
    port: 5432
    username: "forge_app"
    password: "<pg 密码>"
    database: "forge_main"
    sslMode: "require"
```

> **关于 `edgeUsername`/`edgePassword`**：edge 是公网组件，必须用一个**受限数据库账号**连库（能读许可证、不能读主私钥密文那一列）。这个账号需要你在数据库里提前建好并授权。具体授权 SQL 见 `docker-compose/init/01-roles-and-audit.sql`，照着在你的库里执行。

### 3.4 缓存（externalRedis）
```yaml
externalRedis:
  enabled: true
  type: "redis"          # 或 valkey
  host: "redis.intra.example.com"
  port: 6379
  password: "<redis 密码>"
```

### 3.5 对象存储（persistence）—— 默认 local，要用云存储就选 type 填块
```yaml
persistence:
  type: "local"          # 不配云存储就保持 local（用 PVC 存签发产物 + CRL）
  # 若用 S3 兼容：
  # type: "s3"
  # s3:
  #   endpoint: "https://minio.intra.example.com"
  #   accessKey: "..."
  #   secretKey: "..."
```

### 3.6 邮件 / 搜索（可选，默认关）
要发到期提醒邮件就 `mail.enabled: true` 并填对应块；要搜索就 `search.enabled: true`。不需要就保持 `false`。

### 3.7 镜像拉取密钥（最底部）
见第 1 步，填 `imagePullSecrets`。

---

## 4. 私有 CA 证书（私有化最关键，`global.customCA`）

如果你的数据库 / 对象存储 / 邮件等是**自签名证书或企业私有 CA 签发的 https**，必须让 Forge 信任这个 CA，否则连接会报证书错误。

**第一步**：把你的 CA 证书做成一个 Secret（自己执行）：
```bash
kubectl -n forge create secret generic forge-custom-ca \
  --from-file=ca.crt=/path/to/your-ca.crt
```

**第二步**：在 `values.yaml` 开启：
```yaml
global:
  customCA:
    enabled: true
    existingSecret: "forge-custom-ca"   # 上一步建的 Secret 名
    key: ca.crt                          # Secret 里证书的键名
```

开启后，每个后端 Pod 启动时会有一个 initContainer 把系统 CA 和你的私有 CA 合并成一个文件，并自动设好 `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `AWS_CA_BUNDLE` / `CURL_CA_BUNDLE`——覆盖 Python httpx、requests、boto3（S3）、数据库 TLS 等所有出站连接。
> 注意：改了 CA 需要重启 Pod 才生效（合并是启动时一次性做的）。

---

## 5. 安装

```bash
# 子 chart（postgresql/redis）已随包附带；离线环境也能装。联网可刷新：
helm dependency build ./forge

helm install forge ./forge -n forge --create-namespace
```

不想把密钥写进 `values.yaml`，也可以命令行传：
```bash
helm install forge ./forge -n forge --create-namespace \
  --set secret.masterKek=$(openssl rand -base64 32) \
  --set secret.edgeKek=$(openssl rand -base64 32) \
  --set secret.edgeInternalToken=$(openssl rand -base64 32)
```

---

## 6. 验证

```bash
kubectl -n forge get pods
# 等 forge-api 起来后看日志里有没有 "Application startup complete"
kubectl -n forge logs deploy/forge-api | grep "Application startup complete"
```

浏览器打开 `https://forge.your-company.com`，用初始超管账号登录（见交付说明）。

---

## 7. 升级 / 卸载

```bash
helm upgrade forge ./forge -n forge          # 改完 values 后升级
helm uninstall forge -n forge                # 卸载（PVC/外部数据不会被删）
```

---

## 常见问题

- **Pod 拉不到镜像（ImagePullBackOff）**：第 1 步的 `forge-image-repo-secret` 没建或没在 `imagePullSecrets` 引用。
- **api 一直没 Ready**：多半是数据库连不通——检查 `database` 块的 host/账号/密码，以及私有 CA（第 4 步）。
- **证书报错（SSL/certificate verify failed）**：开启 `global.customCA`（第 4 步）。
- **edge 报权限错误**：`edgeUsername` 账号没在数据库建好或没授权，执行 `docker-compose/init/01-roles-and-audit.sql` 里的授权。

安全模型与各 provider 详情见英文版 `README-EN.md` 与 `Project-Docs/03-Services/xinchuang.md`。
