# 系统架构设计：Forge（License Authority）

> 第二步设计文档 1/6。上游 = `../prd/v1.0-mvp.md`。下游依赖：02-database → 03-api → 04-services → 05-frontend → 06-deployment。
> 约定来源：`Project-Docs/00-Global/{b2b-architecture §11.1, security, licensing, observability, cross-platform}.md`。

## 1. 目标

### 1.1 业务目标（摘自 PRD）
- 厂商专用签发所有 B 端产品的 License，**只有厂商能用**，绝不随产品交付。
- 双轨：在线短码（phone-home + 硬绑定 + 租约宽限 + seat 防复制）+ 离线 `.forge`（自包含签名 + 硬件硬绑定 + CRL）。
- 完整 CRUD（含删除）+ 内部审计可查 + 完美落库。

### 1.2 非功能性需求
| 维度 | 指标 |
|------|------|
| 安全 | 零破解；fail-closed；多点防绕过；私钥永不出 forge-api 进程；公网面全 OWASP 加固 |
| 可用性 | 在线校验 SLO ≥ 99.9%（直接影响客户产品运行）|
| 性能 | edge 在线校验 P95 ≤ 200ms（热路径 Redis）；签发 P95 ≤ 500ms |
| 备份 | 私钥最严（加密+异地+离线介质+季度演练）；RPO ≤1h / RTO ≤4h |
| 合规 | 审计 append-only ≥1 年；仅厂商员工 PII（简化合规）|
| 跨平台 | 6 组合；镜像 multi-arch（Oracle 无 arm64，文档标注）|

## 2. 架构总览

### 2.1 系统上下文（C4 L1）
```
┌────────────────────────────────────────────────────────────────┐
│                       厂商 navtra（Forge 域）                     │
│                                                                  │
│   操作员(Admin/Auditor) ──HTTPS──> forge-web ──> forge-api ◀─────┐│
│                                                  (持私钥,内网)    ││
│                                                       │          ││
│                                              [DB/Redis/OSS/SMTP] ││
│                                                       │          ││
│                                                  forge-edge ◀────┘│
│                                                (无私钥,公网入口)   │
└───────────────────────────────────────────────────────┬─────────┘
                                                          │ 公网 HTTPS
                          ┌───────────────────────────────┴───────────┐
                          │            客户私有化环境（出网）            │
                          │  消费方产品 + Verifier SDK(内嵌公钥)        │
                          │  - 在线: POST /edge/v1/activate|validate ──┘
                          │  - 离线: 本地验签 .forge（无网络）
                          └────────────────────────────────────────────┘
```
- 外部交互方：① 厂商操作员（管理端）；② 客户产品内嵌的 Verifier SDK（仅在线轨回连 edge）。
- 离线轨**零网络交互**：Verifier 本地用内嵌公钥验签。

### 2.2 容器图（C4 L2）
| 容器 | 技术 | 网络面 | 职责 | 私钥 |
|------|------|--------|------|------|
| `forge-web` | nginx + React SPA | 内网 | 操作员管理 UI | 无 |
| `forge-api` | FastAPI | **内网/localhost** | 签发核心 + 管理后端 API + edge 内部回路 | **持有** |
| `forge-edge` | FastAPI（裁剪） | **公网** | 在线 activate/validate、记指纹、发租约、查吊销 | **无** |
| `forge-worker` | Celery worker | 内网 | 到期邮件 / 吊销传播 / CRL 生成 / Outbox | 无 |
| `forge-scheduler` | Celery beat | 内网 | 到期扫描 / 租约清理 / 续期提醒触发 | 无 |
| Postgres(默认) | DB（4 provider 适配） | 内网 | License/客户/产品/审计/密钥(密文) | —— |
| Redis | Cache | 内网 | Session / 在线租约 / 限流 / 热校验 | —— |
| Object Storage | 8 provider | 内网 | `.forge` / 导出 / CRL | —— |
| Email | 6 provider | 出站 | 到期提醒 | —— |

### 2.3 关键数据流
- **在线签发**：forge-web → forge-api（生成 UUID 短码、落库 issued、seat 上限）→ 操作员复制短码。
- **在线激活**：客户产品 → `forge-edge /edge/v1/activate {online_code, fingerprint, cluster_id}` → edge 经内部网问 forge-api 校验/绑定 → 返回 `validation_token` + 租约（签名）。后续 `/edge/v1/validate` 续租约（edge 热路径走 Redis，未命中回 forge-api/DB）。
- **离线签发**：forge-web → forge-api（payload + Ed25519 私钥签名 → `.forge` tar，base64）→ 操作员复制。
- **离线激活**：客户产品 Verifier SDK 本地验签（内嵌公钥）+ 指纹比对 + 有效期 + CRL，**无网络**。

## 3. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 单体 vs 微服务 | **模块化单体后端（forge-server）多镜像部署** | forge-api/edge/worker/scheduler 同源不同入口，共享 base 层；§11.1 不强制前后台分离 |
| 签发/校验分离 | **forge-api(私钥·内网) + forge-edge(无私钥·公网)** | 守"私钥永不出厂商内网/不上公网攻击面"（`licensing.md` + security §2.3）；edge 被打穿无签发能力 |
| 同步 vs 异步 | 签发/激活同步；到期邮件/吊销传播/CRL 走 Celery 异步 + Outbox | 关键路径低延迟，副作用异步 |
| 在线断网 | **租约 + 宽限期**（默认租约 24h，宽限可配）| 兼顾可用性与 fail-closed（宽限到期仍 fail-closed）|
| 在线防复制 | **服务器侧 seat/实例追踪 + 首次硬件绑定** | 短码不含签名，唯一防线在服务器 |
| 离线吊销 | **到期重签 + 签名 CRL** | 离线无 phone-home，双手段 |
| 数据存储 | 关系型（4 provider）+ Redis 热缓存 | License 关系强；校验热路径要快 |
| 多租户 | **不做 Workspace**（§11.1 厂商单租户）| YAGNI；商业化再升级（§11.2）|

