# API 设计：Forge

> 第二步设计文档 3/6。上游 = 01-system, 02-database。约定来源：`Project-Docs/00-Global/api-design.md` + `02-Backend/{api-design,orm-patterns}.md` + `error-codes.md`。
> OpenAPI 完整 spec stub 见同目录 `openapi.yaml`（实现期由 FastAPI 自动生成，分 admin / edge 两份）。

## 1. API 总览（三套路径隔离）

| 类别 | 前缀 | 运行容器 | 鉴权 | OpenAPI |
|------|------|----------|------|---------|
| 管理后端 | `/admin-api/v1/...` | forge-api（内网）| Session Cookie（forge-web）/ `X-Forge-API-Key`（程序化）+ RBAC | `/admin-api/v1/openapi.json` |
| 公网校验边缘 | `/edge/v1/...` | forge-edge（公网）| 短码 bearer → `validation_token` + 强限流 | `/edge/v1/openapi.json` |
| 内部回路 | `/internal/v1/...` | edge↔api（内网）| service token / mTLS | 不公开 |

- 风格 RESTful，资源复数 kebab-case，body snake_case，时间 UTC ISO8601。
- 非 CRUD 动作用 `:action` 后缀（`POST /licenses/{id}:revoke`）。
- 版本走 URL 路径（v1/v2），破坏性变更才升版。

## 2. 资源清单

### 2.1 管理后端 `/admin-api/v1`
| 资源 | 路径 | 方法 | 鉴权(权限) | 限流 |
|------|------|------|-----------|------|
| 认证 | `/auth/login` `/auth/logout` `/auth/reset-password` `/me` `/me/permissions` | POST/GET | Session | 登录档 |
| 2FA | `/auth/2fa:setup` `/auth/2fa:verify` `/auth/2fa:disable` | POST | Session | 严格 |
| 用户 | `/users` `/users/{id}` `/users/{id}:reset-password` | GET/POST/PATCH/DELETE | `platform.user.*`(Super Admin) | 默认 |
| 产品 | `/products` `/products/{id}` | GET/POST/PATCH/DELETE | `platform.product.*` | 默认 |
| 客户 | `/customers` `/customers/{id}` | GET/POST/PATCH/DELETE | `platform.customer.*` | 默认 |
| 签发 | `/licenses:issue-online` `/licenses:issue-offline` | POST | `platform.license.issue` | 严格 + Idempotency-Key |
| License | `/licenses` `/licenses/{id}` `/licenses/{id}:revoke` `/licenses/{id}:renew` `/licenses/{id}:replace` | GET/PATCH/DELETE/POST | `platform.license.*`（revoke/delete=Super Admin）| 默认 |
| 绑定 | `/licenses/{id}/bindings` `/licenses/{id}/bindings/{bid}:release` | GET/POST | `platform.license.read/update` | 默认 |
| 密钥 | `/signing-keys` `/signing-keys/{id}:rotate` `/signing-keys/{id}:export-public` | GET/POST | `system.key.*`(Super Admin) | 严格 |
| CRL | `/crl:generate` `/crl/latest` | POST/GET | `platform.license.revoke` | 默认 |
| 审计 | `/audit-logs` `/audit-logs:export` | GET/POST | `platform.audit.read`(Super Admin/Auditor) | 默认 |
| 设置 | `/settings/login` `/settings/password-policy` `/settings/2fa` `/settings/email` `/settings/email:test` | GET/PATCH/POST | `system.settings.*` | 默认 |
| 健康/文档 | `/health` `/livez` `/readyz` `/healthz` `/metrics` `/postman.json` `/docs` | GET | 公开/内网 | —— |

### 2.2 公网边缘 `/edge/v1`
| 资源 | 路径 | 方法 | 鉴权 | 限流 |
|------|------|------|------|------|
| 在线激活 | `/activate` | POST | 短码 bearer（body `online_code`）| 严格(每 IP+短码) |
| 在线续租 | `/validate` | POST | `validation_token` | 严格 |
| 吊销/CRL 查询 | `/revocations:check` | POST | `validation_token` | 严格 |
| 公钥/边缘公钥 | `/public-key` | GET | 公开（只读公钥）| 默认 |
| 健康 | `/healthz` | GET | 公开 | —— |

> edge **不**暴露任何管理/签发接口；不持私钥；CSP `frame-ancestors 'none'`；WAF + Bot 防护（如有表单）。

## 3. 关键端点契约

### 3.1 在线签发 `POST /admin-api/v1/licenses:issue-online`
```
Header: Idempotency-Key: <uuid>   # 24h 同 key+body 返回首次结果
Body: { customer_id, product_id, term_preset, subscription, quotas, features, seat_limit }
201: { data: { license_id, online_code, active_from, active_until, seat_limit, status:"issued" }, request_id }
```
- 服务端生成 UUID 短码、按 term_preset 算 active_until（perpetual→null）、落库 issued、未绑定。

### 3.2 离线签发 `POST /admin-api/v1/licenses:issue-offline`
```
Header: Idempotency-Key: <uuid>
Body: { customer_id, product_id, deployment_id, term_preset, subscription, quotas, features }
201: { data: { license_id, offline_blob(base64), bound_fingerprint, active_until }, request_id }
```
- forge-api 用私钥签 payload → `.forge`（tar: payload.json + signature.bin + metadata.json）→ base64。>30s 则 `202 + task_id` 轮询。

### 3.3 在线激活 `POST /edge/v1/activate`
```
Body: { online_code, fingerprint, cluster_id, product_meta? }
200: { validation_token, lease: { expires_at, grace_until }, license: { features, quotas, active_until }, request_id }
错误: 403 LICENSE_REVOKED / LICENSE_EXPIRED / LICENSE_SEAT_EXCEEDED / LICENSE_BINDING_MISMATCH ; 404 RESOURCE_NOT_FOUND
```
- edge→`/internal/v1/activate`→forge-api：校验短码 active、未超 seat → 首次写 `fingerprint_bindings`（绑定首个硬件）+ seat_used++ → 签短租约（edge_lease 密钥）。

