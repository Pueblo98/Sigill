# Sigil — DB Backup & Restore Drill

**Owner:** the operator running Sigil in production.
**Scope:** Postgres (`sigil`) database. SQLite paper-only deployments
have a one-line variant at the end.
**Cadence:** daily backups, **quarterly** restore drill.

> Untested backups fail >50% of the time when you actually need them.
> Sigil is money-bearing; trade-history loss = tax problem + recovery
> problem. The drill exists so the 3am-tired version of you doesn't
> have to remember the procedure.
>
> — TODOS.md (TODO-3 origin)

This runbook gives you (1) a one-shot daily backup that's safe to run
unattended via cron, (2) a one-shot restore for the drill, and (3) a
checklist for the quarterly drill itself.

---

## 1. Backup architecture

| Aspect | Choice | Why |
|---|---|---|
| Format | `pg_dump --format=custom` | Compressed, parallel-restorable, schema+data in one file. |
| Encryption | `age` (recipient key from decision 1F) | Reuses the existing age key under `~/.config/sigil/age.key`. `sops` is for structured config; an opaque dump goes through raw `age`. |
| Storage | S3 or any S3-compatible (R2, B2, Wasabi, MinIO) | Pluggable via `S3_ENDPOINT`. |
| Retention | 30 daily + 12 monthly + 4 quarterly | S3 lifecycle policy on the operator side; this runbook doesn't configure it. |
| WAL archiving / PITR | **Out of scope for v1.** | Adds operational surface area; revisit when a single-day RPO is insufficient. |

The flow:

```
Postgres -> pg_dump --format=custom -> *.age (age-encrypted) -> S3
```

A daily logical dump means **RPO ≈ 24h** at worst. Trade history
within the last day is the exposure window. If that's too high, layer
on WAL archiving as a separate slice (own runbook).

---

## 2. Required tooling on the backup host

```bash
# Postgres client
sudo apt-get install postgresql-client    # or: brew install libpq

# age (encryption)
sudo apt-get install age                  # or: brew install age

# AWS CLI v2 (works against any S3-compatible endpoint via --endpoint-url)
# https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
```

The age **recipient public key** lives wherever you keep it (e.g.
`~/.config/sigil/age.recipient`). The matching **identity (private)
key** is `~/.config/sigil/age.key` per `config.SOPS_AGE_KEY_FILE`. Only
the restore host needs the private key; the backup host only needs the
recipient public key.

---

## 3. Daily backup (cron-driven)

`scripts/backup_db.sh` is the entrypoint. It:

1. `pg_dump --format=custom $DATABASE_URL` to a tempfile
2. `age -r $AGE_RECIPIENT` encrypts the tempfile in place
3. `aws s3 cp` uploads to `s3://$S3_BUCKET/$S3_PREFIX/sigil-<UTC-stamp>.dump.age`
4. Removes the tempfile (trap on EXIT)

Required env:

```bash
export DATABASE_URL='postgresql://sigil:sigil@localhost:5432/sigil'
export S3_BUCKET='sigil-backups'
export S3_PREFIX='daily'                                   # optional, default 'daily'
export AGE_RECIPIENT='age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Optional, for non-AWS S3-compatible storage:
export S3_ENDPOINT='https://<account>.r2.cloudflarestorage.com'
export S3_PROFILE='sigil-r2'                               # an aws-cli profile name
```

Manual run:

```bash
./scripts/backup_db.sh
```

systemd timer (Linux):

```ini
# /etc/systemd/system/sigil-backup.service
[Unit]
Description=Sigil daily DB backup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/sigil/backup.env
ExecStart=/opt/sigil/scripts/backup_db.sh
User=sigil
StandardOutput=journal
StandardError=journal

# /etc/systemd/system/sigil-backup.timer
[Unit]
Description=Run sigil-backup daily at 02:07 UTC

[Timer]
OnCalendar=*-*-* 02:07:00 UTC
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now sigil-backup.timer
```

cron (any unix):

```cron
7 2 * * * cd /opt/sigil && /opt/sigil/scripts/backup_db.sh >> /var/log/sigil-backup.log 2>&1
```

The off-minute (02:07) avoids fleet collisions with everyone else's
midnight cron.

### Verifying the daily backup ran

```bash
aws s3 ls s3://$S3_BUCKET/$S3_PREFIX/ | tail -5
# Expect a .dump.age within the last 24h.
```

A simple sanity-check job (also cron-able) is the operator's call.

---

## 4. Restore — used in the quarterly drill

`scripts/restore_db.sh` is the entrypoint. It:

1. `aws s3 cp` downloads the `.dump.age`
2. `age -d -i $AGE_KEY_FILE` decrypts to tempdir
3. `pg_restore --clean --if-exists --no-owner` applies the dump to
   `$TARGET_DATABASE_URL`

Required env:

