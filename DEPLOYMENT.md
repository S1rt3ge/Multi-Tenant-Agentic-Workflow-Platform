# Deployment Guide

This project can be deployed with `docker-compose.prod.yml`.

## Prerequisites

- Docker Engine with Compose support
- A Linux host or VM with ports `80` and `443` managed appropriately
- Real secrets for database and JWT configuration
- Real LLM provider API keys if execution features will call external models

## Required Environment Variables

Create a production `.env` file from `.env.example` and set at least:

```env
DB_PASSWORD=<strong-database-password>
JWT_SECRET=<strong-random-256-bit-secret>
CORS_ORIGINS=https://your-frontend-domain.com
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Optional but commonly needed:

```env
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>
VITE_API_URL=https://your-api-domain.com
```

## Production Notes

- `APP_ENV` is already set to `production` in `docker-compose.prod.yml`
- Database is not exposed publicly in production compose
- Backend runs `alembic upgrade head` on startup
- Frontend is served by nginx and proxies `/api/` to the backend container
- If frontend and backend share the same public domain, `VITE_API_URL` can be left empty

## Deploy

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

## Post-Deploy Checks

Run these from the deployment host after startup:

```bash
curl -fsS http://localhost/health
curl -fsS http://localhost/ready
```

Expected:

- `/health` returns frontend-proxied backend health JSON
- `/ready` returns backend readiness JSON with database connectivity

## Smoke Validation

Recommended after deploy:

1. Register a test tenant/user
2. Log in and confirm `/api/v1/auth/me`
3. Create a workflow
4. Create a tool
5. Start and cancel a test execution
6. Open dashboard and confirm analytics endpoints respond

## Logs

Backend logs are structured and support:

- `LOG_FORMAT=json`
- `LOG_LEVEL=INFO|WARNING|ERROR|DEBUG`

View running logs:

```bash
docker-compose -f docker-compose.prod.yml logs -f backend frontend db
```

## Roll Forward / Restart

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

## Rollback Strategy

The safest rollback is to redeploy a previous known-good image/build from git.

Practical rollback path:

1. Check out the previous known-good commit or tag
2. Rebuild images
3. Run `docker-compose -f docker-compose.prod.yml up --build -d`

Do not delete the `pgdata` volume unless you explicitly intend to remove production data.
