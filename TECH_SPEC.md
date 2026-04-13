# TECH_SPEC.md — Техническая спецификация

> Сгенерирована из PROJECT_IDEA.md по методологии Spec-First.
> Каждый модуль содержит 6 блоков: User Stories, Модель данных, API, Экраны, Бизнес-логика, Крайние случаи.

---

## Модуль 1: Auth & Tenant Management

### 1.1 User Stories

- **US-1.1**: Как новый пользователь, я хочу зарегистрироваться через email и пароль, чтобы получить доступ к платформе.
- **US-1.2**: Как зарегистрированный пользователь, я хочу войти в систему и получить JWT-токен, чтобы обращаться к API.
- **US-1.3**: Как owner тенанта, я хочу пригласить коллегу в свой тенант с ролью editor или viewer, чтобы работать совместно.
- **US-1.4**: Как admin, я хочу видеть список всех пользователей своего тенанта, чтобы управлять доступом.
- **US-1.5**: Как пользователь, я хочу обновить свой профиль (имя, пароль), чтобы актуализировать данные.

### 1.2 Модель данных

```sql
-- Тенанты
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,               -- URL-friendly идентификатор
    plan TEXT NOT NULL DEFAULT 'free',        -- free | pro | team | enterprise
    max_workflows INT NOT NULL DEFAULT 2,
    max_agents_per_workflow INT NOT NULL DEFAULT 3,
    monthly_token_budget INT NOT NULL DEFAULT 100000,
    tokens_used_this_month INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tenants_slug ON tenants(slug);

-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'editor',      -- owner | editor | viewer
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
```

### 1.3 API

| Метод | Путь | Тело запроса | Ответ (200/201) | Коды ошибок |
|-------|------|-------------|-----------------|-------------|
| POST | `/api/v1/auth/register` | `{email, password, full_name, tenant_name}` | `{user_id, tenant_id, access_token}` | 400 (валидация), 409 (email exists) |
| POST | `/api/v1/auth/login` | `{email, password}` | `{access_token, refresh_token, user}` | 401 (wrong credentials) |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | `{access_token}` | 401 (invalid token) |
| GET | `/api/v1/auth/me` | — | `{user_id, email, full_name, role, tenant}` | 401 |
| PUT | `/api/v1/auth/me` | `{full_name?, password?}` | `{user}` | 400, 401 |
| GET | `/api/v1/tenants/users` | — | `[{user_id, email, role, is_active}]` | 401, 403 (not owner) |
| POST | `/api/v1/tenants/invite` | `{email, role}` | `{user_id}` | 400, 403, 409 |
| PUT | `/api/v1/tenants/users/{user_id}/role` | `{role}` | `{user}` | 400, 403, 404 |
| DELETE | `/api/v1/tenants/users/{user_id}` | — | 204 | 403, 404 |

### 1.4 Экраны и компоненты

**LoginPage.jsx**
- Поля: email, password.
- Кнопка: "Sign In".
- Ссылка: "Don't have an account? Register".
- Состояния: idle, loading (спиннер на кнопке), error (красный текст под формой), success (редирект на /workflows).

**RegisterPage.jsx**
- Поля: full_name, email, password, tenant_name (название компании).
- Кнопка: "Create Account".
- Состояния: idle, loading, error (валидация + серверные ошибки), success (редирект на /workflows).

**TeamSettingsPage.jsx** (доступен только owner)
- Таблица пользователей: email, role, status, actions (change role, remove).
- Кнопка "Invite User" → модальное окно с полями email + role (dropdown: editor/viewer).
- Состояния: loading (skeleton), loaded, empty ("No team members yet").

### 1.5 Бизнес-логика

- При регистрации автоматически создаётся тенант с планом `free`. Пользователь получает роль `owner`.
- JWT access_token: срок жизни 30 минут. Refresh_token: 7 дней.
- Пароль хешируется через bcrypt (cost factor 12).
- Приглашённый пользователь получает временный пароль, который обязан сменить при первом входе.
- Owner не может удалить сам себя. Owner не может понизить свою роль.
- Viewer не может создавать/редактировать воркфлоу, только просматривать.
- Все запросы к API (кроме auth/register, auth/login) требуют валидный JWT. Middleware извлекает `tenant_id` из токена и инжектит в каждый запрос.

