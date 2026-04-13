---
description: Реализация нового модуля по спецификации TECH_SPEC.md
---

# Skill: Implement Module

## Когда использовать
При реализации нового модуля из TECH_SPEC.md (M1-M7).

## Workflow

### 1. Подготовка
- Прочитай секцию модуля в TECH_SPEC.md.
- Определи зависимости: какие модули должны быть готовы.
- Проверь что зависимые таблицы и endpoints существуют.

### 2. Backend (порядок)
1. **Models** (`backend/app/models/`): SQLAlchemy models по Модели данных из спеки.
2. **Schemas** (`backend/app/schemas/`): Pydantic schemas — Request и Response отдельно.
3. **Services** (`backend/app/services/`): Business logic по секции Бизнес-логика.
4. **API Routes** (`backend/app/api/v1/`): Endpoints по таблице API из спеки.
5. **Migration**: `alembic revision --autogenerate -m "add {module} tables"`.

### 3. Frontend (порядок)
1. **API client** (`frontend/src/api/`): функции для вызова endpoints.
2. **Hooks** (`frontend/src/hooks/`): custom hooks для data fetching и state.
3. **Components** (`frontend/src/components/`): UI-компоненты по секции Экраны.
4. **Pages** (`frontend/src/pages/`): страницы, собирающие компоненты.
5. **Router**: добавить route в App.jsx.

### 4. Проверка
- Все endpoints из таблицы API реализованы.
- Все состояния UI обработаны (loading, loaded, empty, error).
- Все крайние случаи из секции учтены.
- tenant_id фильтрация в каждом DB-запросе.
- Нет TODO-заглушек.

### 5. Чеклист завершения
- [ ] Models созданы + migration applied
- [ ] Schemas: request + response
- [ ] Service: полная бизнес-логика
- [ ] API: все endpoints из спеки
- [ ] Frontend: pages + components + hooks
- [ ] Error handling: все коды ошибок из спеки
- [ ] Edge cases: все случаи обработаны
