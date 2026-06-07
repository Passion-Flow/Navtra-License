#!/bin/bash
# ==================================================================================================
# generate-image-repo-secret-docker.sh   (use when your GitLab runner / target is DOCKER-based)
#
# Logs the host's Docker daemon into your private registry (Harbor) so the runner can push/pull
# Forge images. Credentials are stored in ~/.docker/config.json. In GitLab CI, prefer the masked
# CI variable REGISTRY_PASSWORD over passing the password on the command line.
#
# Usage:
#   ./generate-image-repo-secret-docker.sh <username> <password> <registry-url>
#   ./generate-image-repo-secret-docker.sh robot$forge 'S3cr3t' harbor.intra.example.com
# ==================================================================================================
set -euo pipefail

PROJECT_NAME="forge"

if [ "$#" -lt 3 ]; then
  echo "How to use: $0 <username> <password> <registry-url>"
  exit 1
fi

USERNAME="$1"; PASSWORD="$2"; REGISTRY="$3"

printf '%s' "$PASSWORD" | docker login "$REGISTRY" --username "$USERNAME" --password-stdin

echo "✅ Logged in to '$REGISTRY' as '$USERNAME' (creds in ~/.docker/config.json)."