### 1.6 Крайние случаи

- **Дублированный email при регистрации**: 409 Conflict с сообщением "Email already registered".
- **Expired JWT**: 401 с телом `{detail: "Token expired"}`. Frontend перехватывает, пытается refresh. Если refresh тоже expired — редирект на /login.
- **Owner удаляет последнего editor**: разрешено, но показать предупреждение "You'll be the only user".
- **Инвайт на email уже существующего пользователя в другом тенанте**: 409 "User already belongs to another tenant".
- **Concurrent login с разных устройств**: разрешено, каждый получает свой JWT.

---

## Модуль 2: Workflow Management (CRUD)

### 2.1 User Stories

- **US-2.1**: Как пользователь, я хочу создать новый воркфлоу с названием и описанием, чтобы начать проектирование агентного графа.
- **US-2.2**: Как пользователь, я хочу видеть список всех воркфлоу моего тенанта, чтобы выбрать нужный для редактирования.
- **US-2.3**: Как пользователь, я хочу дублировать существующий воркфлоу, чтобы создать вариацию без потери оригинала.
- **US-2.4**: Как пользователь, я хочу удалить воркфлоу (soft delete), чтобы он не отображался, но логи сохранились.
- **US-2.5**: Как viewer, я хочу видеть воркфлоу, но не иметь возможности его изменять.

### 2.2 Модель данных

```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    definition JSONB NOT NULL DEFAULT '{"nodes": [], "edges": []}',
    execution_pattern TEXT NOT NULL DEFAULT 'linear',  -- linear | parallel | cyclic
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflows_tenant_id ON workflows(tenant_id);
CREATE INDEX idx_workflows_tenant_active ON workflows(tenant_id, is_active);
```

**definition JSONB format:**
```json
{
  "nodes": [
    {
      "id": "node-1",
      "type": "agent",
      "position": {"x": 100, "y": 200},
      "data": {
        "agent_config_id": "uuid",
        "label": "Retriever"
      }
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "node-1",
      "target": "node-2",
      "data": {
        "condition": null
      }
    }
  ]
}
```

### 2.3 API

| Метод | Путь | Тело запроса | Ответ | Коды ошибок |
|-------|------|-------------|-------|-------------|
| POST | `/api/v1/workflows` | `{name, description?, execution_pattern?}` | 201: `{workflow}` | 400, 401, 403 (viewer), 422 (max workflows reached) |
| GET | `/api/v1/workflows` | query: `?page=1&per_page=20&search=` | 200: `{items: [...], total, page}` | 401 |
| GET | `/api/v1/workflows/{id}` | — | 200: `{workflow}` | 401, 404 |
| PUT | `/api/v1/workflows/{id}` | `{name?, description?, definition?, execution_pattern?}` | 200: `{workflow}` | 400, 401, 403, 404 |
| POST | `/api/v1/workflows/{id}/duplicate` | — | 201: `{workflow}` (copy) | 401, 403, 404, 422 |
| DELETE | `/api/v1/workflows/{id}` | — | 204 | 401, 403, 404 |

### 2.4 Экраны и компоненты

**WorkflowListPage.jsx**
- Сетка карточек воркфлоу: name, description (обрезано 100 символов), execution_pattern badge, last_updated, кнопки (Open, Duplicate, Delete).
- Кнопка "New Workflow" → модальное окно: name (required), description (optional), pattern (dropdown: linear/parallel/cyclic).
- Поиск по названию (debounce 300ms).
- Пагинация: 20 элементов на страницу.
- Состояния: loading (skeleton cards), loaded, empty ("Create your first workflow"), error.

### 2.5 Бизнес-логика

- При создании воркфлоу проверяется лимит: `COUNT(workflows WHERE tenant_id = X AND is_active = true) < tenant.max_workflows`. Если превышен — 422 с сообщением "Workflow limit reached. Upgrade your plan."
- Duplicate создаёт копию с name = "{original_name} (Copy)" и пустой execution history.
- Delete — soft delete: `is_active = false`. Воркфлоу не отображается в списке, но execution_logs сохраняются.
- `definition` сохраняется целиком при каждом PUT (не merge, а replace). Frontend отправляет полный JSON.
- `updated_at` обновляется автоматически через SQLAlchemy event.
- Viewer видит список и может открыть воркфлоу в read-only mode (builder без возможности редактирования).

