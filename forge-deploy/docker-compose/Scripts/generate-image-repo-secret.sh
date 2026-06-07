#!/bin/bash
# ==================================================================================================
# generate-image-repo-secret.sh  (docker-compose variant)
#
# docker-compose deployments do NOT use a Kubernetes Secret — the host's Docker daemon pulls images
# using credentials stored in ~/.docker/config.json. This script logs the host into your PRIVATE
# registry (e.g. an internal Harbor) so `docker compose pull` / `up` can fetch forge-api / forge-web.
#
# Usage:
#   ./generate-image-repo-secret.sh <username> <password> <registry-url>
#
# Example (internal Harbor):
#   ./generate-image-repo-secret.sh robot$forge 'S3cr3t' harbor.intra.example.com
# Example (Aliyun ACR):
#   ./generate-image-repo-secret.sh Passion-Flow 'pass' \
#       crpi-ew8juv9423tvogc4.cn-hongkong.personal.cr.aliyuncs.com
# ==================================================================================================
set -euo pipefail

PROJECT_NAME="forge"          # project slug (kept for parity with the k8s variant / Agent convention)

if [ "$#" -lt 3 ]; then
  echo "How to use: $0 <username> <password> <registry-url>"
  echo "Example:    $0 myuser mypass harbor.intra.example.com"
  exit 1
fi

USERNAME="$1"
PASSWORD="$2"
REGISTRY="$3"

printf '%s' "$PASSWORD" | docker login "$REGISTRY" --username "$USERNAME" --password-stdin

echo
echo "✅ Logged in to '$REGISTRY' as '$USERNAME' (creds saved in ~/.docker/config.json)."
echo "   Set REGISTRY=$REGISTRY in your .env, then run:  docker compose pull && docker compose up -d"
