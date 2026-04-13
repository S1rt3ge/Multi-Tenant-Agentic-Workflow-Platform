---
description: Правила для Alembic миграций и SQL
globs: ["backend/alembic/**/*.py", "**/*.sql"]
---

# Database & Migrations Rules

## Типы данных
- Primary keys: UUID (`gen_random_uuid()`).
- Text: `TEXT` (не VARCHAR).
- JSON: `JSONB` (не JSON).
- Timestamps: `TIMESTAMPTZ` (не TIMESTAMP).
- Boolean: `BOOLEAN NOT NULL DEFAULT`.

## Tenant Isolation
- Каждая таблица (кроме tenants) имеет `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`.
- Index на tenant_id в каждой таблице.
- Composite indexes: `(tenant_id, часто_фильтруемое_поле)`.

## Migrations
- Генерация: `alembic revision --autogenerate -m "description"`.
- Применение: `alembic upgrade head`.
- Откат: `alembic downgrade -1`.
- Каждая миграция содержит и upgrade и downgrade.
- Naming: описательное сообщение на английском.

## Constraints
- NOT NULL по умолчанию для всех полей (кроме description, nullable fields из спеки).
- UNIQUE constraints: email (users), slug (tenants), (tenant_id, name) для tool_registry.
- ON DELETE CASCADE для FK к tenants и workflows.