### 3.4 在线续租 `POST /edge/v1/validate`
```
Body: { validation_token, fingerprint }
200: { lease: { expires_at, grace_until }, status:"active", request_id }
错误: 403 LICENSE_REVOKED / LICENSE_LEASE_EXPIRED / LICENSE_BINDING_MISMATCH
```
- 热路径走 Redis（db0 `forge:lease:*`）；未命中回 forge-api/DB；查吊销表。断网由**产品侧** SDK 在宽限期内容忍。

### 3.5 吊销 `DELETE`/`POST /admin-api/v1/licenses/{id}:revoke`
```
Body: { reason }
200: { data:{ status:"revoked", revoked_at }, request_id }
```
- 写 `revocations` + 置 license.status=revoked + 发 `license.revoked` 事件；在线即时生效，离线进 CRL。

## 4. 错误码扩展（业务码）

继承全局基础码（`AUTH_*`/`PERM_*`/`VALIDATION_*`/`RATE_LIMIT_*`/`RESOURCE_*`/`SYSTEM_*`），新增 Forge 业务码（`forge-shared/error-codes.yaml`，每码 zh-CN+en+http+log_level）：

| code | http | 含义 |
|------|------|------|
| `LICENSE_REVOKED` | 403 | 已吊销 |
| `LICENSE_EXPIRED` | 403 | 已过期 |
| `LICENSE_BINDING_MISMATCH` | 403 | 指纹不匹配 |
| `LICENSE_SEAT_EXCEEDED` | 403 | 超 seat（在线复制白嫖）|
| `LICENSE_LEASE_EXPIRED` | 403 | 租约+宽限到期 |
| `LICENSE_INVALID_SIGNATURE` | 403 | 验签失败/篡改 |
| `LICENSE_NOT_ACTIVATED` | 409 | 在线短码未激活 |
| `ISSUE_INVALID_TERM` | 400 | 有效期档非法 |
| `ISSUE_DEPLOYMENT_ID_REQUIRED` | 400 | 离线缺部署ID |
| `EDGE_UPSTREAM_UNAVAILABLE` | 503 | edge 连不上 forge-api |
| `KEY_ROTATION_CONFLICT` | 409 | 密钥轮换冲突 |

统一响应 `{code, message, details, request_id}`；HTTP 层始终正确；禁裸字符串；500 不漏栈。

## 5. 鉴权矩阵（端点 × 角色）

| 端点组 | Super Admin | Admin | Auditor |
|--------|:-:|:-:|:-:|
| 签发 / 续期 / 替换 | ✅ | ✅ | ❌ |
| 吊销 / 删除 License | ✅ | ❌ | ❌ |
| 产品 / 客户 CRUD | ✅ | ✅ | ❌ |
| 用户管理 / 密钥管理 / 系统设置 | ✅ | ❌ | ❌ |
| 审计日志读 / 导出 | ✅ | ❌ | ✅ |
| License 列表/详情读 | ✅ | ✅ | ✅(只读) |

- RBAC 在 Workspace 解析之后（Forge 无 workspace，直接平台级）；前端 `usePerm()` 仅 UX，后端每端点独立 `@require_perm`。

## 6. 限流配置

| 维度 | 默认 |
|------|------|
| 全局 IP | 1000/min |
| 单 IP/endpoint | 60/min |
| 登录 | 同 IP ≤10/min；同账号失败 5 次锁 15min |
| **edge `/activate`** | 同 IP ≤20/min；同短码 ≤10/min（防爆破/枚举）|
| **edge `/validate`** | 同 token ≤60/min |
| 签发 | 同账号 ≤30/min |

429 带 `Retry-After`；Redis 滑动窗口（db4）。edge 限流尤为关键（公网面）。

## 7. Webhook 事件目录

| Event Type | 触发 | Payload 关键字段 |
|------------|------|------------------|
| `license.issued` | 签发成功 | license_id, mode, customer, product |
| `license.activated` | 首次激活 | license_id, fingerprint(脱敏), cluster_id |
| `license.expiring` | 到期前 30/7 天 | license_id, active_until |
| `license.expired` | 到期 | license_id |
| `license.revoked` | 吊销 | license_id, reason |
| `license.seat_exceeded` | 超 seat 回连 | license_id, attempted_fingerprint |

Payload `evt_<uuid>` + `type` + `api_version` + `X-Webhook-Signature`(HMAC-SHA256) + 5min 时间戳防重放 + 6 次指数退避 + DLQ（webhook.md）。

## 8. 中间件顺序（FastAPI，1→9）
CORS → Request ID → Trace(OTel) → Authentication(Session→state.user) → ~~License Gating~~（Forge 不自我 gate，**跳过**）→ ~~Workspace Resolution~~（无多租户，**跳过**）→ RBAC → Rate Limit → Audit Logger。
- edge 进程裁剪中间件：Request ID → Trace → Rate Limit(强) → 短码/token 校验 → Audit。

## 9. 约定细则
- Schema 命名 `<Entity>Create/Update/Out/List`，Pydantic v2 strict，`response_model=` 不直返 ORM。
- 分页：管理列表 offset（`page/page_size` 1..100）；审计/吊销大列表 cursor。排序白名单。
- 幂等：签发 + activate/validate 支持 `Idempotency-Key`。
- 每端点必限流；`request_id` 贯穿响应+日志+审计；OpenAPI 分 admin/edge 两份 + Postman。
