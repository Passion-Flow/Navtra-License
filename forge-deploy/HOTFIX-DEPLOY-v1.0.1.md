# 云 Forge 热修部署 v1.0.1（删除/吊销 License 立即锁定客户端）

> 修复内容：① forge-edge 把软删除的 License 也当吊销（删除/吊销现在都会在下次 phone-home 锁定已激活的在线客户端）；② Verifier SDK 区分"权威拒绝→立即锁"与"网络故障→宽限"。代码已在 GitHub `main`，深度测试全过（删除/吊销→edge 返回 `LICENSE_REVOKED`，正常→200 无回归）。
>
> 为什么在服务器上构建：云服务器是 amd64，本机是 arm64 Mac，本地模拟 amd64 构建 pip 不稳。**在 amd64 服务器原生构建又快又稳**，且符合"每架构原生构建"规则。

## 在云服务器（118.89.84.188）执行

```bash
# 1) 拉取最新代码（含修复）
cd ~/Navtra-License 2>/dev/null || git clone https://github.com/Passion-Flow/Navtra-License.git ~/Navtra-License && cd ~/Navtra-License
git fetch origin && git checkout main && git pull        # 应包含 commit 7b3adfb

# 2) 原生构建 amd64 镜像，打 v1.0.1（不覆盖已发布的 v1.0.0）
cd Project-source
REG=crpi-ew8juv9423tvogc4.cn-hongkong.personal.cr.aliyuncs.com/navtra-mirror
docker build -f forge-server/Dockerfile -t $REG/forge-api:v1.0.1 .

# 3)（可选）推 ACR 留存版本——其它机器/多架构以后补
docker push $REG/forge-api:v1.0.1

# 4) 用新镜像滚动更新运行中的栈（api/edge/worker/scheduler 共用同一镜像）
cd ~/install-forge          # 你当前 docker compose 部署目录（docker ps 显示 install-forge-*）
export FORGE_TAG=v1.0.1     # 或编辑 .env 把 FORGE_TAG 改成 v1.0.1（持久化）
docker compose up -d forge-api forge-edge forge-worker forge-scheduler

# 5) 验证（公钥不变、edge 健康）
docker compose ps                                  # forge-api / forge-edge 应 healthy
docker exec install-forge-forge-api-1 forge keys export-public --purpose master   # 应与之前一致
curl -fsS http://127.0.0.1:8081/livez && echo OK
```

## 部署后验证"删除→锁定"

1. OpenRelay 已在线激活的情况下，在 Forge 后台**删除**（或吊销）那张 License。
2. 等 OpenRelay 复验周期（现已改为 **30 秒**）。
3. OpenRelay 应转入锁定态（前台显示"需要激活许可证."）。

## 回滚

```bash
cd ~/install-forge && export FORGE_TAG=v1.0.0 && docker compose up -d forge-api forge-edge forge-worker forge-scheduler
```
旧 v1.0.0 镜像仍在 ACR，一条命令切回。

## 注意

- 这是**热修单机部署**；正式发版时按 `migration/` 与三交付物规范做完整多架构（amd64+arm64）构建。
- KEK / 数据库不动，无需备份恢复（仅换镜像）。
- 本机 Mac 上的 `forge-local` 开发栈已先行验证为修复版（fixtest 镜像），可作参照。