```bash
export TARGET_DATABASE_URL='postgresql://sigil:sigil@drill-host:5432/sigil_drill'
export S3_BUCKET='sigil-backups'
export AGE_KEY_FILE="$HOME/.config/sigil/age.key"

# Optional:
export S3_ENDPOINT='https://<account>.r2.cloudflarestorage.com'
export S3_PROFILE='sigil-r2'
```

Run:

```bash
./scripts/restore_db.sh daily/sigil-2026-05-01T02-07-00Z.dump.age
```

The S3 key is the only positional arg. The script prints the next
verification step on success.

---

## 5. Quarterly drill — the actual procedure

Goal: confirm the latest backup is restorable on a clean machine and
that the resulting DB passes app smoke. Schedule: first business day
of January / April / July / October. Block ~30 min on the calendar.

### Pre-drill (5 min)

- [ ] Verify the latest backup exists in S3 (last 24h).
- [ ] Verify the age private key is on the drill host (or KMS-style
      retrievable).
- [ ] Provision the drill VM (any small Postgres-capable host;
      `docker run -d --name sigil-drill-pg -p 55432:5432 -e POSTGRES_PASSWORD=drill postgres:16` is fine).

### Drill (15 min)

- [ ] Set env vars (§4).
- [ ] Run `./scripts/restore_db.sh <latest-key>`.
      Expected: `[restore] done` with no errors.
- [ ] Connect and spot-check:
      ```bash
      psql "$TARGET_DATABASE_URL" -c "select count(*) from market_prices;"
      psql "$TARGET_DATABASE_URL" -c "select count(*) from positions;"
      psql "$TARGET_DATABASE_URL" -c "select max(check_time) from source_health;"
      ```
      Compare to production counts from the previous day; any
      delta beyond ~24h of new rows is suspect.
- [ ] Run the in-process smoke against the drill DB:
      ```bash
      DATABASE_URL="$TARGET_DATABASE_URL" \
        .venv/Scripts/python.exe scripts/smoke_paper_flow.py
      ```
      (Note: `Config` is `BaseModel`, not `BaseSettings`. Either edit
      `config.py` for the drill, or use `scripts/smoke_uvicorn.py` as
      a wrapper template that mutates `config` before importing.)
- [ ] Run `pytest -m critical` against the drill DB if you want belt-
      and-suspenders.

### Post-drill (10 min)

- [ ] Append a row to the drill log (§6).
- [ ] Tear down the drill VM (`docker rm -f sigil-drill-pg`).
- [ ] Calendar the next drill on day 1 of the next quarter.

If anything in the drill failed: file a follow-up TODO with the
specific error; do **not** mark the drill green.

---

## 6. Drill log

| Date (UTC) | Backup tested | Restore time | Smoke result | Issues / fixes | Operator |
|---|---|---|---|---|---|
| _e.g. 2026-07-01_ | _e.g. daily/sigil-2026-06-30T02-07-00Z.dump.age_ | _e.g. 4m 12s_ | _green / red_ | _link/notes_ | _name_ |

Append in chronological order. Don't truncate — the trend is the
signal. A drill that took 12 minutes last time and 30 today is itself
a finding.

**First drill (operator-gated):** see TODO-10 in `TODOS.md`. Land it
within 30 days of this runbook shipping.

---

## 7. SQLite paper-only variant

If you're running the paper-only path against `sigil_paper.db`
(decision 1B fallback), the procedure simplifies to:

```bash
# Backup: copy + encrypt
cp sigil_paper.db /tmp/sigil_paper-$(date -u +%Y-%m-%dT%H-%M-%SZ).db
age -r $AGE_RECIPIENT -o /tmp/sigil_paper-*.db.age /tmp/sigil_paper-*.db
aws s3 cp /tmp/sigil_paper-*.db.age s3://$S3_BUCKET/$S3_PREFIX/

# Restore: download + decrypt + run
aws s3 cp s3://$S3_BUCKET/$S3_PREFIX/<key> /tmp/restore.db.age
age -d -i $AGE_KEY_FILE -o /tmp/restore.db /tmp/restore.db.age
DATABASE_URL="sqlite+aiosqlite:///tmp/restore.db" \
  .venv/Scripts/python.exe scripts/smoke_paper_flow.py
```

The drill checklist still applies; just swap the script calls.

---

## 8. Out of scope for v1 (logged for later)

- **WAL archiving + PITR** — RPO < 24h. Significant operational
  surface area; only worth it if a day's loss is unacceptable.
- **Cross-region replication** — bucket-level concern; configure on
  S3 side.
- **Backup encryption key rotation** — age recipient swaps require a
  re-encrypt of the existing dump set.
- **Automated drill** — a CI job that pulls yesterday's backup,
  restores it to ephemeral Postgres, runs smoke. Worth doing once
  manual drills are routine and the drill log shows zero novel
  surprises three quarters in a row.