### 2.6 Крайние случаи

- **Создание при исчерпанном лимите**: 422 "Workflow limit reached. Upgrade your plan."
- **Удаление воркфлоу с running execution**: запретить, 409 "Cannot delete workflow with running execution".
- **Concurrent edit**: last-write-wins. Нет collaborative editing в MVP.
- **Пустой definition**: допустимо при создании (граф будет пустым в builder).
- **Workflow не найден (чужой tenant)**: 404 (не 403, чтобы не раскрывать существование чужих ресурсов).

---

## Модуль 3: Workflow Builder (UI)

### 3.1 User Stories

- **US-3.1**: Как пользователь, я хочу перетащить ноду агента на canvas, чтобы добавить агента в граф.
- **US-3.2**: Как пользователь, я хочу соединить два агента ребром (drag от output handle к input handle), чтобы задать поток данных.
- **US-3.3**: Как пользователь, я хочу кликнуть на ноду и настроить агента в sidebar (role, model, prompt, tools), чтобы сконфигурировать его поведение.
- **US-3.4**: Как пользователь, я хочу сохранить граф кнопкой Save, чтобы не потерять изменения.
- **US-3.5**: Как пользователь, я хочу запустить воркфлоу кнопкой Run прямо из builder, чтобы протестировать.
- **US-3.6**: Как пользователь, я хочу видеть валидационные ошибки графа (нет нод, несвязанные ноды), чтобы исправить перед запуском.

### 3.2 Модель данных

Builder работает с `workflows.definition` (JSONB). Дополнительно — таблица конфигураций агентов:

```sql
CREATE TABLE agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,                     -- соответствует node.id в definition
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'analyzer',      -- retriever | analyzer | validator | escalator | custom
    system_prompt TEXT NOT NULL DEFAULT 'You are a helpful assistant.',
    model TEXT NOT NULL DEFAULT 'gpt-4o',      -- gpt-4o | gpt-4o-mini | claude-sonnet | claude-opus
    tools JSONB NOT NULL DEFAULT '[]',         -- [{tool_id: uuid, name: "search_api"}]
    memory_type TEXT NOT NULL DEFAULT 'buffer', -- buffer | summary | vector
    max_tokens INT NOT NULL DEFAULT 4096,
    temperature FLOAT NOT NULL DEFAULT 0.7,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_configs_workflow ON agent_configs(workflow_id);
CREATE INDEX idx_agent_configs_tenant ON agent_configs(tenant_id);
CREATE UNIQUE INDEX idx_agent_configs_node ON agent_configs(workflow_id, node_id);
```

### 3.3 API

| Метод | Путь | Тело | Ответ | Ошибки |
|-------|------|------|-------|--------|
| GET | `/api/v1/workflows/{wf_id}/agents` | — | 200: `[{agent_config}]` | 401, 404 |
| POST | `/api/v1/workflows/{wf_id}/agents` | `{node_id, name, role, system_prompt, model, tools, memory_type, max_tokens, temperature}` | 201: `{agent_config}` | 400, 401, 403, 404, 422 (max agents) |
| PUT | `/api/v1/workflows/{wf_id}/agents/{agent_id}` | partial update fields | 200: `{agent_config}` | 400, 401, 403, 404 |
| DELETE | `/api/v1/workflows/{wf_id}/agents/{agent_id}` | — | 204 | 401, 403, 404 |

### 3.4 Экраны и компоненты

**BuilderPage.jsx**
- Layout: Sidebar (left, 280px) + Canvas (center, flex) + Config Panel (right, 320px, hidden по умолчанию).

**Canvas.jsx** (React Flow)
- Background: dots pattern.
- Drag-and-drop из sidebar: создаёт ноду на canvas.
- Custom node `AgentNode.jsx`: иконка роли + name + model badge + input/output handles.
- Edge: анимированный, с label для condition (если cyclic pattern).
- Toolbar сверху: Save (Ctrl+S), Run, Validate, Zoom controls.
- Mini-map в правом нижнем углу.

