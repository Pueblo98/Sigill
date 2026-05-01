#!/usr/bin/env bash
# Restore a Sigil Postgres backup from S3 — used in the quarterly drill.
# See runbooks/backup-restore.md for the full procedure + checklist.
#
# Usage:
#   ./scripts/restore_db.sh <s3-key>
#
# Required env:
#   TARGET_DATABASE_URL   postgresql://user:pass@drill-host:port/dbname
#   S3_BUCKET             e.g. sigil-backups
#   AGE_KEY_FILE          path to age private key (default: ~/.config/sigil/age.key)
#
# Optional env:
#   S3_ENDPOINT           for S3-compatible (R2/B2/Wasabi/MinIO)
#   S3_PROFILE            aws-cli profile name
#
# Exit codes: 0 success; 1 missing arg/env; 2 download; 3 decrypt; 4 restore.

set -euo pipefail

KEY="${1:?usage: restore_db.sh <s3-key>}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL required}"
: "${S3_BUCKET:?S3_BUCKET required}"
AGE_KEY_FILE="${AGE_KEY_FILE:-$HOME/.config/sigil/age.key}"

if [ ! -r "$AGE_KEY_FILE" ]; then
    echo "[restore] AGE_KEY_FILE not readable: $AGE_KEY_FILE" >&2
    exit 1
fi

TMP="$(mktemp -d -t sigil-restore-XXXXXXXX)"
trap 'rm -rf "$TMP"' EXIT

aws_args=(s3 cp)
[ -n "${S3_PROFILE:-}" ]  && aws_args=(--profile "$S3_PROFILE"   "${aws_args[@]}")
[ -n "${S3_ENDPOINT:-}" ] && aws_args=(--endpoint-url "$S3_ENDPOINT" "${aws_args[@]}")

echo "[restore] $(date -u +%FT%TZ) downloading s3://${S3_BUCKET}/${KEY}"
if ! aws "${aws_args[@]}" "s3://${S3_BUCKET}/${KEY}" "$TMP/dump.age"; then
    echo "[restore] FAIL s3 download" >&2
    exit 2
fi

echo "[restore] decrypting"
if ! age -d -i "$AGE_KEY_FILE" -o "$TMP/dump" "$TMP/dump.age"; then
    echo "[restore] FAIL age decrypt" >&2
    exit 3
fi

echo "[restore] applying to $TARGET_DATABASE_URL"
if ! pg_restore \
        --no-owner --no-privileges \
        --clean --if-exists \
        --dbname "$TARGET_DATABASE_URL" \
        "$TMP/dump"; then
    echo "[restore] FAIL pg_restore" >&2
    exit 4
fi

echo "[restore] OK"
echo
echo "[restore] next: spot-check counts and run smoke flow"
echo "  psql \"\$TARGET_DATABASE_URL\" -c \"select count(*) from market_prices;\""
echo "  DATABASE_URL=\"\$TARGET_DATABASE_URL\" \\"
echo "    .venv/Scripts/python.exe scripts/smoke_paper_flow.py"
echo "  # then log the drill in runbooks/backup-restore.md §6"