## 4. 多租户隔离方案

- **Forge 不实现 Workspace 多租户**（b2b §11.1 厂商内部产品放宽）。所有业务表**不带 `workspace_id`**，ORM 不注入 workspace 过滤。
- 隔离边界改为**角色权限**（Super Admin / Admin / Auditor）+ 软删 + 审计。
- §11.2 提醒：若未来对外商业化（多厂商 SaaS 化签发），需回补 `workspace_id` 升级标准 B 端档——数据模型预留该演进点（见 02-database §0）。

## 5. 安全架构（核心，最严档）

### 5.1 信任边界
```
[公网] ── forge-edge（无私钥, WAF, 限流, 严格输入校验, fail-closed）
   │  仅 /edge/v1/* + /healthz；CSP frame-ancestors none；TLS1.2+ / HSTS
   │  edge → forge-api 走内部网（可选 mTLS, 短期证书）
[内网] ── forge-api（私钥进程）── DB/Redis/OSS（禁公网端口）
   │  forge-web/worker/scheduler 同内网，均无私钥
```

### 5.2 私钥保护（贯穿）
- 私钥**只存在于 forge-api 进程 / Vault-HSM**；forge-edge/web/worker/scheduler **绝不挂载**。
- 静态：AES-256-GCM 加密；KEK 在 KMS / env `FORGE_FIELD_ENCRYPTION_KEY`（不进代码/仓库/日志），DEK 随密文存 DB；KEK 轮换 ≥ 年度。
- 零泄露：私钥 / 验签内部细节**绝不进**日志 / 错误响应 / API 响应 / 镜像 / 仓库；CI secret 扫描 gitleaks 强制。
- 签发 UI 不暴露"生成密钥"动作；私钥永不回显（只显公钥 + 脱敏 key id）。

### 5.3 加密链
- 传输：公网入口 HTTPS TLS1.2+，HTTP→HTTPS 308，HSTS preload，OCSP Stapling。
- 签名链：Ed25519（默认）厂商私钥签 + 消费方内嵌公钥验（detached signature）；payload 任一字段改动 → 签名失效。
- 在线租约：edge 用**边缘专用密钥**（非主签名私钥）签发短时租约 token；产品校验 edge 公钥。

### 5.4 鉴权流（三套路径隔离）
| 路径 | 用途 | 鉴权 |
|------|------|------|
| `/admin-api/v1/*` | 管理端 CRUD/签发 | Session Cookie + RBAC（forge-web）或 `X-Forge-API-Key`（程序化）|
| `/edge/v1/*` | 公网在线校验 | 短码 bearer（activate）→ `validation_token`（validate）+ 强限流 |
| `/internal/v1/*` | edge↔api 内部回路 | service token / mTLS，仅内网可达 |

### 5.5 防绕过（抗破解）
- 锁定/放行/seat/租约判定**多点独立 + 关键路径内联**，禁单一全局布尔（防一处 patch 解锁）。
- 时间防回拨：单调时间戳 + 最后已知时间。
- fail-closed：任何异常/缺失/解析失败/字段篡改 → 拒绝。
- 全 OWASP Top10：SSRF 私网 blocklist、SQL 参数化、CSRF SameSite+双提交、输入 Pydantic strict。

## 6. 可观测性

- **三支柱**：Metrics（Prometheus RED/USE，`/metrics`）；Logs（structlog JSON，脱敏，stdout）；Traces（OTel，`request_id` 贯穿响应+日志+审计）。
- 三探针：`/livez`（进程活）/ `/readyz`（DB/Redis 就绪）/ `/healthz`。
- 关键 SLI/SLO：edge 校验可用性 ≥99.9% / P95 ≤200ms；签发成功率 ≥99.9%。
- 关键告警：私钥访问异常、edge 5xx 激增、seat 超额激增、到期邮件失败、备份失败。

## 7. 跨平台支持

- 6 组合（Win/Linux/Mac × amd64/arm64）；生产 Linux amd64/arm64 Tier 1。
- 镜像 buildx **双架构**（linux/amd64 + linux/arm64），禁单架构。
- **限制**：Oracle DB 无 arm64 官方镜像 → arm64 部署不可选 Oracle provider（postgres/mysql/tidb 可）。`.gitattributes` LF；全 UTC + UTF-8；Windows 开发强制 WSL2。

## 8. 风险与取舍

| 风险 | 缓解 |
|------|------|
| 公网 edge 是攻击面 | edge 无私钥；WAF + 限流 + fail-closed；被打穿仅泄露校验逻辑，无签发能力 |
| 在线短码可被复制 | 首次硬件绑定 + seat 追踪 + 即时吊销；超额审计告警 |
| 离线无法实时吊销 | 到期重签为主 + 签名 CRL 强吹销；永久 License 谨慎签发 |
| 私钥单点 = 全客户命脉 | 进程隔离 + Vault-HSM + 加密备份异地离线 + 年度轮换双密钥窗口 |
| Oracle arm64 缺失 | 文档明示；arm64 默认 postgres |
| forge-api 内网不可达时 edge 退化 | edge 缓存内校验 + 短租约续命；新激活排队，绝不放行未校验 |
| 时钟回拨绕过有效期 | 单调时间 + 最后已知时间校验 |