**Sidebar.jsx** (левая панель)
- Палитра нод: секции по ролям (Retriever, Analyzer, Validator, Escalator, Custom).
- Каждая нода — draggable элемент с иконкой и названием.
- Под палитрой: список шаблонов (preset workflows).

**AgentConfigPanel.jsx** (правая панель, появляется при клике на ноду)
- Поля:
  - Name (text input)
  - Role (dropdown: retriever, analyzer, validator, escalator, custom)
  - Model (dropdown: gpt-4o, gpt-4o-mini, claude-sonnet, claude-opus)
  - System Prompt (textarea, 6 строк)
  - Tools (multi-select из tool_registry тенанта)
  - Memory Type (radio: buffer / summary / vector)
  - Max Tokens (number input, 256-16384)
  - Temperature (slider, 0.0-2.0, шаг 0.1)
- Кнопка "Apply" — сохраняет конфигурацию агента.

### 3.5 Бизнес-логика

- **Валидация графа перед запуском**:
  1. Минимум 1 нода.
  2. Все ноды связаны (нет orphan nodes).
  3. Для linear: граф — DAG (без циклов), если pattern не cyclic.
  4. Каждая нода имеет сохранённую agent_config.
  5. У каждого агента заполнен system_prompt.
- **Auto-save**: debounce 2 секунды после последнего изменения position/edges. Не сохраняет при каждом движении.
- **Undo/Redo**: React Flow встроенный. Хранит последние 50 действий.
- При добавлении ноды на canvas — автоматически создаётся agent_config с дефолтными значениями (POST /agents).
- При удалении ноды — удаляется agent_config (DELETE /agents) и все связанные edges.
- Проверка лимита: `COUNT(agent_configs WHERE workflow_id = X) < tenant.max_agents_per_workflow`.

### 3.6 Крайние случаи

- **Drag ноду за пределы canvas**: React Flow ограничивает bounds.
- **Два ребра между одной парой нод**: запретить, показать toast "Connection already exists".
- **Ребро к самому себе (self-loop)**: разрешить только для cyclic pattern. Для linear/parallel — запретить.
- **Удаление ноды со связями**: удалить ноду + все входящие/исходящие рёбра + agent_config.
- **Browser refresh без сохранения**: показать confirm dialog "You have unsaved changes. Leave?"
- **Viewer открывает builder**: все элементы disabled (не может drag, edit, delete). Кнопки Save/Run скрыты.

---

## Модуль 4: Workflow Execution Engine

### 4.1 User Stories

- **US-4.1**: Как пользователь, я хочу запустить воркфлоу с входными данными, чтобы получить результат обработки агентами.
- **US-4.2**: Как пользователь, я хочу видеть статус исполнения в реальном времени (какой агент работает сейчас), чтобы понимать прогресс.
- **US-4.3**: Как пользователь, я хочу остановить running execution, чтобы не тратить токены на ошибочный запуск.
- **US-4.4**: Как пользователь, я хочу видеть подробные логи каждого шага (вход, выход, токены, reasoning), чтобы отлаживать агентов.
- **US-4.5**: Как система, я хочу автоматически остановить execution при превышении token budget тенанта, чтобы контролировать расходы.

### 4.2 Модель данных

```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',     -- pending | running | completed | failed | cancelled
    input_data JSONB,
    output_data JSONB,
    total_tokens INT NOT NULL DEFAULT 0,
    total_cost FLOAT NOT NULL DEFAULT 0.0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_executions_tenant ON executions(tenant_id);
CREATE INDEX idx_executions_workflow ON executions(workflow_id);
CREATE INDEX idx_executions_status ON executions(tenant_id, status);
CREATE INDEX idx_executions_created ON executions(tenant_id, created_at DESC);

CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    agent_config_id UUID REFERENCES agent_configs(id),
    step_number INT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,                       -- llm_call | tool_call | decision | error
    input_data JSONB,
    output_data JSONB,
    tokens_used INT NOT NULL DEFAULT 0,
    cost FLOAT NOT NULL DEFAULT 0.0,
    decision_reasoning TEXT,                    -- почему агент принял это решение
    duration_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_logs_execution ON execution_logs(execution_id);
CREATE INDEX idx_execution_logs_step ON execution_logs(execution_id, step_number);
```

