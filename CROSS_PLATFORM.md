# Cross-Platform Sanity Matrix

This document tracks the minimum supported GraphPilot CLI flow across operating systems.

## Scope

Target flow:

1. install `graphpilot`
2. `graphpilot init`
3. `graphpilot doctor`
4. `graphpilot up`
5. `graphpilot status`
6. `graphpilot smoke`
7. `graphpilot down`

## Current Coverage

| Platform | Install + Init | Doctor | Up/Status | Smoke | Down | Source |
|----------|----------------|--------|-----------|-------|------|--------|
| Linux | ✅ | ✅ | ✅ | ✅ | ✅ | `CLI E2E` workflow |
| Windows | ✅ | partial | manual pending | manual pending | manual pending | `CLI Cross-Platform Sanity` + local notes |
| macOS | ✅ | partial | manual pending | manual pending | manual pending | `CLI Cross-Platform Sanity` |

## What Is Automated Today

- `CLI E2E` proves the full npm-installed runtime flow on Linux.
- `CLI Cross-Platform Sanity` proves CLI packaging, `help`, `init`, and file generation on Linux/Windows/macOS.

## What Still Needs Manual Validation

### Windows

Use `graphpilot.cmd` if PowerShell blocks the generated shim.

Checklist:

1. `npm install -g graphpilot@latest`
2. `graphpilot.cmd init`
3. `graphpilot.cmd doctor`
4. `graphpilot.cmd up`
5. `graphpilot.cmd status`
6. `graphpilot.cmd smoke`
7. `graphpilot.cmd down`

Expected notes:

- Docker Desktop must be running
- `.env` is created under `%USERPROFILE%\.graphpilot`
- backend health becomes available at `http://localhost:8000/health`

### macOS

Checklist:

1. `npm install -g graphpilot@latest`
2. `graphpilot init`
3. `graphpilot doctor`
4. `graphpilot up`
5. `graphpilot status`
6. `graphpilot smoke`
7. `graphpilot down`

Expected notes:

- Docker Desktop or compatible local Docker engine must be running
- `.env` is created under `~/.graphpilot`
- frontend should be reachable at `http://localhost:3000`

## Release Gate Recommendation

For the next release cut, require at minimum:

- Linux full path green in CI
- Windows manual checklist completed once against `graphpilot@latest`
- macOS manual checklist completed once against `graphpilot@latest`
