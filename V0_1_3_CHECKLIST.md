# v0.1.3 Release Checklist

This document is the acceptance checklist for the next release hardening cycle.

Use it as the final go/no-go artifact before cutting `v0.1.3`.

## Step 1: Pipeline Health

Goal: all automated quality gates are green on `main`.

Required:

- `CI` green
- `Smoke` green
- `CLI E2E` green
- `CLI Cross-Platform Sanity` green
- `Observability SLO` green
- `Security Gates` green
- `Publish Images` green on latest `main`

Acceptance criteria:

- no red workflow on `main`
- no flaky rerun needed to get green
- no temporary workflow disablement

Evidence:

- run IDs:
- verification date:
- verifier:

Status:

- [ ] done

## Step 2: Cross-Platform Runtime Validation

Goal: confirm the real user runtime path works across supported platforms.

### Windows manual pass

Run:

1. `npm install -g graphpilot@latest`
2. `graphpilot.cmd init`
3. `graphpilot.cmd doctor`
4. `graphpilot.cmd up`
5. `graphpilot.cmd status`
6. `graphpilot.cmd smoke`
7. `graphpilot.cmd down`

Acceptance criteria:

- no undocumented workaround required
- runtime files created correctly under `%USERPROFILE%\.graphpilot`
- backend health reachable
- smoke passes

Evidence:

- operator:
- date:
- notes:

Current finding:

- Previously blocked on published `graphpilot@0.1.2` referencing non-existent GHCR tags `0.1.2`.
- Corrective release `graphpilot@0.1.3` fixes this and resolves `v0.1.3` images correctly.
- Latest Windows rerun on the published package failed only because host port `8000` was already occupied by an unrelated local container, not because of a package/runtime artifact mismatch.

Status:

- [ ] Windows done

### macOS manual pass

Run:

1. `npm install -g graphpilot@latest`
2. `graphpilot init`
3. `graphpilot doctor`
4. `graphpilot up`
5. `graphpilot status`
6. `graphpilot smoke`
7. `graphpilot down`

Acceptance criteria:

- no undocumented workaround required
- runtime files created correctly under `~/.graphpilot`
- frontend and backend reachable
- smoke passes

Evidence:

- operator:
- date:
- notes:

Status:

- [ ] macOS done

## Step 3: Security Risk Review

Goal: review all temporary accepted risks and confirm they are still justified.

Scope:

- `.security/container-risk-accepted.json`
- any upstream base-image or package updates available since last review

Acceptance criteria:

- every accepted risk has owner and future expiry
- no stale/expired accepted risk remains
- any fixable risk is removed from the accepted list and remediated instead

Evidence:

- reviewer:
- date:
- removed entries:
- remaining entries reviewed:

Status:

- [ ] done

## Step 4: Release Decision

Goal: make a formal go/no-go decision for `v0.1.3`.

Go criteria:

- Step 1 complete
- Step 2 Windows complete
- Step 2 macOS complete
- Step 3 complete
- `ROLLBACK.md` still valid for the current release target
- docs remain synchronized (`README`, `PROGRESS`, `RELEASE`, `DEPLOYMENT`, `ROLLBACK`, `CROSS_PLATFORM`)

No-go triggers:

- any red workflow on `main`
- missing Windows or macOS runtime pass
- expired accepted risks not reviewed
- rollback procedure no longer matches the deployed runtime model
- published npm artifact points to non-existent GHCR tags or otherwise fails the real install/run path

Decision:

- [ ] GO for `v0.1.3`
- [ ] NO-GO for `v0.1.3`

Decision notes:

- release owner:
- decision date:
- blockers, if any:
