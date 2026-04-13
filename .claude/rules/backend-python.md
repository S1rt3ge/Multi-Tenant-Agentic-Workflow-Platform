---
description: Правила для backend Python-файлов
globs: ["backend/**/*.py"]
---

# Backend Python Rules

## Async
- Все функции endpoints — `async def`.
- SQLAlchemy: только `AsyncSession`. Импорт: `from sqlalchemy.ext.asyncio import AsyncSession`.
- Все DB-операции через `await session.execute(...)`, `await session.commit()`.

## Multi-tenancy
- Каждый endpoint принимает `tenant_id` через `Depends(get_current_tenant)`.
- Каждый SELECT/UPDATE/DELETE включает `WHERE tenant_id = :tenant_id`.
- Никогда не выполняй запросы без фильтра по tenant_id (кроме auth/register, auth/login).

## FastAPI Patterns
- Route handlers в `app/api/v1/`. Один файл на модуль.
- Pydantic schemas в `app/schemas/`. Response и Request модели отдельно.
- Business logic в `app/services/`. Route handler вызывает service, не содержит логику.
- Error responses: `raise HTTPException(status_code=XXX, detail="Message")`.

## SQLAlchemy Models
- Primary key: `id = Column(UUID, primary_key=True, default=uuid4)`.
- Все таблицы имеют `tenant_id`, `created_at`, `updated_at` (кроме tenants — там нет tenant_id).
- JSONB columns: `Column(JSONB, nullable=False, default=dict/list)`.
- Indexes на `tenant_id` и часто используемые поля (email, workflow_id).

## Imports Order
1. stdlib (uuid, datetime)
2. third-party (fastapi, sqlalchemy, pydantic)
3. local (app.core, app.models, app.schemas, app.services)
