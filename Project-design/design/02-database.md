# 数据模型设计：Forge

> 第二步设计文档 2/6。上游 = 01-system。约定来源：`Project-Docs/00-Global/{database, data-validation, audit-log, b2b-architecture §11.1}.md`。
> 多 provider 兼容（postgres/mysql/oracle/tidb）：下文用 PostgreSQL 方言示例；可移植规则见 §11。

## 0. Workspace 决策（前置）

- **不使用 `workspace_id`**：Forge 厂商单租户（b2b §11.1 放宽多租户）。所有业务表**不带** `workspace_id`，ORM 不注入 workspace 过滤，不适用"联合索引首列 workspace_id"规则。
- **演进点（§11.2）**：若未来商业化为多厂商 SaaS 签发，需新增 `workspace_id` 并回补隔离——届时走 evolution-protocol 升级，不在 v1 实现。

## 1. ER 图

```
customers ──1:N──> licenses <──N:1── products
                      │ N:1
                      ├──────> signing_keys
                      │ 1:N
                      ├──────> fingerprint_bindings ──1:N──> leases
                      │ 1:N
                      └──────> revocations ──N:1──> crl_bundles
users ──(issued_by/created_by/updated_by)──> licenses / products / customers ...
audit_log（独立 append-only，软引用 actor_id / resource_id，不设 FK）
outbox（事务性事件）   idempotency_keys（幂等）
```

## 2. 实体清单

| 表名 | 用途 | 软删 | 关键索引/唯一 |
|------|------|------|---------------|
| `users` | 厂商操作员（Super Admin/Admin/Auditor）| ✅ | `uq_users_email`(WHERE deleted_at IS NULL) |
| `products` | 产品（A/B/C/D…）| ✅ | `uq_products_slug`(WHERE deleted_at IS NULL) |
| `customers` | 客户企业 | ✅ | `idx_customers_name` |
| `signing_keys` | 签名密钥对（私钥密文）| ✅ | `uq_signing_keys_key_id` |
| `licenses` | 签发的 License（在线/离线）| ✅ | `uq_licenses_license_id`, `uq_licenses_online_code`(部分), `idx_licenses_customer_product`, `idx_licenses_status_active_until` |
| `fingerprint_bindings` | 在线 seat/硬件绑定追踪 | ✅ | `uq_binding_license_fp`, `idx_binding_license` |
| `leases` | 在线租约（持久化供审计；热态在 Redis）| ✅ | `idx_leases_license`, `idx_leases_expires` |
| `revocations` | 吊销记录 | ❌（业务上保留）| `uq_revocations_license` |
| `crl_bundles` | 签名 CRL 包版本 | ✅ | `uq_crl_version` |
| `audit_log` | append-only 审计 | **无 deleted_at** | `(timestamp)`,`(actor_id,timestamp)`,`(resource_type,resource_id,timestamp)` |
| `outbox` | 事务性事件外发 | ❌ | `idx_outbox_unpublished` |
| `idempotency_keys` | 幂等键（签发 24h）| ❌ | `uq_idem_key_scope` |

基线列（除 audit_log/outbox/idempotency_keys 外每张业务表都有）：`id uuid PK DEFAULT uuid v7`、`created_at`、`updated_at`、`deleted_at`、`created_by`、`updated_by`。

## 3. 字段详细（关键表）

