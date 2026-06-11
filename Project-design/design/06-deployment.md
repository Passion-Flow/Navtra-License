# 部署设计：Forge

> 第二步设计文档 6/6。约定来源：`Project-Docs/04-Deployment/{overview,docker-compose,helm,gitlab,multi-platform-deploy,k8s-security,k8s-secrets}.md` + `00-Global/cross-platform.md`。
> 三种交付物全产出（用户拍板严守）。核心特殊点：**公网/内网网络隔离**保证私钥永不上公网攻击面。

## 1. 镜像规划（5 镜像）

| 镜像 | 角色 | 网络面 | 源 | Dockerfile | 私钥 |
|------|------|--------|----|-----------|------|
| `forge-api` | FastAPI 签发核心 + 管理后端 | **内网** | `forge-server/` | `Dockerfile.api` | **持有** |
| `forge-edge` | 公网在线校验中继 | **公网** | `forge-server/` | `Dockerfile.edge` | 无 |
| `forge-worker` | Celery worker | 内网 | `forge-server/` | `Dockerfile.worker` | 无 |
| `forge-scheduler` | Celery beat（单实例）| 内网 | `forge-server/` | `Dockerfile.scheduler` | 无 |
| `forge-web` | nginx + Admin SPA | 内网 | `forge-admin/` | `Dockerfile` | 无 |

- api/edge/worker/scheduler 共享 `forge-server/` + 同 base 层，不同 ENTRYPOINT 共享缓存层。
- 镜像 tag `$CI_COMMIT_REF_SLUG-$CI_COMMIT_SHORT_SHA`（禁 latest）。

## 2. multi-arch
- buildx 双架构 `linux/amd64,linux/arm64`（禁单架构），CI emit ≥2 manifest，`imagetools inspect` 验证。
- Dockerfile `FROM --platform=$BUILDPLATFORM` + `ARG TARGETARCH`；`CMD/ENTRYPOINT` 不硬编码 arch。
- **限制**：Oracle DB 无 arm64 → arm64 部署默认 postgres。macOS 仅开发；Windows 开发 WSL2。

## 3. 三套交付物（`forge-deploy/`）

### 3.1 docker-compose（`forge-deploy/docker/`）
- 四件套 `docker-compose.yaml` + `.env.example` + `.gitignore` + `README.md` + `envs/`（core-services/databases/caches/object-storage/infrastructure）。
- dify 风格：YAML anchor `x-shared-app-env: &shared-app-env`（含 `env_file` + `restart: always`）；`env_file` 分文件 + 可选 `required:false`；scheduler `deploy:{replicas:1}` 注释「必须单实例」。
- `.gitignore`：`*.env` + `!*.env.example`；敏感默认 `#REPLACE_ME#`。
- 自托管 db/redis 有 healthcheck；app `depends_on: service_healthy`；健康 `/api/v1/health`。

### 3.2 Helm（`forge-deploy/helm/`）
- `Chart.yaml` + 单 `values.yaml`（无 example）+ `templates/`（按组件 `api/ edge/ worker/ scheduler/ web/ shared/`；`_helper.tpl`+`ingress.yaml`+`NOTES.txt` 在根）。
- values dify 风格：`###` 分区标题 / 每组件自带 `image:` 块 / `resources` 展开式 / 枚举字段 `# The X type support: a,b,c` / 敏感 `"#REPLACE_ME#"` / 外部凭证 inline+`externalSecretName` 双路径。
- scheduler 模板硬编码 `replicas:1 + strategy:Recreate`。
- 无 bitnami 子 chart（db/cache/storage 均客户自有实例）。

### 3.3 GitLab（`forge-deploy/gitlab/`）
- `.gitlab-ci.yml` 顶层仅 `stages + variables + include`；job 拆 `pipelines/{lint,test,build,scan,publish,deploy-compose,deploy-helm,verify}.yml`。
- build 阶段 5 个 build job（forge-api/edge/worker/scheduler/web 各一）；`.build-base` + `extends`。
- 凭证仅 CI/CD Variables；prod deploy `when:manual`；scan 阻塞 publish，publish 失败阻塞 deploy。

## 4. 网络拓扑（核心：私钥不上公网）

