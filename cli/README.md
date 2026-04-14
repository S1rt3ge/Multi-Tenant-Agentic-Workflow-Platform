# GraphPilot CLI

GraphPilot is a local launcher CLI for the self-hosted GraphPilot stack.

## Install

For local development/testing from this repository:

```bash
npm install -g ./cli
```

## Usage

```bash
graphpilot init
graphpilot doctor
graphpilot up
graphpilot status
```

On Windows, if PowerShell blocks the generated `graphpilot.ps1` shim because of execution policy, use `graphpilot.cmd` instead.

Make sure Docker Desktop or another local Docker daemon is running before starting the stack.

## Commands

- `graphpilot init` — initialize local runtime files in `~/.graphpilot`
- `graphpilot doctor` — verify Docker, Compose, and local runtime readiness
- `graphpilot up` — start the local stack
- `graphpilot status` — show stack status
- `graphpilot logs` — follow stack logs
- `graphpilot down` — stop the stack
- `graphpilot reset` — stop the stack and remove local volumes

## Runtime Model

GraphPilot uses Docker Compose and published backend/frontend runtime images.

The CLI initializes a per-user app directory and manages the local stack from there.
