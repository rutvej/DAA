#!/bin/bash
set -e

# Load environment variables if available
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

PROJECT_ID=${PROJECT_ID:-"my-daa-project"}
REGION=${REGION:-"us-central1"}

echo "=== Building and pushing container images ==="
gcloud builds submit --tag gcr.io/$PROJECT_ID/daa-backend-api ../app/backend-api
gcloud builds submit --tag gcr.io/$PROJECT_ID/daa-python-agent ../app/python-agent

echo "=== Running Terraform ==="
terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="region=$REGION" \
  -var="gemini_api_key=$GEMINI_API_KEY" \
  -var="gitlab_private_token=$GITLAB_PRIVATE_TOKEN" \
  -auto-approve

echo "=== Deployment Completed Successfully ==="