### 4.3 API

| Метод | Путь | Тело | Ответ | Ошибки |
|-------|------|------|-------|--------|
| POST | `/api/v1/workflows/{wf_id}/execute` | `{input_data}` | 201: `{execution_id, status: "pending"}` | 400 (invalid graph), 401, 403, 404, 422 (budget exceeded) |
| GET | `/api/v1/executions` | query: `?workflow_id=&status=&page=&per_page=` | 200: `{items, total, page}` | 401 |
| GET | `/api/v1/executions/{id}` | — | 200: `{execution}` | 401, 404 |
| GET | `/api/v1/executions/{id}/logs` | — | 200: `[{execution_log}]` | 401, 404 |
| POST | `/api/v1/executions/{id}/cancel` | — | 200: `{execution}` (status: cancelled) | 401, 404, 409 (not running) |
| WS | `/api/v1/executions/{id}/stream` | — | Streaming: `{step, agent, status, tokens}` events | 401, 404 |

### 4.4 Экраны и компоненты

**ExecutionPage.jsx**
- Layout: split view — Canvas (left, read-only, подсвечивает текущий агент) + Log Panel (right).

**RunPanel.jsx**
- Форма запуска: textarea для input_data (JSON или plain text).
- Кнопка Run + кнопка Cancel (visible только при status=running).
- Progress: current step / total steps.
- Cost counter: обновляется в реальном времени через WebSocket.

**LogViewer.jsx**
- Timeline шагов: step_number, agent_name, action, duration_ms.
- Кликабельный шаг раскрывает: input_data, output_data, tokens_used, cost, decision_reasoning.
- Цветовая кодировка: зелёный (success), красный (error), жёлтый (warning), серый (pending).
- Фильтр по agent_name.

### 4.5 Бизнес-логика

**Graph Compiler (`graph_compiler.py`)**:
1. Получает `workflow.definition` (JSON с nodes и edges).
2. Создаёт LangGraph `StateGraph` с typed state: `{messages: list, current_agent: str, results: dict, metadata: dict}`.
3. Для каждой ноды создаёт node function, которая:
   - Загружает agent_config
   - Формирует messages (system_prompt + контекст из state)
   - Вызывает LLM API (через model, указанный в config)
   - Записывает execution_log
   - Обновляет state
4. Для каждого edge добавляет transition. Conditional edges — для cyclic pattern (условие в `edge.data.condition`).
5. Компилирует и возвращает runnable graph.

**Executor (`executor.py`)**:
1. Создаёт execution (status: pending).
2. Проверяет budget: `tenant.tokens_used_this_month + estimated_cost < tenant.monthly_token_budget`.
3. Устанавливает status: running, started_at.
4. Запускает compiled graph через `graph.ainvoke(input_data)`.
5. При каждом шаге:
   - Записывает execution_log (step_number, agent, action, tokens, cost, reasoning).
   - Обновляет execution.total_tokens, execution.total_cost.
   - Обновляет tenant.tokens_used_this_month.
   - Отправляет WebSocket event.
   - Проверяет budget: если превышен — cancel execution.
6. По завершении: status = completed/failed, output_data = final result.

**Cost Calculation**:
- GPT-4o: input $2.50/1M tokens, output $10.00/1M tokens.
- GPT-4o-mini: input $0.15/1M tokens, output $0.60/1M tokens.
- Claude Sonnet: input $3.00/1M tokens, output $15.00/1M tokens.
- Claude Opus: input $15.00/1M tokens, output $75.00/1M tokens.
- Стоимость записывается в execution_logs.cost для каждого шага.

### 4.6 Крайние случаи

