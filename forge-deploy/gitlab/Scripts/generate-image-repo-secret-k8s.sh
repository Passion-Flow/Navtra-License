#!/bin/bash
# ==================================================================================================
# generate-image-repo-secret-k8s.sh   (use when your GitLab pipeline DEPLOYS to Kubernetes)
#
# Creates the Kubernetes imagePullSecret so the cluster can pull Forge images from your private
# registry (Harbor). Secret name follows the project: forge-image-repo-secret
# Then reference it in Helm values: imagePullSecrets: [{ name: forge-image-repo-secret }]
#
# Usage:
#   ./generate-image-repo-secret-k8s.sh <username> <password> <k8s-namespace> [registry-url]
#   ./generate-image-repo-secret-k8s.sh robot$forge 'S3cr3t' forge https://harbor.intra.example.com
# ==================================================================================================
set -euo pipefail

PROJECT_NAME="forge"
SECRET_NAME="${PROJECT_NAME}-image-repo-secret"

if [ "$#" -lt 3 ]; then
  echo "How to use: $0 <username> <password> <k8s-namespace> [registry-url]"
  exit 1
fi

USERNAME="$1"; PASSWORD="$2"; NAMESPACE="$3"; REGISTRY="${4:-https://index.docker.io/v1/}"
OUTPUT_FILE="./config.json"
AUTH=$(printf '%s:%s' "$USERNAME" "$PASSWORD" | base64 | tr -d '\n')

cat > "$OUTPUT_FILE" <<EOF
{ "auths": { "$REGISTRY": { "auth": "$AUTH" } } }
EOF

kubectl -n "$NAMESPACE" delete secret "$SECRET_NAME" --ignore-not-found
kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
  --from-file=.dockerconfigjson="$OUTPUT_FILE" \
  --type=kubernetes.io/dockerconfigjson
rm -f "$OUTPUT_FILE"

echo "✅ Created imagePullSecret '$SECRET_NAME' in namespace '$NAMESPACE'."
