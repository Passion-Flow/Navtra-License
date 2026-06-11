# Forge 服务器迁移手册（换服务器 / 换 IP / 换域名）

> 适用：docker-compose 部署形态（Helm 部署的迁移以本手册资产清单为准，操作改用 Velero/VolumeSnapshot）。
> 原则：**Forge 是全部已售产品的收费命脉**——迁移按"先演练、双机并行、验证后割接、保留回滚"执行，任何一步失败都不影响旧服务器继续服务。

---

## 0. 必须先懂的三件事

1. **两把 KEK 是命根子**：`FORGE_FIELD_ENCRYPTION_KEY`（master KEK）与 `FORGE_EDGE_KEK` 在 `.env` 里。签名私钥以 KEK 信封加密存在 PostgreSQL 中——**数据库 + KEK 必须同时迁走**；KEK 丢失 = 私钥永久无法解封 = 已发放的全部 License 体系作废（产品内嵌的公钥将再也没有对应私钥能签新票）。这是不可恢复事故，没有任何补救手段。
2. **离线客户零影响**：已用 `.forge` 离线激活的客户产品不与 Forge 通信，迁移对他们完全透明。
3. **在线客户的影响取决于端点形态**（对齐 `00-Global/licensing.md` [2026-06-11] 端点耐久性标准）：
   - **域名时代**（已购许可域名，DNS 指向 Forge）：迁移 = 改一条 DNS 记录，客户零感知。
   - **IP 时代**（当前过渡态，产品部署 env 直指 IP）：换服务器 = 新 IP，需逐个更新各产品部署的 `*_FORGE_EDGE_URL` 并依赖租约宽限期兜底。**这正是要尽快买域名的原因。**

### 迁移资产清单（缺一不可）

| 资产 | 位置（部署目录内） | 内容 | 必迁 |
|------|--------------------|------|------|
| PostgreSQL 数据 | `volumes/postgres`（经 pg_dump 导出） | 客户/产品/License 记录、**KEK 加密的签名私钥**、在线租约/席位状态、审计 | ✅ |
| `.env` | `.env` | **两把 KEK**、DB/Redis 密码、端口、邮件等全部配置 | ✅ |
| 文件存储卷 | `volumes/storage` | forge-shared/storage（生成的 License 文件等） | ✅ |
| Redis 卷 | `volumes/redis` | 缓存 + Celery 队列（AOF） | 建议（丢失仅损失在制队列任务） |
| 部署文件 | `docker-compose.yaml` / `init/` / `Scripts/` | 随发布包走，新机重新解压即可 | 随发布包 |
| 镜像 | 阿里云 ACR | 新机重新 `docker compose pull` | 重新拉取 |

---

## 1. 迁移前准备（新服务器）

1. 新服务器装好 Docker Engine + Compose 插件（`docker compose version` 能跑）。
2. **安全组放行**：TCP 80（forge-web 后台）、TCP 8081（forge-edge 公网验证端）。80 建议限源到厂商办公 IP；8081 必须对客户可达。
3. 解压同版本 Forge 部署包（如 `forge-docker-compose-1.0.0.tgz`）到部署目录；**不要**执行 `cp .env.example .env`（恢复脚本会落位旧 `.env`）。
4. 配镜像仓库登录：`bash Scripts/generate-image-repo-secret.sh`（docker login 到 ACR）。
5. 时钟同步确认：`timedatectl`（验签与租约对时间敏感，NTP 必须开启）。

## 2. 旧服务器备份

```bash
cd <部署目录>            # docker-compose.yaml 与 .env 所在目录
# 演练用热备份（不停服）：
bash migration/Scripts/backup-forge.sh
# 正式割接用终备份（短暂停应用层冻结写入，postgres/redis 不停，结束自动拉起）：
bash migration/Scripts/backup-forge.sh --final
```

产物 `forge-migration-<时间戳>.tar.gz`。传输到新服务器：

```bash
scp forge-migration-*.tar.gz user@<新服务器>:/opt/
```

⚠ 该包含 KEK 与全部许可数据：只走 scp/sftp，传完即删中转副本；长期留存的备份副本必须加密存放（如 `age`/`gpg` 加密后入对象存储）。