```sql
-- 000001_users
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  email         varchar(320) NOT NULL CHECK (email ~ '^[^@]+@[^@]+\.[^@]+$'),
  username      varchar(64)  NOT NULL,
  password_hash varchar(255) NOT NULL,                 -- argon2id
  role          varchar(20)  NOT NULL DEFAULT 'admin'
                CHECK (role IN ('super_admin','admin','auditor')),
  is_active     boolean      NOT NULL DEFAULT true,
  twofa_enabled boolean      NOT NULL DEFAULT false,
  twofa_secret_ciphertext text,                        -- AES-256-GCM
  backup_codes_ciphertext text,
  last_login_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz,
  created_by uuid, updated_by uuid
);
CREATE UNIQUE INDEX uq_users_email ON users(email) WHERE deleted_at IS NULL;

-- 000005_products
CREATE TABLE products (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  slug        varchar(64)  NOT NULL,                    -- 如 DIFY_ENTERPRISE
  name        varchar(255) NOT NULL,
  description text,
  features_template jsonb NOT NULL DEFAULT '[]',        -- 可选 features 模板
  quotas_template   jsonb NOT NULL DEFAULT '{}',        -- 可选 quotas 模板
  default_alg varchar(16) NOT NULL DEFAULT 'ed25519'
              CHECK (default_alg IN ('ed25519','rsa2048','rsa4096','sm2')),
  is_active   boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz, created_by uuid, updated_by uuid
);
CREATE UNIQUE INDEX uq_products_slug ON products(slug) WHERE deleted_at IS NULL;

-- 000006_customers
CREATE TABLE customers (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  name          varchar(255) NOT NULL,                  -- 客户企业名
  contact_name  varchar(128),
  contact_email varchar(320) CHECK (contact_email IS NULL OR contact_email ~ '^[^@]+@[^@]+\.[^@]+$'),
  notes         text,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz, created_by uuid, updated_by uuid
);

-- 000008_signing_keys（私钥密文，绝不明文/回显）
CREATE TABLE signing_keys (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  key_id      varchar(64)  NOT NULL,                    -- 如 ed25519-<short>
  alg         varchar(16)  NOT NULL CHECK (alg IN ('ed25519','rsa2048','rsa4096','sm2')),
  public_key  text         NOT NULL,                    -- PEM/base64，可导出
  private_key_ciphertext text NOT NULL,                 -- AES-256-GCM(私钥)
  dek_wrapped text NOT NULL,                            -- KEK 包裹的 DEK
  purpose     varchar(16) NOT NULL DEFAULT 'master'
              CHECK (purpose IN ('master','edge_lease')),
  is_active   boolean NOT NULL DEFAULT true,            -- 当前签发用
  rotated_at  timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz, created_by uuid, updated_by uuid
);
CREATE UNIQUE INDEX uq_signing_keys_key_id ON signing_keys(key_id);

-- 000010_licenses（核心）
CREATE TABLE licenses (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  license_id    uuid NOT NULL DEFAULT uuid_generate_v7(),   -- 对外脱敏展示
  customer_id   uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  product_id    uuid NOT NULL REFERENCES products(id)  ON DELETE RESTRICT,
  signing_key_id uuid NOT NULL REFERENCES signing_keys(id) ON DELETE RESTRICT,
  mode          varchar(8)  NOT NULL CHECK (mode IN ('online','offline')),
  online_code   varchar(64),                                -- 在线短码(UUID)；offline 为 NULL
  offline_blob  text,                                       -- 离线 .forge base64；online 为 NULL
  term_preset   varchar(16) NOT NULL
                CHECK (term_preset IN ('1m','3m','6m','1y','3y','5y','perpetual')),
  active_from   timestamptz NOT NULL,
  active_until  timestamptz,                                -- online perpetual=NULL; offline perpetual=签发+99y; 其余按档位
  subscription  varchar(32) NOT NULL DEFAULT 'Enterprise',
  quotas        jsonb NOT NULL DEFAULT '{}',
  features      jsonb NOT NULL DEFAULT '[]',
  scope         varchar(24) NOT NULL DEFAULT 'customer_x_product'
                CHECK (scope IN ('customer_x_product','customer_bundle','instance')),
  binding       varchar(8) NOT NULL DEFAULT 'hard'
                CHECK (binding IN ('none','soft','hard')),
  bound_fingerprint varchar(128),                           -- online:激活时绑;offline:签发时绑
  cluster_id    varchar(128),
  seat_limit    integer NOT NULL DEFAULT 1 CHECK (seat_limit >= 1),
  seat_used     integer NOT NULL DEFAULT 0 CHECK (seat_used >= 0),
  status        varchar(12) NOT NULL DEFAULT 'issued'
                CHECK (status IN ('issued','active','expiring','expired','revoked','locked')),
  alg           varchar(16) NOT NULL DEFAULT 'ed25519',
  issued_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  issued_at     timestamptz NOT NULL DEFAULT NOW(),
  activated_at  timestamptz,
  revoked_at    timestamptz,
  revoke_reason varchar(255),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz, created_by uuid, updated_by uuid,
  CHECK (mode <> 'online'  OR online_code  IS NOT NULL),
  CHECK (mode <> 'offline' OR offline_blob IS NOT NULL),
  CHECK (active_until IS NULL OR active_until > active_from)
);
CREATE UNIQUE INDEX uq_licenses_license_id ON licenses(license_id);
CREATE UNIQUE INDEX uq_licenses_online_code ON licenses(online_code) WHERE online_code IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_licenses_customer_product ON licenses(customer_id, product_id);
CREATE INDEX idx_licenses_status_active_until ON licenses(status, active_until);

-- 000012_fingerprint_bindings（在线 seat/硬件追踪）
CREATE TABLE fingerprint_bindings (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  license_id   uuid NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
  fingerprint  varchar(128) NOT NULL,
  cluster_id   varchar(128),
  status       varchar(12) NOT NULL DEFAULT 'active'
               CHECK (status IN ('active','released','blocked')),
  first_seen_at timestamptz NOT NULL DEFAULT NOW(),
  last_seen_at  timestamptz NOT NULL DEFAULT NOW(),
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  deleted_at timestamptz, created_by uuid, updated_by uuid
);
CREATE UNIQUE INDEX uq_binding_license_fp ON fingerprint_bindings(license_id, fingerprint) WHERE deleted_at IS NULL;
CREATE INDEX idx_binding_license ON fingerprint_bindings(license_id);

-- 000020_audit_log（append-only，无 deleted_at，仅 INSERT 权限）
CREATE TABLE audit_log (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  timestamp     timestamptz NOT NULL DEFAULT NOW(),         -- 服务端时间
  actor_type    varchar(12) NOT NULL CHECK (actor_type IN ('user','system','api_key','cli')),
  actor_id      varchar(128),
  actor_name    varchar(255),                               -- 快照
  action        varchar(48) NOT NULL,
  resource_type varchar(32),
  resource_id   varchar(128),
  result        varchar(8) NOT NULL CHECK (result IN ('success','failure')),
  reason        varchar(255),                               -- 失败=错误码
  ip            varchar(45),
  user_agent    varchar(512),
  request_id    varchar(64),
  metadata      jsonb NOT NULL DEFAULT '{}'                 -- 脱敏后
);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, timestamp);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id, timestamp);
```

