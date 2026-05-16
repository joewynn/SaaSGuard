#!/usr/bin/env bash
# zenml/stack_setup.sh
# Run once: bash zenml/stack_setup.sh
# Registers a local development stack with MLflow experiment tracking.

set -euo pipefail

echo "Registering ZenML stack components..."

# 1. Artifact store: local filesystem (models/, pipelines/artifacts/)
zenml artifact-store register local_store \
  --flavor=local \
  --path="$(pwd)/pipelines/artifacts"

# 2. Orchestrator: local (runs steps in the current Python process)
zenml orchestrator register local_orchestrator \
  --flavor=local

# 3. Assemble the stack (metrics logged via ZenML server, no MLflow needed)
zenml stack register saasguard_local \
  --artifact-store=local_store \
  --orchestrator=local_orchestrator

# 5. Set as the active stack
zenml stack set saasguard_local

echo "Stack registered and activated."
zenml stack describe