## 3. 新服务器恢复

```bash
cd <新部署目录>
bash migration/Scripts/restore-forge.sh /opt/forge-migration-<时间戳>.tar.gz
```

脚本顺序：校验 SHA256 → 落位 `.env` + storage/redis 卷 → 拉镜像 → 单起 postgres（首启自动建受限 edge 角色 + 审计 REVOKE）→ `pg_restore --clean` → 起全栈 → 等 forge-api 健康。

## 4. 验证清单（全过才允许割接）

```bash
# 4.1 五容器健康
docker compose ps        # forge-api / forge-edge / forge-web 应为 healthy

# 4.2 探针
curl -fsS http://127.0.0.1:8081/livez && echo OK-edge
curl -fsS http://127.0.0.1/ -o /dev/null -w '%{http_code}\n'   # forge-web 200

# 4.3 公钥一致性（最关键——证明私钥随库迁来且 KEK 能解）
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose master
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose edge_lease
# 输出必须与旧服务器导出 **逐字节一致**；不一致 = 立即停止，检查 .env 的 KEK 与 DB 恢复
```

4.4 登录后台（`http://<新IP>`），核对：客户列表、产品列表、**License 总数与旧库一致**、审计日志可见历史记录。
4.5 试签发：对测试客户签一张离线 License → 在任一消费方产品（或 `forge-verify offline <blob>`）验证可激活。
4.6 edge 真激活：对测试部署签一张**在线**短码，从外网执行激活，确认拿到租约。

## 5. 割接（流量切换）

### 域名时代（标准路径）
1. 提前 24–48 小时把许可域名 DNS TTL 降到 300s。
2. 验证清单全过后，把 A 记录切到新服务器 IP。
3. **旧服务器保持运行 ≥ 72 小时**（部分解析器无视 TTL）；期间观察旧机 8081 访问日志归零。
4. 可选加固：旧机起一个 nginx 把 8081/80 反代回源到新 IP，再多保几天。

### IP 时代（当前过渡态）
1. 新机验证全过后，逐个更新各消费方产品部署的 `*_FORGE_EDGE_URL` 为新 IP 并重启对应组件。
2. 更新期间在线客户依赖**租约宽限期**继续运行（SDK 缓存的签名租约在 grace_until 前有效）——割接窗口务必小于最短宽限期。
3. 全部产品确认切换后，旧机再保留 72 小时观察。
4. 若有客户长期联系不上：按救援路径补发**离线 `.forge`**（双轨互为灾备）。

## 6. 旧服务器下线

- 访问日志连续 72h 归零 + 全部验证项复核后：`docker compose down`。
- 旧机磁盘上的 `volumes/` 与 `.env` **安全擦除**（`shred`/全盘加密销毁），不要带 KEK 退还云厂商。
- 最后一份终备份加密归档（异地 + 离线各一份，对齐 backup-recovery.md 3-2-1）。

## 7. 回滚

割接后发现异常：把 DNS 切回旧 IP（或产品 env 改回旧 IP）即回滚——旧服务器一直在线就是回滚方案本身。**注意**：回滚后新机上已签发的 License 会留在新库，回滚前先在新机导出增量（后台审计页核对割接窗口内的签发记录，逐张在旧机重签）。

## 8. 换域名（与换服务器解耦，摘要）

按 `00-Global/licensing.md` [2026-06-11] §D：新旧域名双轨并行 → （SDK steering 能力上线后）经签名租约下发新端点 → 旧域名 301/代理保留以年计 → 旧许可域名**永不释放注册**。

## 9. 演练要求

对齐 backup-recovery.md：**每季度**至少做一次"备份 → 异机恢复 → 验证清单 4.1–4.6"演练（可用任意临时 VM，不割接）。第一次正式迁移前必须先完整演练一遍。

---

## 附录 A：纯手动迁移步骤（不使用脚本，逐条命令）

> 脚本（第 2/3 节）只是把下面的命令固化；任何一步想自己掌控，按本附录手敲。所有命令都在**部署目录**（`docker-compose.yaml` 与 `.env` 所在目录）执行。

### A.1 旧服务器：手动备份

