#!/usr/bin/env bash
# Daily Postgres backup for Sigil. Cron-driven; safe to run unattended.
# See runbooks/backup-restore.md for the full procedure + cadence.
#
# Required env:
#   DATABASE_URL    postgresql://user:pass@host:port/db
#   S3_BUCKET       e.g. sigil-backups
#   AGE_RECIPIENT   age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#
# Optional env:
#   S3_PREFIX       default: daily
#   S3_ENDPOINT     for S3-compatible (R2/B2/Wasabi/MinIO)
#   S3_PROFILE      aws-cli profile name
#
# Exit codes: 0 success; 1 missing env; 2 dump failure; 3 encrypt failure;
#             4 upload failure.

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL required}"
: "${S3_BUCKET:?S3_BUCKET required}"
: "${AGE_RECIPIENT:?AGE_RECIPIENT required (age1...)}"
S3_PREFIX="${S3_PREFIX:-daily}"

TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
KEY="${S3_PREFIX}/sigil-${TS}.dump.age"

TMP="$(mktemp -t sigil-backup-XXXXXXXX)"
ENC="${TMP}.age"
trap 'rm -f "$TMP" "$ENC"' EXIT

aws_args=(s3 cp)
[ -n "${S3_PROFILE:-}" ]  && aws_args=(--profile "$S3_PROFILE"   "${aws_args[@]}")
[ -n "${S3_ENDPOINT:-}" ] && aws_args=(--endpoint-url "$S3_ENDPOINT" "${aws_args[@]}")

echo "[backup] $(date -u +%FT%TZ) dumping $DATABASE_URL"
if ! pg_dump --format=custom --no-owner --no-privileges -f "$TMP" "$DATABASE_URL"; then
    echo "[backup] FAIL pg_dump" >&2
    exit 2
fi

echo "[backup] encrypting -> $ENC"
if ! age -r "$AGE_RECIPIENT" -o "$ENC" "$TMP"; then
    echo "[backup] FAIL age encrypt" >&2
    exit 3
fi

echo "[backup] uploading -> s3://${S3_BUCKET}/${KEY}"
if ! aws "${aws_args[@]}" "$ENC" "s3://${S3_BUCKET}/${KEY}"; then
    echo "[backup] FAIL s3 upload" >&2
    exit 4
fi

SIZE_BYTES=$(wc -c < "$ENC" | tr -d ' ')
echo "[backup] OK  ${KEY} (${SIZE_BYTES} bytes)"