其余表（`leases` / `revocations` / `crl_bundles` / `outbox` / `idempotency_keys`）字段在 Migration 阶段补全，遵循同一基线规则。

## 4. 关系与 ON DELETE 策略

| 外键 | 策略 | 理由 |
|------|------|------|
| `licenses.customer_id → customers.id` | RESTRICT | 有 License 的客户不可硬删（软删 + 审计）|
| `licenses.product_id → products.id` | RESTRICT | 同上 |
| `licenses.signing_key_id → signing_keys.id` | RESTRICT | 验签溯源不可断 |
| `licenses.issued_by → users.id` | SET NULL | 操作员删除不毁 License 历史 |
| `fingerprint_bindings.license_id → licenses.id` | CASCADE | 绑定从属 License |
| `revocations.license_id → licenses.id` | RESTRICT | 吊销记录须留存 |
| `audit_log` | **无 FK** | append-only，软引用，actor/resource 删除不影响历史 |

**删除语义（AC-5）**：业务删除一律软删（`deleted_at`）+ 审计；`audit_log` 永不删。物理清理由 scheduler 定时清 ≥90 天软删行（可配，合规对齐）。

## 5. Migration 计划（000001~）

`000001_users` · `000005_products` · `000006_customers` · `000008_signing_keys` · `000010_licenses` · `000012_fingerprint_bindings` · `000014_leases` · `000016_revocations` · `000018_crl_bundles` · `000020_audit_log` · `000022_outbox` · `000024_idempotency_keys` · `000030_seed_error_codes`。每个含 up+down，幂等（`IF NOT EXISTS`），通用 Alembic + 必要的方言 SQL。审计/索引大表用 `CREATE INDEX CONCURRENTLY`。

## 6. 数据分类（L1-L5，对齐 data-compliance）

| 表/字段 | 等级 | 加密 |
|---------|------|------|
| `signing_keys.private_key_ciphertext` / `dek_wrapped` | **L5 凭证** | AES-256-GCM（KEK/DEK 分层）|
| `users.password_hash` | L4 | argon2id（不可逆）|
| `users.twofa_secret_ciphertext` / `backup_codes_ciphertext` | L5 | AES-256-GCM |
| `customers.contact_email` / `contact_name` | L3 PII（厂商客户联系人）| 可选字段级加密 |
| `licenses.bound_fingerprint` / `cluster_id` | L3 | 脱敏展示 |
| `licenses.license_id` / `online_code` | L2 | 后台脱敏 `<前4>****<后4> Show` |
| `products` / `audit_log`(一般) | L2 | —— |

## 7. 性能考虑

- 数据量：License 量级中等（千~十万级）；`audit_log` 与 `leases`/`fingerprint_bindings` 增长快。
- 分区：`audit_log` 按月分区 + 归档到对象存储 `forge-audit-archive` 后清理；`leases` 热态主要在 Redis，DB 仅留审计。
- 索引覆盖：在线校验热路径 `licenses(online_code)` 唯一索引 + Redis 缓存；到期扫描走 `idx_licenses_status_active_until`。
- 单表 ≤5 索引；范围列（时间/状态）置联合索引末位。

## 8. 校验（三层，对齐 data-validation）

- 单一事实源 JSON Schema：`forge-shared/schemas/{license,product,customer,issue_request}.json` → 生成 Pydantic v2（strict + extra:forbid）+ Zod；CI diff 防漂移。
- DB CHECK 为最后防线（NOT NULL/UNIQUE/枚举 CHECK/FK），复杂业务规则在 Service 层。

## 9. 事务

- 业务写 + 审计写**同事务**（一起提交/回滚）；事件经 **Outbox** 在 commit 后发布。
- 在线 seat 计数走 Redis 分布式锁（db5）+ DB 落账，避免并发超 seat；长事务 >1s 禁止。

## 10. （保留）多租户演进
见 §0：v1 不实现，预留 `workspace_id` 升级路径。

## 11. 多 provider 可移植规则

- `jsonb` → MySQL/Oracle 用 `json` + 应用层校验；`uuid` → MySQL `BINARY(16)`/`CHAR(36)`、Oracle `RAW(16)`；`timestamptz` → Oracle `TIMESTAMP WITH TIME ZONE`。
- 部分唯一索引（`WHERE deleted_at IS NULL`）在不支持的引擎用「复合唯一含 deleted_at 规范化列」兜底。
- 方言特性（`RETURNING`/`ON CONFLICT`/序列）封装在 `app/adapters/database/<provider>/`；业务层只用方言中立 ORM。
- 默认隔离级别 Read Committed（MySQL InnoDB 适配器强制下调）。