```bash
cd <部署目录>

# ① 确认两把 KEK 在场（输出不能为空、不能是 #REPLACE_ME#）
grep -E '^(FORGE_FIELD_ENCRYPTION_KEY|FORGE_EDGE_KEK)=' .env

# ② 正式割接前冻结写入（演练可跳过本步）：只停应用层，postgres/redis 不停
docker compose stop forge-api forge-edge forge-worker forge-scheduler forge-web

# ③ 导出数据库（-Fc 自定义格式，含签名私钥密文、License、租约、审计全部数据）
docker compose exec -T postgres pg_dump -U forge_app -d forge_main -Fc > forge_main.dump
#    ↑ 用户名/库名若在 .env 改过，以 .env 的 DATABASE_USERNAME / DATABASE_NAME 为准

# ④ 打包持久化卷
tar czf storage.tar.gz -C volumes storage          # 文件存储（License 文件等）
tar czf redis.tar.gz   -C volumes redis            # 缓存+队列（可选，建议带上）

# ⑤ 复制 .env（最敏感文件：两把 KEK 在里面）
cp .env env-backup && chmod 600 env-backup

# ⑥ 生成校验和并总打包
shasum -a 256 forge_main.dump storage.tar.gz redis.tar.gz env-backup > SHA256SUMS   # Linux 用 sha256sum
tar czf forge-migration-manual.tar.gz forge_main.dump storage.tar.gz redis.tar.gz env-backup SHA256SUMS
chmod 600 forge-migration-manual.tar.gz
rm forge_main.dump storage.tar.gz redis.tar.gz env-backup SHA256SUMS

# ⑦ 恢复旧服务器运行（割接完成前旧机必须在线）
docker compose up -d

# ⑧ 传输到新服务器（只走加密通道）
scp forge-migration-manual.tar.gz user@<新服务器IP>:/opt/
```

### A.2 新服务器：手动恢复

```bash
# ① 前置：装 Docker + Compose、放行安全组 80/8081、解压部署包、镜像仓库登录、NTP 开启
docker compose version && timedatectl | grep -i ntp

cd <新部署目录>

# ② 解开备份并校验
mkdir -p /opt/forge-restore && tar xzf /opt/forge-migration-manual.tar.gz -C /opt/forge-restore
cd /opt/forge-restore && sha256sum -c SHA256SUMS && cd -      # 校验失败立即停止

# ③ 落位 .env 与卷（确认 volumes/postgres 为空——全新机器才允许恢复）
cp /opt/forge-restore/env-backup .env && chmod 600 .env
mkdir -p volumes
tar xzf /opt/forge-restore/storage.tar.gz -C volumes
tar xzf /opt/forge-restore/redis.tar.gz   -C volumes

# ④ 拉镜像，先只起 postgres（首启自动执行 init/01-roles-and-audit.sh：建受限 edge 角色 + 审计表 REVOKE）
docker compose pull
docker compose up -d postgres
watch -n2 'docker compose exec -T postgres pg_isready'        # ready 后 Ctrl-C

# ⑤ 恢复数据库
docker compose exec -T postgres pg_restore -U forge_app -d forge_main \
  --clean --if-exists --no-owner < /opt/forge-restore/forge_main.dump

# ⑥ 起全栈并等健康
docker compose up -d
watch -n3 'docker compose ps'                                  # forge-api/edge/web 均 healthy 后 Ctrl-C

# ⑦ 清理中转副本
rm -rf /opt/forge-restore /opt/forge-migration-manual.tar.gz
```

### A.3 手动验证（等同第 4 节，必须全过）

```bash
docker compose ps
curl -fsS http://127.0.0.1:8081/livez
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose master
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose edge_lease
# ↑ 两段公钥与旧服务器输出逐字节比对；然后登录后台核对 License 总数、试签发一张离线票、外网打一次在线激活
```

### A.4 手动割接 / 回滚

与第 5/7 节完全一致（割接是 DNS 或产品 env 层面的动作，本就无脚本）：域名时代切 A 记录、IP 时代逐产品改 `*_FORGE_EDGE_URL`；旧机保 72h 即天然回滚方案。