- **LLM API возвращает 429 (rate limit)**: retry с exponential backoff (1s, 2s, 4s, max 3 attempts). Если все 3 failed — step.action = "error", execution продолжается со следующим агентом (если есть fallback edge) или fails.
- **LLM API timeout (>30s)**: cancel step, log error, try next agent или fail execution.
- **Budget exceeded mid-execution**: cancel execution, status = "cancelled", error_message = "Monthly token budget exceeded".
- **Agent output не парсится**: log raw output, пометить step как warning, передать raw text следующему агенту.
- **Cyclic graph бесконечный цикл**: max_iterations = 10 (конфигурируемо). При превышении — force stop, status = "failed", error_message = "Max iterations exceeded".
- **Concurrent executions одного воркфлоу**: разрешено, каждая execution независима.
- **Cancel во время LLM call**: установить flag, проверять после каждого шага. Текущий LLM call завершится, но следующий шаг не начнётся.
- **WebSocket disconnect**: execution продолжается на сервере. При reconnect — клиент получает текущий state через GET /executions/{id}.

---

## Модуль 5: Tool Registry

### 5.1 User Stories

- **US-5.1**: Как пользователь, я хочу зарегистрировать внешний API как инструмент, чтобы агенты могли его вызывать.
- **US-5.2**: Как пользователь, я хочу протестировать инструмент (ping/test call), чтобы убедиться что конфигурация правильная.
- **US-5.3**: Как пользователь, я хочу привязать инструмент к агенту в builder, чтобы агент мог его использовать при исполнении.

### 5.2 Модель данных

```sql
CREATE TABLE tool_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    tool_type TEXT NOT NULL,                   -- api | database | file_system
    config JSONB NOT NULL,
    -- api: {url, method, headers, body_template, response_path}
    -- database: {connection_string, query_template}
    -- file_system: {base_path, allowed_extensions}
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tool_registry_tenant ON tool_registry(tenant_id);
CREATE UNIQUE INDEX idx_tool_registry_name ON tool_registry(tenant_id, name);
```

### 5.3 API

| Метод | Путь | Тело | Ответ | Ошибки |
|-------|------|------|-------|--------|
| POST | `/api/v1/tools` | `{name, description, tool_type, config}` | 201: `{tool}` | 400, 401, 403, 409 (name exists) |
| GET | `/api/v1/tools` | — | 200: `[{tool}]` | 401 |
| PUT | `/api/v1/tools/{id}` | partial update | 200: `{tool}` | 400, 401, 403, 404 |
| DELETE | `/api/v1/tools/{id}` | — | 204 | 401, 403, 404 |
| POST | `/api/v1/tools/{id}/test` | `{test_input?}` | 200: `{success: bool, response, latency_ms}` | 401, 404 |

### 5.4 Экраны и компоненты

**ToolsPage.jsx**
- Список инструментов: name, type (badge), description, status (active/inactive), actions.
- Кнопка "Add Tool" → модальное окно:
  - Name (text)
  - Description (text)
  - Type (dropdown: API, Database, File System)
  - Config (dynamic form в зависимости от type):
    - API: URL, Method (GET/POST/PUT), Headers (key-value pairs), Body Template (textarea), Response Path (JSONPath)
    - Database: Connection String, Query Template
    - File System: Base Path, Allowed Extensions (comma-separated)
- Кнопка "Test" — запускает test call, показывает результат в toast.

### 5.5 Бизнес-логика

- Tool name уникален в рамках тенанта.
- При test call: выполняется реальный запрос с timeout 10s. Результат: success/fail + response body + latency.
- Config валидация:
  - API: url обязателен, должен быть валидный URL. Method: GET/POST/PUT/DELETE.
  - Database: connection_string обязателен. Query_template должен содержать `{input}` placeholder.
  - File System: base_path обязателен.
- При использовании в агенте: tool_service.py выполняет запрос по config, подставляя input от агента.
- Secrets (API keys в headers, connection strings) хранятся в config JSONB. В будущем — шифрование at rest.

### 5.6 Крайние случаи

- **Tool API не отвечает при test**: timeout 10s, показать "Tool unreachable".
- **Невалидный URL**: клиентская валидация + серверная. 400 "Invalid URL format".
- **Удаление tool, привязанного к агенту**: разрешить, но при execution — log warning "Tool {name} not found, skipping".
- **Tool возвращает non-JSON response**: обработать как plain text, передать агенту.
- **Connection string содержит credentials**: сохраняется в JSONB. При GET /tools — маскировать пароль: `postgres://user:****@host/db`.

