#!/usr/bin/env bash
# Idempotent. SeaweedFS needs the bucket created via the S3 API.
set -euo pipefail
: "${S3_ACCESS_KEY:=lakehouse}"; : "${S3_SECRET_KEY:=lakehouse-local-secret}"
: "${S3_BUCKET:=lakehouse}"; : "${S3_ENDPOINT_HOST:=http://localhost:8333}"
export AWS_ACCESS_KEY_ID=$S3_ACCESS_KEY AWS_SECRET_ACCESS_KEY=$S3_SECRET_KEY AWS_DEFAULT_REGION=us-east-1
if aws --endpoint-url "$S3_ENDPOINT_HOST" s3 ls "s3://$S3_BUCKET" >/dev/null 2>&1; then
  echo "bucket s3://$S3_BUCKET already exists"
else
  aws --endpoint-url "$S3_ENDPOINT_HOST" s3 mb "s3://$S3_BUCKET"
  echo "created s3://$S3_BUCKET"
fi
