# Multi-Tenant Agentic Workflow Platform
# AI Development Guide (Spec-First)

## Обзор
No-code платформа для визуального проектирования, запуска и мониторинга агентных воркфлоу на LangGraph. Multi-tenant SaaS с полным аудитом и cost tracking.

## Стек
- Backend: FastAPI, LangGraph, SQLAlchemy (Async), PostgreSQL, Alembic
- Frontend: React (JS only), React Flow, Tailwind CSS, Recharts
- Infrastructure: Docker, docker-compose
- Auth: JWT (access 30min + refresh 7d), bcrypt

## Архитектура
- Multi-tenancy: `tenant_id` во всех таблицах. Middleware инжектит через FastAPI Depends.
- Оркестрация: LangGraph StateGraph. JSON definition -> compiled graph -> execution.
- Логирование: каждый шаг агента -> `execution_logs` (tokens, cost, reasoning).
- Изоляция: все DB-запросы фильтруются по tenant_id. Нет RLS на уровне PostgreSQL — фильтрация на уровне ORM.

## 7 модулей (порядок реализации)
1. Auth & Tenants (M1) — JWT, регистрация, invite, RBAC (owner/editor/viewer)
2. Workflow CRUD (M2) — создание, список, дублирование, soft delete
3. Tool Registry (M5) — регистрация API/DB/FS инструментов для агентов
4. Builder UI (M3) — React Flow canvas, drag-and-drop, agent config panel
5. Execution Engine (M4) — graph compiler, executor, WebSocket live logs
6. Dashboard (M6) — KPI, cost timeline, workflow breakdown, export
7. Infrastructure (M7) — Docker, Alembic, env config

## Правила
- Frontend: ТОЛЬКО JavaScript. НЕ TypeScript. НЕ .tsx/.ts файлы.
- Backend: Async everywhere. AsyncSession для SQLAlchemy. async def для всех endpoints.
- DI: `get_current_tenant` и `get_db` через FastAPI Depends() в каждом endpoint.
- Без TODO-заглушек. Реализуй логику полностью по TECH_SPEC.md.
- Все эндпоинты под `/api/v1/`. Версионирование через path prefix.
- Error responses: `{"detail": "Human-readable message"}`. HTTP-коды по TECH_SPEC.
- JSONB для definition (workflow graph), config (tools), tools (agent).

## Backend Rules
- Все endpoint handlers — `async def`. SQLAlchemy: только `AsyncSession`.
- Каждый SELECT/UPDATE/DELETE включает `WHERE tenant_id = :tenant_id`.
- Route handlers в `app/api/v1/`. Один файл на модуль.
- Business logic в `app/services/`. Route handler вызывает service, не содержит логику.
- Pydantic schemas: Request и Response модели отдельно в `app/schemas/`.
- `raise HTTPException(status_code=XXX, detail="Message")` для ошибок.
- Primary key: UUID с `default=uuid4`. Text: TEXT. JSON: JSONB. Timestamps: TIMESTAMPTZ.
- Index на `tenant_id` в каждой таблице. Composite indexes: `(tenant_id, поле)`.
- FK с `ON DELETE CASCADE` к tenants и workflows.

## Frontend Rules
- ТОЛЬКО .js и .jsx. Функциональные компоненты + hooks. Без class components.
- Tailwind CSS utility-first. Без отдельных CSS-файлов.
- API calls через axios instance из `src/api/client.js`. JWT interceptor: auto-attach + refresh.
- Каждая страница: 4 состояния — loading (skeleton), loaded, empty (message), error (retry).
- React Flow: useNodesState, useEdgesState. Custom AgentNode. Auto-save debounce 2s.
- State management: React Context + useReducer для auth/tenant. useState для локального.

## Engine Rules (LangGraph)
- Compiler: JSON definition (nodes + edges) → LangGraph StateGraph.
- State schema: `{messages: list, current_agent: str, results: dict, metadata: dict}`.
- Cost tracking: после каждого LLM call рассчитай cost по модели. Проверяй budget перед каждым call.
- Error handling: LLM 429 → exponential backoff (max 3). Timeout >30s → cancel step. Cyclic max_iterations=10.
- WebSocket: events (step_start, step_complete, execution_complete, error) на каждом шаге.

## Workflow реализации модуля
1. Прочитай секцию модуля в `TECH_SPEC.md` (user stories, данные, API, UI, логика, edge cases).
2. Backend: models → schemas → services → api routes → migration.
3. Frontend: api client → hooks → components → pages → router.
4. Проверь: все endpoints реализованы, tenant_id в каждом запросе, все edge cases, нет TODO.

## Структура
```
backend/app/          — FastAPI application
  main.py             — app factory, middleware, router includes
  core/               — config, security, dependencies
  models/             — SQLAlchemy models (tenant, user, workflow, execution...)
  schemas/            — Pydantic schemas
  api/v1/             — route handlers
  services/           — business logic
  engine/             — LangGraph compiler, executor, agents, tools
frontend/src/         — React application
  pages/              — page components (Login, Register, Builder, Dashboard...)
  components/         — reusable components (builder/, execution/, dashboard/, common/)
  hooks/              — custom hooks (useAuth, useWorkflow, useWebSocket)
  api/                — axios client with JWT interceptor
```

## Команды
- `npm run dev` — фронтенд (port 3000)
- `uvicorn app.main:app --reload` — бэкенд (port 8000)
- `docker-compose up` — полный стек (postgres + backend + frontend)
- `alembic upgrade head` — применить миграции
- `alembic revision --autogenerate -m "desc"` — создать миграцию

## Ключевые файлы
- `TECH_SPEC.md` — полная спецификация всех модулей (user stories, API, DB, UI, edge cases)
- `PROJECT_IDEA.md` — документ идеи с архитектурой, монетизацией, рисками

## Справочные файлы (читать при работе над конкретным модулем)
- `.claude/agents/database-architect.md` — паттерны для схемы БД и миграций
- `.claude/agents/backend-engineer.md` — паттерны для FastAPI endpoints и services
- `.claude/agents/frontend-developer.md` — паттерны для React UI и React Flow
- `.claude/agents/execution-engine-architect.md` — паттерны для LangGraph engine
- `.claude/agents/qa-reviewer.md` — чеклист для code review
- `.claude/skills/implement-module.md` — детальный workflow реализации модуля
- `.claude/skills/create-migration.md` — workflow создания Alembic миграции