---

## Модуль 6: Dashboard & Analytics

### 6.1 User Stories

- **US-6.1**: Как пользователь, я хочу видеть общую статистику: количество воркфлоу, запусков, потраченных токенов, стоимость за текущий месяц.
- **US-6.2**: Как пользователь, я хочу видеть график стоимости по дням за последние 30 дней, чтобы отслеживать тренд.
- **US-6.3**: Как пользователь, я хочу видеть breakdown стоимости по воркфлоу, чтобы определить самый дорогой.
- **US-6.4**: Как пользователь, я хочу видеть success rate (% успешных запусков), чтобы оценить надёжность.
- **US-6.5**: Как пользователь, я хочу экспортировать логи в CSV/JSON, чтобы анализировать офлайн.

### 6.2 Модель данных

Нет отдельных таблиц — аналитика агрегируется из `executions` и `execution_logs` через SQL-запросы.

**Ключевые запросы**:

```sql
-- KPI за текущий месяц
SELECT
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE status = 'completed') as successful,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    SUM(total_tokens) as tokens_used,
    SUM(total_cost) as total_cost
FROM executions
WHERE tenant_id = :tenant_id
  AND created_at >= date_trunc('month', now());

-- Стоимость по дням (30 дней)
SELECT
    date_trunc('day', created_at) as day,
    SUM(total_cost) as daily_cost,
    COUNT(*) as executions_count
FROM executions
WHERE tenant_id = :tenant_id
  AND created_at >= now() - interval '30 days'
GROUP BY day
ORDER BY day;

-- Breakdown по воркфлоу
SELECT
    w.name as workflow_name,
    COUNT(e.id) as runs,
    SUM(e.total_cost) as cost,
    AVG(EXTRACT(EPOCH FROM (e.completed_at - e.started_at))) as avg_duration_sec
FROM executions e
JOIN workflows w ON e.workflow_id = w.id
WHERE e.tenant_id = :tenant_id
  AND e.created_at >= date_trunc('month', now())
GROUP BY w.id, w.name
ORDER BY cost DESC;
```

### 6.3 API

| Метод | Путь | Тело | Ответ | Ошибки |
|-------|------|------|-------|--------|
| GET | `/api/v1/analytics/overview` | query: `?period=month` | 200: `{total_executions, successful, failed, tokens_used, total_cost, success_rate}` | 401 |
| GET | `/api/v1/analytics/cost-timeline` | query: `?days=30` | 200: `[{day, daily_cost, executions_count}]` | 401 |
| GET | `/api/v1/analytics/workflow-breakdown` | query: `?period=month` | 200: `[{workflow_name, runs, cost, avg_duration_sec}]` | 401 |
| GET | `/api/v1/analytics/export` | query: `?format=csv&from=&to=` | 200: file download (CSV or JSON) | 401 |

### 6.4 Экраны и компоненты

**DashboardPage.jsx**
- Layout: KPI cards (top row) + Cost Chart (middle) + Workflow Table (bottom).

**MetricsGrid.jsx** (KPI cards)
- 4 карточки в ряд:
  1. Total Executions (число + % change vs. prev month)
  2. Success Rate (% + progress bar)
  3. Tokens Used (число + bar: used/budget)
  4. Total Cost ($XX.XX + trend arrow)
- Refresh каждые 60 секунд.

**CostChart.jsx**
- Line chart (Recharts или Chart.js): ось X = дни, ось Y = стоимость ($).
- Tooltip: дата, стоимость, количество запусков.
- Бюджетная линия: горизонтальная красная пунктирная линия = monthly_token_budget в $.

**WorkflowBreakdown.jsx**
- Таблица: workflow_name, runs, cost, avg_duration, % от общей стоимости (progress bar).
- Сортировка по стоимости (desc по умолчанию).

### 6.5 Бизнес-логика

