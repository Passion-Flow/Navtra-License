# 07 · 部署身份与反克隆（设备指纹安全升级）

> 状态：设计定稿（2026-06-12）。本文是实现契约，覆盖 Forge edge / models / scheduler、Verifier SDK（py/node/go）、licensing.md。
> 决策来源：设备指纹防克隆深度调研（Keygen / Cryptlex / Sentinel / LicenseSpring / systemd / cloud-init 官方）。

## 1. 问题与威胁模型

**现状缺陷**：部署指纹 = 实时采集的单一 machine-id（Linux `/etc/machine-id` 等）SHA-256，且**服务端不落库指纹**。两个真坑（均有官方背书）：

- **克隆 VM/模板化撞指纹**：systemd 官方要求克隆镜像必须清空 `/etc/machine-id`；cloud-init 对"克隆不重置 machine-id"标记 wont_fix。客户克隆已激活 VM → 两机同指纹 → **一张 License 多机共用（绕过 seat）**。
- **容器/K8s 指纹无意义**：Docker 默认不暴露 machine-id；pod 随机重启 → 指纹漂移；多 pod 同宿主 → 同指纹。
- **服务端无去重**：不存指纹，**无法发现"一证多机"**。

**威胁**：① 复制激活介质到另一台机/集群；② 克隆 VM 共享 License；③ 容器漂移导致误锁或绕过。

## 2. 身份三件套（核心设计）

业界统一范式（Keygen/Cryptlex/Sentinel/LicenseSpring 共识）：**多信号模糊指纹 + 首激活随机 install_id（与指纹双锁）+ 服务端落库去重**。三者缺一不可。

### 2.1 设备指纹（device fingerprint）——多信号 + 模糊匹配
客户端采集**信号向量**（各自哈希，不拼成单一 SHA-256）：

| 信号 | 来源 | 强度 |
|---|---|---|
| `dmi_product_uuid` | `/sys/class/dmi/id/product_uuid`（云厂商也用它当 instance 身份）| 强 |
| `board_serial` | DMI 主板序列号 | 强 |
| `disk_serial` | 根盘序列号 | 强 |
| `cpu_sig` | CPU 型号+核数+特征 | 中 |
| `machine_id` | `/etc/machine-id` / IOPlatformUUID / MachineGuid | 中（克隆会撞，不可单用）|
| `mac` | 首个非回环 MAC | 弱（虚拟网卡/随机化）|

- **匹配用模糊阈值**（学 Cryptlex/Sentinel）：N 个采到的信号中命中 ≥K 判同机（默认 N 中 ≥⌈N·0.6⌉，至少含 1 个强信号）。换盘/换网卡不立即失效，避免误杀。
- **对外仍暴露一个 `fingerprint` 字符串**（= 信号向量的规范化稳定摘要）作为主键展示（Deployment ID），但服务端额外存信号向量用于模糊比对与克隆检测。

### 2.2 install_id——首激活随机、与指纹双锁
- 首次激活时客户端生成 **128-bit 随机 install_id**，持久化到本地（裸机：受保护文件；K8s：见 §3）。
- **install_id 单独无效**：服务端激活记录 = `install_id + fingerprint 向量` 双锁。校验两者都要对。
- **防迁移**：整盘克隆把 install_id 一起带走 → 但 fingerprint 向量在新机对不上 → 拒。这是 install_id 必须叠加硬件指纹的原因（LicenseSpring 明确警告）。
- **满足"重部署即不同身份"**：重装/重部署无旧 install_id → 首激活必生成新值 → 客户看到的部署身份就变了；硬件指纹仍把它钉在本机。

### 2.3 注入式部署 UID（deployment UID）——容器/集群权威身份
容器里硬件信号不可信，由客户基础设施**注入一个稳定 UID**（`FORGE_DEPLOYMENT_UID` / 各产品 `<PRODUCT>_DEPLOYMENT_UID`，来自 ConfigMap/Secret）。存在即**优先作为权威身份**，跳过硬件指纹采集。

## 3. 各部署形态的身份解析（含集群/K8s/pod/GitLab）

| 形态 | 权威身份 | pod 重启 / 集群 / 重部署 |
|---|---|---|
| **裸机 / 单 VM** | 多信号硬件指纹 + 文件持久化 install_id | 重启指纹不变；换盘换网卡模糊匹配兜底；重装→新 install_id |
| **容器 / K8s** | **注入 `*_DEPLOYMENT_UID`**（ConfigMap/Secret）+ install_id（存 PVC/Secret） | **pod 随机重启 → Secret 不变 → UID 不变 → 不重激活**；UID 缺失则 fail-closed 提示需注入 |
| **集群多机** | **整集群 = 一个 deployment UID = 一张 License**；多副本共享注入 UID | seat_limit 按副本数；或服务端并发上限兜底（floating 式）|
| **GitLab / Helm / compose** | 部署 Secret 注入稳定 UID | 同容器/集群 |

**身份解析优先级（SDK 内）**：`*_DEPLOYMENT_UID`（注入）> 多信号硬件指纹 > 报错 fail-closed。
**install_id 存储位置**：裸机 `~/.config/forge/<product>/install_id`（0600）；K8s 优先 PVC，无 PVC 则纳入注入 Secret。

