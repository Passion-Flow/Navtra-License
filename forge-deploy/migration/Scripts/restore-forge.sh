#!/usr/bin/env bash
# Forge 服务器迁移 — 新服务器恢复脚本
# 前置：新服务器已装 Docker + Compose 插件；已解压 Forge 部署包并 cd 进部署目录
#       （docker-compose.yaml 所在目录）；已配好镜像仓库登录（Scripts/generate-image-repo-secret.sh）。
# 用法：bash migration/Scripts/restore-forge.sh /path/to/forge-migration-<时间戳>.tar.gz
set -euo pipefail

ARCHIVE="${1:-}"
[[ -n "$ARCHIVE" && -f "$ARCHIVE" ]] || { echo "用法: $0 <forge-migration-*.tar.gz>"; exit 1; }
[[ -f docker-compose.yaml ]] || { echo "✗ 请在 Forge 的 docker-compose 部署目录内执行"; exit 1; }
if [[ -d volumes/postgres && -n "$(ls -A volumes/postgres 2>/dev/null)" ]]; then
  echo "✗ volumes/postgres 非空——为防误覆盖，请确认这是全新服务器后手动清空再执行"; exit 1
fi

echo "→ 1/6 解包备份…"
WORK=$(mktemp -d)
tar xzf "$ARCHIVE" -C "$WORK"
SRC=$(find "$WORK" -maxdepth 1 -type d -name "forge-migration-*" | head -1)
[[ -n "$SRC" ]] || { echo "✗ 备份包结构不对"; exit 1; }

echo "→ 2/6 校验完整性（SHA256）…"
( cd "$SRC" && (shasum -a 256 -c SHA256SUMS 2>/dev/null || sha256sum -c SHA256SUMS 2>/dev/null) ) \
  || { echo "✗ 校验失败——备份可能损坏，停止恢复"; exit 1; }

echo "→ 3/6 落位 .env（两把 KEK 必须与旧服务器逐字一致）与持久化卷…"
cp "$SRC/.env" .env && chmod 600 .env
mkdir -p volumes
[[ -f "$SRC/storage.tar.gz" ]] && tar xzf "$SRC/storage.tar.gz" -C volumes
[[ -f "$SRC/redis.tar.gz"   ]] && tar xzf "$SRC/redis.tar.gz"   -C volumes

echo "→ 4/6 拉镜像并单独启动 PostgreSQL（首启会执行 init 角色脚本）…"
docker compose pull
docker compose up -d postgres
echo -n "   等待 postgres 就绪"
for i in $(seq 1 60); do
  docker compose exec -T postgres pg_isready -q && break || { echo -n "."; sleep 2; }
done; echo ""

DB_USER=$(grep -E '^DATABASE_USERNAME=' .env | cut -d= -f2-); DB_USER=${DB_USER:-forge_app}
DB_NAME=$(grep -E '^DATABASE_NAME=' .env | cut -d= -f2-);     DB_NAME=${DB_NAME:-forge_main}

echo "→ 5/6 恢复数据库（pg_restore --clean）…"
docker compose exec -T postgres pg_restore -U "${DB_USER}" -d "${DB_NAME}" \
  --clean --if-exists --no-owner < "$SRC/forge_main.dump"

echo "→ 6/6 启动全栈…"
docker compose up -d
echo -n "   等待 forge-api 健康"
for i in $(seq 1 60); do
  state=$(docker compose ps --format '{{.Name}} {{.Health}}' 2>/dev/null | grep forge-api | awk '{print $2}')
  [[ "$state" == "healthy" ]] && break || { echo -n "."; sleep 3; }
done; echo ""

rm -rf "$WORK"
echo ""
echo "✓ 恢复完成。请立即执行 migration/README-CN.md 第 4 节【验证清单】（健康检查 / 登录 / 公钥比对 / 试签发 / edge 真激活）"
echo "  验证全过之前，不要切换任何流量，不要关停旧服务器。"
