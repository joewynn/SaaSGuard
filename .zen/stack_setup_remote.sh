#!/usr/bin/env bash
# zenml/stack_setup_remote.sh

set -euo pipefail

echo "=== Registering Remote Production Stack (Railway) ==="

BUCKET_NAME="practical-satchel-6-e2hfi"
ENDPOINT_URL="https://t3.storageapi.dev"

# 1️⃣ Register artifact store (idempotent)
echo "Registering Railway Bucket as Artifact Store..."
if ! zenml artifact-store describe railway_bucket &>/dev/null; then
  zenml artifact-store register railway_bucket \
    --flavor=s3 \
    --path="s3://${BUCKET_NAME}" \
    --client_kwargs='{"endpoint_url": "'${ENDPOINT_URL}'", "verify": false}'
else
  echo "⚠️  Artifact store 'railway_bucket' already exists, skipping..."
fi

# 2️⃣ Register stack (idempotent) — uses the local_orchestrator registered in stack_setup.sh
echo "Creating/verifying production stack..."
if ! zenml stack describe saasguard_production &>/dev/null; then
  zenml stack register saasguard_production \
    --orchestrator=local_orchestrator \
    --artifact-store=railway_bucket
else
  echo "⚠️  Stack 'saasguard_production' already exists, skipping..."
fi

# 4️⃣ Activate stack
zenml stack set saasguard_production

echo "✅ Remote stack setup completed!"
echo ""
zenml stack describe
zenml status