## 4. 服务端 schema 变更（Forge）

### 4.1 `fingerprint_bindings` 扩列
```
+ install_id        String(64)  nullable   -- 首激活随机 id（与 fingerprint 双锁）
+ signals           JSONB       nullable   -- 信号向量 {dmi_product_uuid: h, board_serial: h, ...}（哈希后）
+ deployment_uid    String(128) nullable   -- 注入式 UID（容器/集群权威身份）
+ last_heartbeat_at DateTime(tz) nullable  -- 心跳水位（去死机）
```
唯一性：`(license_id, fingerprint)` 仍为业务键；克隆检测看"同 license 下 ALIVE 的不同 fingerprint 数 vs seat_limit"。

### 4.2 新表 `clone_alerts`
```
id, license_id FK, detected_at, alive_fingerprints int, seat_limit int,
sample JSONB(最多 N 个指纹摘要+ip), status(open/ack/resolved)
```

### 4.3 心跳与去死机
- ALIVE 定义：`last_heartbeat_at` 在窗口内（默认 **10 分钟**，仿 Keygen）。
- scheduler 定期（默认每 2 分钟）把超窗 binding 置 `status=dead`，释放 seat。

## 5. Edge API 变更

### 5.1 `/edge/v1/activate`（扩字段，向后兼容）
请求新增：`install_id`、`signals`（信号向量）、`deployment_uid?`。
逻辑：
1. 解析权威身份（deployment_uid 优先，否则 fingerprint）。
2. 查 `(license_id, 权威身份)` binding：
   - 命中 → 复用；校验 install_id 一致（不一致 = 介质被复制到新装 → 拒 `INSTALL_ID_MISMATCH`）。
   - 未命中 → **seat 计数 = 当前 ALIVE 的不同权威身份数**；`< seat_limit` 才新建 binding（存 install_id/signals/deployment_uid），否则 **`SEAT_LIMIT_EXCEEDED` 拒新 + 写 clone_alert**（决策：告警 + 超 seat 拒新）。
3. 模糊匹配：新 fingerprint 与既有 binding 的 signals 命中 ≥K → 视为同机的硬件漂移，**更新**既有 binding 而非新建（防换盘误占 seat）。

### 5.2 `/edge/v1/validate`（续期）
- 续期时更新 `last_heartbeat_at`；带上 install_id 比对（不符 → 锁 `INSTALL_ID_MISMATCH`）。
- 续期即心跳，无需单独心跳端点（OpenRelay 30s 复验天然就是心跳）。

### 5.3 克隆检测（落在 validate/activate 路径）
- 每次 activate/validate 后：若同 license 下 **ALIVE 的不同权威身份数 > seat_limit** → 写/更新 `clone_alert`，后台告警。
- 已在线的 binding 不动（只拒超出的新身份），符合"告警 + 超 seat 拒新"。

## 6. SDK 变更（py / node / go 对齐）

- `collect_signals()`：跨平台采多信号，返回 `{signal: sha256}` 向量 + 规范化 `fingerprint` 摘要。
- `resolve_identity()`：`*_DEPLOYMENT_UID` env > 多信号指纹 > 抛错。
- `install_id`：首次 `ensure_install_id(path)` 生成并持久化（0600），激活/校验都带上。
- activate/validate 请求体加 `install_id` / `signals` / `deployment_uid`。
- 公钥仍编译内嵌；无新增明文密钥。

## 7. 后台（forge-admin）

- License 详情页展示：当前 ALIVE bindings（fingerprint 摘要 / deployment_uid / install_id 摘要 / last_seen / ip）。
- 克隆告警列表（clone_alerts）：可 ack / resolve。

## 8. 兼容与迁移

- 旧 binding（无 install_id/signals）：validate 容忍 null（按旧单指纹逻辑放行），下次 activate 补齐。
- DB 迁移：Alembic 新增列与表，全部 nullable，不破坏既有激活。
- 镜像 tag 仍 **v1.0.0**（未发版，覆盖式）。

## 9. 明确反驳"纯随机每次部署变"

- 重启即变 → 破坏硬绑定（谁都能无限激活）。
- 存盘随机值 → 随快照/整盘克隆被复制 → 抗克隆失败。
- **正解**：随机 install_id 负责"重装即换身份 + per-install 唯一"；多信号指纹/注入 UID 负责"钉在本机/本集群"；服务端 install_id↔指纹双锁 + 心跳去重 + 超 seat 告警拒新负责"发现并挡住一证多机"。三者协同——这就是业界范式。

## 10. 验收

- 克隆 VM（同 machine-id）二次激活 → seat 满则拒 + 告警（不误锁已在线）。
- 同机重装 → 新 install_id，激活成功，旧 binding 心跳超时被回收。
- K8s pod 随机重启（Secret 注入 UID 不变）→ 不需要重激活、不误锁。
- 复制整个激活介质到异机 → fingerprint 不符 → 拒。
- 换硬盘（模糊匹配命中）→ 不新占 seat、不误锁。
