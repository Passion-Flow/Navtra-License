#!/usr/bin/env bash
# Forge 服务器迁移 — 旧服务器备份脚本
# 用法（在 docker-compose 部署目录内执行，即 docker-compose.yaml 与 .env 所在目录）：
#   bash migration/Scripts/backup-forge.sh            # 热备份（服务不停，适合演练）
#   bash migration/Scripts/backup-forge.sh --final    # 终备份（停应用层冻结写入，适合正式割接）
# 产物：forge-migration-<时间戳>.tar.gz（含 DB dump / storage / redis / .env / 校验清单）
set -euo pipefail

FINAL=0
[[ "${1:-}" == "--final" ]] && FINAL=1

[[ -f docker-compose.yaml && -f .env ]] || {
  echo "✗ 请在 Forge 的 docker-compose 部署目录内执行（需存在 docker-compose.yaml 与 .env）"; exit 1; }

# 读取 .env（仅取本脚本需要的字段）
DB_USER=$(grep -E '^DATABASE_USERNAME=' .env | cut -d= -f2- || true)
DB_NAME=$(grep -E '^DATABASE_NAME=' .env | cut -d= -f2- || true)
DB_USER=${DB_USER:-forge_app}
DB_NAME=${DB_NAME:-forge_main}

# KEK 在场校验 —— 没有这两把钥匙，备份恢复后私钥永远解不开
for key in FORGE_FIELD_ENCRYPTION_KEY FORGE_EDGE_KEK; do
  val=$(grep -E "^${key}=" .env | cut -d= -f2- || true)
  if [[ -z "$val" || "$val" == "#REPLACE_ME#" ]]; then
    echo "✗ .env 中 ${key} 缺失或未填——该备份无法用于恢复，先修复 .env"; exit 1
  fi
done

STAMP=$(date +%Y%m%d-%H%M%S)
WORK="forge-migration-${STAMP}"
mkdir -p "${WORK}"

if [[ $FINAL -eq 1 ]]; then
  echo "→ 终备份模式：停止应用层（postgres/redis 保持运行）冻结写入…"
  docker compose stop forge-api forge-edge forge-worker forge-scheduler forge-web
fi

echo "→ 1/4 导出 PostgreSQL（pg_dump -Fc，含签名私钥的加密密文与全部业务数据）…"
docker compose exec -T postgres pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc \
  > "${WORK}/forge_main.dump"

echo "→ 2/4 打包持久化卷（storage / redis）…"
[[ -d volumes/storage ]] && tar czf "${WORK}/storage.tar.gz" -C volumes storage || echo "  （无 storage 卷，跳过）"
if [[ -d volumes/redis ]]; then
  docker compose exec -T redis sh -c 'redis-cli -a "$(printenv REDIS_PASS 2>/dev/null || true)" BGSAVE' >/dev/null 2>&1 || true
  tar czf "${WORK}/redis.tar.gz" -C volumes redis
else
  echo "  （无 redis 卷，跳过）"
fi

echo "→ 3/4 复制 .env（含两把 KEK——整个备份里最敏感的文件）…"
cp .env "${WORK}/.env"
chmod 600 "${WORK}/.env"

echo "→ 4/4 生成校验清单并打包…"
( cd "${WORK}" && shasum -a 256 * .env 2>/dev/null || sha256sum * .env 2>/dev/null ) \
  > "${WORK}/SHA256SUMS" || true
tar czf "${WORK}.tar.gz" "${WORK}"
rm -rf "${WORK}"
chmod 600 "${WORK}.tar.gz"

if [[ $FINAL -eq 1 ]]; then
  echo "→ 重新拉起应用层（旧服务器在割接完成前必须保持在线）…"
  docker compose up -d
fi

echo ""
echo "✓ 备份完成：${WORK}.tar.gz"
echo "  下一步：scp 到新服务器，并在新服务器执行 restore-forge.sh（见 migration/README-CN.md 第 3 节）"
echo "  ⚠ 该文件含 KEK 与全部许可数据：仅经加密通道传输（scp/sftp），落地后尽快删除中转副本"