- Все аналитические запросы фильтруются по `tenant_id` из JWT.
- Success rate = `completed / total * 100`. Если total = 0 — показать "N/A".
- Cost timeline заполняет пропущенные дни нулями (чтобы на графике не было разрывов).
- Export: CSV содержит columns: execution_id, workflow_name, status, tokens, cost, started_at, completed_at. JSON — массив объектов.
- Данные кешируются на 60 секунд (server-side). Кеш инвалидируется при новом execution.

### 6.6 Крайние случаи

- **Нет данных за период**: все KPI = 0, график пустой с сообщением "No executions in this period".
- **Очень большой export (>10000 записей)**: стримить файл, не загружать всё в память. Лимит: 50000 записей.
- **Timezone**: все даты в UTC на бэкенде. Frontend конвертирует в локальный timezone пользователя.
- **Budget = 0 (free plan без бюджета)**: не показывать budget line на графике.

---

## Модуль 7: System Infrastructure

### 7.1 Middleware & Security

**TenantMiddleware**:
```python
# Каждый запрос (кроме auth) проходит через:
# 1. Извлечь JWT из Authorization header
# 2. Декодировать, получить user_id и tenant_id
# 3. Проверить что user.is_active = true
# 4. Инжектировать tenant_id в request.state.tenant_id
# 5. Все последующие DB-запросы фильтруют по tenant_id
```

**CORS**:
- Development: allow origin `http://localhost:3000`
- Production: allow origin только конкретный домен

**Rate Limiting**:
- Per tenant: 100 requests/min на API
- Per execution: 1 concurrent execution на free, 5 на pro, 20 на team

### 7.2 Docker Compose

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: agentic_platform
      POSTGRES_USER: platform
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://platform:${DB_PASSWORD}@db:5432/agentic_platform
      JWT_SECRET: ${JWT_SECRET}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports: ["8000:8000"]
    depends_on: [db]

  frontend:
    build: ./frontend
    environment:
      REACT_APP_API_URL: http://localhost:8000
    ports: ["3000:3000"]
    depends_on: [backend]

volumes:
  pgdata:
```

### 7.3 Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://platform:password@localhost:5432/agentic_platform

# Auth
JWT_SECRET=<random-256-bit-key>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# App
APP_ENV=development  # development | production
CORS_ORIGINS=http://localhost:3000
```

### 7.4 Alembic Migrations

- Initial migration: создаёт все таблицы (tenants, users, workflows, agent_configs, tool_registry, executions, execution_logs).
- Naming convention: `{rev}_{description}.py` (e.g., `001_initial_schema.py`).
- Каждая миграция — идемпотентна. Alembic автоматически генерирует через `alembic revision --autogenerate -m "description"`.

---

## Зависимости между модулями

```
Auth & Tenants (M1) ← базовая зависимость для всех модулей
       ↓
Workflow CRUD (M2) ← зависит от M1 (tenant_id, user auth)
       ↓
Builder UI (M3) ← зависит от M2 (workflow definition) + M5 (tools для agent config)
       ↓
Execution Engine (M4) ← зависит от M2 (workflow) + M3 (agent_configs) + M5 (tool_registry)
       ↓
Dashboard (M6) ← зависит от M4 (executions, execution_logs)

Tool Registry (M5) ← зависит от M1, используется M3 и M4
```

**Порядок реализации**: M1 → M2 → M5 → M3 → M4 → M6 → M7 (infra параллельно с M1)

---

## SPEC_TEMPLATE.md — Шаблон для новых фич

```markdown
# Спецификация фичи: [НАЗВАНИЕ]

## Описание
[Что делает, для кого, зачем]

## User Stories
- Как [роль], я хочу [действие], чтобы [результат].

## Модель данных
[Таблицы, поля, типы, constraints, FK, индексы]

## API
| Метод | Путь | Тело | Ответ | Ошибки |
|-------|------|------|-------|--------|

## Экраны и компоненты
[Страницы, компоненты, состояния: loading, loaded, empty, error]

## Бизнес-логика
[Правила, валидации, формулы, условия]

## Крайние случаи
[Что может пойти не так, ожидаемое поведение]

## Приоритет
[MVP | v2 | v3]

## Зависимости
[От каких модулей зависит]
```
