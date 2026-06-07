#!/bin/bash
# ==================================================================================================
# generate-image-repo-secret.sh
#
# Creates the Kubernetes imagePullSecret that lets Forge pods pull images from a PRIVATE registry
# (e.g. an internal Harbor). The secret name follows the project name:  forge-image-repo-secret
# Reference it from Helm values:  imagePullSecrets: [{ name: forge-image-repo-secret }]
#
# Usage:
#   ./generate-image-repo-secret.sh <username> <password> <k8s-namespace> [registry-url]
#
# Example (internal Harbor):
#   ./generate-image-repo-secret.sh robot$forge 'S3cr3t' forge https://harbor.intra.example.com
# Example (Aliyun ACR):
#   ./generate-image-repo-secret.sh Passion-Flow 'pass' forge \
#       https://crpi-ew8juv9423tvogc4.cn-hongkong.personal.cr.aliyuncs.com
# ==================================================================================================
set -euo pipefail

PROJECT_NAME="forge"                       # <-- the project's slug; secret = <PROJECT_NAME>-image-repo-secret
SECRET_NAME="${PROJECT_NAME}-image-repo-secret"

if [ "$#" -lt 3 ]; then
  echo "How to use: $0 <username> <password> <k8s-namespace> [registry-url]"
  echo "Example:    $0 myuser mypass forge https://harbor.intra.example.com"
  exit 1
fi

USERNAME="$1"
PASSWORD="$2"
NAMESPACE="$3"
REGISTRY="${4:-https://index.docker.io/v1/}"
OUTPUT_FILE="./config.json"

AUTH=$(printf '%s:%s' "$USERNAME" "$PASSWORD" | base64 | tr -d '\n')

cat > "$OUTPUT_FILE" <<EOF
{
  "auths": {
    "$REGISTRY": {
      "auth": "$AUTH"
    }
  }
}
EOF

echo "Generated docker config: $OUTPUT_FILE"

# Replace the secret if it already exists (idempotent).
kubectl -n "$NAMESPACE" delete secret "$SECRET_NAME" --ignore-not-found
kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
  --from-file=.dockerconfigjson="$OUTPUT_FILE" \
  --type=kubernetes.io/dockerconfigjson

rm -f "$OUTPUT_FILE"

echo
echo "✅ Created imagePullSecret '$SECRET_NAME' in namespace '$NAMESPACE'."
echo "   Now set it in Helm values.yaml:"
echo "     imagePullSecrets:"
echo "       - name: $SECRET_NAME"