### 4.1 docker-compose 双网络
```yaml
networks:
  public:   { driver: bridge }          # 宿主发布端口
  internal: { internal: true }          # 无出网/无宿主路由
services:
  forge-edge:  { networks: [public, internal], ports: ["18080:8081","18443:8443"] }  # 唯一公网
  forge-web:   { networks: [public],   ports: ["13000:80"] }   # 厂商内网访问（生产可仅内网）
  forge-api:   { networks: [internal] }                        # 无 ports，宿主不可达
  forge-worker:{ networks: [internal] }
  forge-scheduler:{ networks: [internal], deploy:{replicas:1} }
  postgres/redis/minio: { networks: [internal] }               # 禁公网端口
```
- edge 是唯一既在 public 又能经 internal 到达 forge-api 的组件；私钥 env/文件仅 forge-api 消费，任何 edge/web 可达的 env_file 都不含私钥。

### 4.2 Helm NetworkPolicy（default-deny）
- `templates/shared/networkpolicy.yaml`：全局 default-deny ingress+egress（DNS 53 放行）。
- `ingress.yaml` **只路由 forge-edge（+ 内网访问的 forge-web）**，**绝不含 forge-api**。
- `forge-api` NetworkPolicy：Ingress **仅允许 `component: edge` pod**（无 ingress-nginx、无其他组件）；Egress 仅 postgres/redis。
- edge 在 ingress 层加 WAF（ModSecurity + OWASP CRS）+ 限流 + 安全头。
- 全 pod：securityContext runAsNonRoot(UID 10001)/readOnlyRootFilesystem/drop ALL caps/seccomp RuntimeDefault + PSS restricted（forge-api 尤甚）。

## 5. 扩缩容
- HPA：forge-edge 按 CPU/RPS（公网校验是热点）；forge-api 适度；forge-web 静态低。
- 资源基线：api 1c/1Gi、edge 1c/512Mi（可水平扩）、worker 2c/2Gi、scheduler 0.5c/512Mi（单实例不扩）、web 0.2c/256Mi。
- PDB + 反亲和 + 优雅停机；scheduler 永远单实例。

## 6. 安全
- NetworkPolicy（§4.2）+ securityContext + PSS restricted。
- 私钥**绝不**普通 values 字段：用 **Vault Agent Injector（HSM-backed，仅注入 forge-api pod）** 或离线介质；ESO/Sealed-Secrets 为次选；values 用 `externalSecretName` + `secretKeyRef`，默认 `"#REPLACE_ME#"`。
- 私钥 Secret 仅挂 forge-api，绝不挂 edge/web/worker/scheduler。
- 证书/私钥不进 git；secret 扫描 CI 阻塞。

## 7. 备份 / 灾备（最严）
- RPO ≤1h / RTO ≤4h；DB 全量日 + WAL 时；3-2-1。
- **私钥专项**：加密备份 + 异地冷备 + 离线介质；KEK 与密文分离；季度恢复演练（含"私钥灾难重建"Runbook）。
- K8s：VolumeSnapshot + Velero；恢复 Runbook `forge-deploy/runbook/rollback.md` + `key-recovery.md`。

## 8. 多平台部署
- 生产 Linux amd64/arm64（Tier1）；Windows Server Linux 容器/WSL2（Tier2 复用 Linux 镜像）；Windows 原生/arm64（Tier3 按需）。
- `.gitattributes` LF（`.sh` lf / `.bat .ps1` crlf）；全 UTC + UTF-8。

## 9. 监控告警
- 三探针 `/livez /readyz /healthz` + `/metrics`；OTel Data Push 可配。
- 关键告警：edge 5xx 激增 / seat 超额激增 / 私钥访问异常 / 到期邮件失败 / 备份失败 / forge-api 不可达（edge 退化）。
- 客户产品侧（Verifier SDK）不接 Forge 监控；Forge 仅监控自身签发/校验链路。

## 10. 部署形态说明（呼应用户「公网厂商服务器」选择）
- 单台公网厂商服务器 compose 部署时：**forge-edge 唯一对外**（18080/18443），forge-api/worker/scheduler/db/redis 全在 `internal` 网络、宿主不发布端口；forge-web 仅厂商内网/VPN 访问。
- 这样既满足"客户直连 `域名/公网IP:端口` 校验"，又守住"私钥永不在公网攻击面"。
