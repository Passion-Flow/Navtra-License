# Service 集成设计：Forge

> 第二步设计文档 4/6。约定来源：`Project-Docs/03-Services/{overview,database,object-storage,cache,email,init-scripts}.md`。
> 铁律：用到某分类 → 该分类**全部 provider** 必须实现适配器（用户拍板严守）。Env 字段化（禁 connection-string）。每 provider 一份 compose。

## 1. 5 大分类选型

| 分类 | 启用 | 默认 Provider | 必出 Provider |
|------|:-:|------|------|
| Object Storage | ✅ | local（filesystem）| 8 个全部：local(filesystem/minio双模),s3,azure-blob,aliyun-oss,google-storage,tencent-cos,volcengine-tos,huawei-obs |
| Database | ✅ | postgres | 4 个全部：postgres,mysql,oracle,tidb |
| Vector DB | ❌ | — | — |
| Cache | ✅ | redis | redis |
| Email | ✅ | smtp(MailHog dev) | 6 个全部：smtp,aws_ses,sendgrid,aliyun_dm,tencent_ses,volcengine_dm |

切换走 env `<SERVICE>_TYPE`；provider SDK 由适配器层封装，业务层只调统一接口。

## 2. 各 Service 用法

### 2.1 Database
- 用途：`users/products/customers/signing_keys/licenses/fingerprint_bindings/leases/revocations/crl_bundles/audit_log/outbox/idempotency_keys`。
- 账号分权：`forge_app`（业务，无 DDL）/ `forge_migrator`（CI 迁移）/ `forge_readonly`（审计/报表只读，对应 Auditor 数据）。
- 库：`forge_main`（业务）+ `forge_audit`（审计，可独立库）。
- 默认隔离 Read Committed；连接池 `DATABASE_POOL_SIZE=20`。
- **arm64 限制**：Oracle 无 arm64 镜像，arm64 部署不可选 oracle。

### 2.2 Cache / Redis（db 切分）
| db | 用途 | Forge 用法 |
|----|------|-----------|
| db0 | 业务缓存 | 在线热校验缓存 + 租约 `forge:lease:*`（TTL）|
| db1 | Session | `forge_admin_session:*` |
| db2 | Celery broker | 到期邮件/吊销传播/CRL 任务 |
| db3 | Celery result | 任务结果 |
| db4 | 限流计数 | 全局/登录/edge 限流滑动窗口 |
| db5 | 分布式锁 | 在线 seat 计数互斥（防并发超 seat）|

- redis.conf：AOF+RDB 双开、`maxmemory 1gb` `allkeys-lru`、危险命令重命名、`requirepass`。
- 3 模式：standalone(dev) / Sentinel / Cluster；适配器层支持全拓扑。

### 2.3 Object Storage
- 用途：`.forge` 文件归档（bucket `forge-uploads`）、审计/CRL 导出（`forge-exports`）、签名 CRL 包（`forge-public` 匿名只读）、临时（`forge-tmp`，7 天 TTL）。
- local-minio：`minio-init` 容器自动建 4 bucket + 设 `forge-public` 匿名 + `forge-tmp` ILM 7 天。
- 统一接口：`upload/download/delete/presigned_upload_url/presigned_download_url/head/list`。

### 2.4 Email
- 用途：License 到期提醒（30 天每周、7 天每天、过期当天），主备 failover（`EMAIL_FALLBACK_*` + 熔断 5 次→OPEN→fallback）。
- 关键邮件走 Celery `email` 队列 + DLQ；模板双语（zh-CN+en，HTML+TXT）。
- dev = MailHog（11025/18025）。

## 3. 适配器实现位置（统一接口 + 全 provider）

```
forge-server/app/adapters/
├── database/        base.py + {postgres,mysql,oracle,tidb}/        # 4
├── object_storage/  base.py + {local,s3,azure_blob,aliyun_oss,
│                     google_storage,tencent_cos,volcengine_tos,huawei_obs}/  # 8
├── cache/           base.py + redis/                               # 1（standalone/sentinel/cluster）
└── email/           base.py + {smtp,aws_ses,sendgrid,aliyun_dm,
                      tencent_ses,volcengine_dm}/                    # 6
```
- 业务代码只 import `base` 抽象接口；provider 由 `<SERVICE>_TYPE` 启动时选。禁业务层直接 import 具体 SDK。

## 4. 凭证管理（Env 字段化）

```
DATABASE_TYPE=postgres
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_USERNAME=forge_app
DATABASE_PASSWORD=Postgres@!QAZxsw2.
DATABASE_NAME=forge_main
DATABASE_SSL_MODE=prefer

CACHE_TYPE=redis
CACHE_HOST=redis
CACHE_PORT=6379
CACHE_PASSWORD=Redis@!QAZxsw2.
CACHE_DB_APP=0  CACHE_DB_SESSION=1  CACHE_DB_BROKER=2
CACHE_DB_RESULT=3  CACHE_DB_RATELIMIT=4  CACHE_DB_LOCK=5

OBJECT_STORAGE_TYPE=local
OBJECT_STORAGE_LOCAL_MODE=filesystem
OBJECT_STORAGE_DEFAULT_BUCKET=forge-uploads

EMAIL_TYPE=smtp
EMAIL_FROM_NAME=Forge
EMAIL_FROM_ADDRESS=forge@navtra.ai
```
- 密码默认 `<ServiceName>@!QAZxsw2.`（首字母大写）；公有云 provider 用客户自带 access key/secret，密码模板不适用。
- 字段名在 compose `.env` / Helm values / GitLab variables **一一对应**。
- **私钥 KEK** 独立：`FORGE_FIELD_ENCRYPTION_KEY`（KMS/Vault，不进任一 env_file 可达 edge/web）。

## 5. Service 故障降级矩阵

| 依赖故障 | 降级行为 |
|----------|----------|
| 主 DB | 签发只读拒绝；edge 走 Redis 缓存继续在线校验；恢复后补账 |
| Redis 缓存(db0) | edge 回退查 DB（降速不锁客户）|
| Redis Session(db1) | 管理端强制登出 |
| Redis Broker(db2/3) | 拒绝异步任务，到期邮件延后补发 |
| Redis Lock(db5) | seat 计数转 DB 行锁兜底 |
| Object Storage | `.forge`/CRL 下载不可用，签发仍即时返回文本 |
| Email | 入队暂存 + 主备 failover；关键邮件 DLQ + 告警 |
| forge-api（edge 视角）| edge 仅验已缓存 + 发短租约；新激活排队，**绝不放行未校验**（`EDGE_UPSTREAM_UNAVAILABLE`）|

## 6. Init（三层）
- Layer1 容器：postgres `init/01-extensions.sql`(uuid-ossp/pgcrypto/pg_trgm) + `02-readonly-user.sql`(forge_readonly)；minio-init 建 bucket；redis.conf。
- Layer2 应用：`forge migrate up`（advisory lock 互斥）→ `forge bootstrap`（超管 forge@navtra.ai + 错误码字典 + i18n + RBAC 角色映射）。
- Layer3：Forge 厂商手动初始化（§11.1 省向导 UI）：导入主密钥 / 改超管 / 配邮件，经 CLI + Settings 页完成。
- 禁 mock 业务数据进 bootstrap（`forge seed --demo` 另设）。
