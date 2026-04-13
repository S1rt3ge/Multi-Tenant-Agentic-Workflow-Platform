---
description: Создание Alembic миграции для новых или изменённых таблиц
---

# Skill: Create Migration

## Когда использовать
При добавлении новых таблиц, изменении полей, добавлении индексов.

## Workflow

### 1. Проверь модели
- Убедись что SQLAlchemy model в `backend/app/models/` обновлена.
- Модель импортирована в `backend/app/models/__init__.py`.
- Все поля соответствуют TECH_SPEC.md (типы, constraints, defaults).

### 2. Создай миграцию
```bash
cd backend
alembic revision --autogenerate -m "описание изменений"
```

### 3. Проверь сгенерированный файл
- Открой файл в `backend/alembic/versions/`.
- Проверь что:
  - Все таблицы/колонки присутствуют.
  - Индексы созданы (tenant_id, composite indexes).
  - Foreign keys с ON DELETE CASCADE.
  - `downgrade()` корректно откатывает изменения.

### 4. Примени
```bash
alembic upgrade head
```

### 5. Верификация
```bash
# Проверь что таблицы созданы
python -c "from app.models import *; print('Models OK')"
```

## Правила
- Одна миграция = одно логическое изменение.
- Не объединяй несвязанные изменения в одну миграцию.
- Всегда проверяй downgrade path.
- UUID primary keys: `sa.Column(sa.UUID, primary_key=True, server_default=sa.text('gen_random_uuid()'))`.
