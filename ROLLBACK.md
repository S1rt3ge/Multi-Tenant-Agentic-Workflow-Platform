# Rollback And Restore Runbook

This document covers rollback and restore only.

For adjacent procedures:

- use `DEPLOYMENT.md` for forward deployment steps
- use `RELEASE.md` for release preparation and publication flow

This runbook covers two recovery paths:

- production rollback using `docker-compose.prod.yml`
- local packaged runtime rollback using `graphpilot`

Use it when a newly deployed release is unhealthy, regressions are confirmed, or data must be restored from a known-good backup.

## Recovery Goals

1. preserve current data before changing anything else
2. redeploy a known-good application version/tag
3. restore database state only if rollback alone is insufficient
4. verify health, auth, workflow, and analytics paths after recovery

## Required Inputs

- previous known-good git tag, for example `v0.1.2`
- current deployment path or runtime home
- access to the host where Docker Compose is running
- enough disk space for SQL backup files

## Production Rollback

### 1. Capture a safety backup first

From the deployment host:

```bash
mkdir -p backups
ts=$(date -u +"%Y%m%dT%H%M%SZ")
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U platform -d agentic_platform --clean --if-exists \
  > "backups/pre-rollback-${ts}.sql"
```

Optional compressed variant:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U platform -d agentic_platform --clean --if-exists \
  | gzip > "backups/pre-rollback-${ts}.sql.gz"
```

### 2. Confirm the target rollback version

Check the previous good release/tag before touching the stack.

Example:

```bash
git fetch --tags
git tag --sort=-creatordate | head
```

### 3. Roll back application code/images

If production deploys from a checked-out repo:

```bash
git fetch --tags
git checkout v0.1.2
docker compose -f docker-compose.prod.yml up --build -d
```

If the deployment process uses released GHCR images only, pin the runtime to the known-good release tag and redeploy from that tag's compose/config snapshot.

### 4. Verify rollback health

Run these from the deployment host:

```bash
curl -fsS http://localhost/health
curl -fsS http://localhost/ready
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --since=10m backend frontend db
```

Expected:

- `/health` returns HTTP 200
- `/ready` returns HTTP 200 with database readiness
- backend/frontend containers are healthy or running cleanly
- no repeating migration/startup/auth errors in logs

### 5. Restore database only if needed

Use restore when rollbacking app code/images is not enough and the database must be returned to an earlier state.

Stop write traffic first, then run:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U platform -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'agentic_platform' AND pid <> pg_backend_pid();"

docker compose -f docker-compose.prod.yml exec -T db \
  psql -U platform -d agentic_platform \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

docker compose -f docker-compose.prod.yml exec -T db \
  psql -U platform -d agentic_platform \
  < backups/pre-rollback-<timestamp>.sql
```

For a gzipped dump:

```bash
gunzip -c backups/pre-rollback-<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db \
  psql -U platform -d agentic_platform
```

Then restart backend/frontend if needed:

```bash
docker compose -f docker-compose.prod.yml up -d backend frontend
```

### 6. Post-restore validation

Recommended minimum validation after rollback or restore:

1. login works and `/api/v1/auth/me` returns 200
2. create a workflow
3. create a tool
4. start and cancel one execution
5. load analytics overview/timeline/export

## Local GraphPilot Rollback

The packaged local runtime is controlled by `GRAPHPILOT_HOME/.env`.

### 1. Stop the local stack

```bash
graphpilot down
```

### 2. Change the runtime image tag

Edit `~/.graphpilot/.env` (or `%USERPROFILE%\.graphpilot\.env` on Windows) and set:

```env
GRAPHPILOT_IMAGE_TAG=v0.1.2
```

### 3. Start the known-good runtime

```bash
graphpilot up
graphpilot status
graphpilot smoke
```

### 4. Optional local data backup and restore

Backup local DB state:

```bash
docker compose -f ~/.graphpilot/docker-compose.yml exec -T db \
  pg_dump -U platform -d agentic_platform --clean --if-exists \
  > graphpilot-backup.sql
```

Restore local DB state:

```bash
docker compose -f ~/.graphpilot/docker-compose.yml exec -T db \
  psql -U platform -d agentic_platform \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

docker compose -f ~/.graphpilot/docker-compose.yml exec -T db \
  psql -U platform -d agentic_platform \
  < graphpilot-backup.sql
```

Windows PowerShell example path:

```powershell
docker compose -f "$env:USERPROFILE\.graphpilot\docker-compose.yml" exec -T db `
  pg_dump -U platform -d agentic_platform --clean --if-exists `
  > graphpilot-backup.sql
```

## Incident Notes To Record

After every rollback or restore, record:

- incident start and end time
- bad version and restored version
- whether DB restore was needed
- backup filename used
- post-rollback validation result
- follow-up fix owner

## Guardrails

- do not delete the database volume unless permanent data removal is intended
- always take a fresh pre-rollback backup before modifying data
- prefer image/code rollback first; restore DB only when necessary
- remove temporary accepted-risk entries from `.security/container-risk-accepted.json` once upstream fixes become available
