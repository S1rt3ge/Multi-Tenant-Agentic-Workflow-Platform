# PROJECT_IDEA: Multi-Tenant Agentic Workflow Platform

---

## 1. Проблема

Построение продакшн-ready агентных систем на базе LLM — процесс, требующий **3-6 недель** даже для опытной команды. Основные боли:

- **Оркестрация**: разработчик вручную пишет связи между агентами (retriever -> analyzer -> validator). На граф из 5 агентов уходит ~40 часов boilerplate-кода.
- **Отсутствие визуализации**: отладка агентного графа происходит через логи в терминале. Невозможно увидеть, какой агент принял какое решение и почему.
- **Контроль затрат**: один запрос к GPT-4o стоит $0.01-0.03. Воркфлоу из 5 агентов с 3 итерациями — $0.15-0.45 за один запуск. При 1000 запусках/день — $150-450/день. Без трекинга бюджет сгорает за неделю.
- **Multi-tenancy**: SaaS-продукт требует изоляции данных между клиентами. Реализация row-level security + tenant middleware с нуля — 2-3 недели.
- **Аудируемость**: регуляторы (финансы, медицина) требуют полный лог решений AI. Существующие фреймворки не предоставляют audit trail из коробки.

**Итог**: разработчик тратит 70% времени на инфраструктуру и 30% — на бизнес-логику агентов.

---

## 2. Решение

No-code платформа для визуального проектирования, запуска и мониторинга агентных воркфлоу на базе LangGraph.

**Пошаговый процесс пользователя**:
1. **Создаёт тенант** — изолированное рабочее пространство с API-ключами и лимитами.
2. **Открывает Builder** — drag-and-drop canvas на React Flow. Перетаскивает ноды агентов, соединяет рёбрами.
3. **Настраивает агентов** — для каждой ноды задаёт: роль (system prompt), модель (GPT-4o, Claude, Llama), инструменты (API, БД, файлы), memory (short-term buffer, long-term vector store).
4. **Выбирает паттерн исполнения** — linear (последовательный), parallel (параллельный), cyclic (с обратной связью / swarm).
5. **Запускает воркфлоу** — система компилирует граф в LangGraph StateGraph, исполняет, пишет логи каждого шага.
6. **Мониторит** — в реальном времени видит: какой агент сейчас работает, сколько токенов потрачено, какие решения приняты.
7. **Анализирует** — дашборд с историей запусков, графиками стоимости, метриками успешности.

**Каждый шаг = модуль системы**. Это не абстрактная идея — это конкретная архитектура.

---

## 3. Почему сейчас

- **LangGraph зрелый** (v0.2+, 2025): стабильный API для циклических графов с состоянием. Год назад этого не было.
- **Рынок агентов взрывается**: по данным Gartner, к 2028 году 33% корпоративного ПО будет использовать AI-агентов (вместо 1% в 2024).
- **Конкуренты не закрыли нишу**: LangFlow/Flowise — визуальные, но без multi-tenancy и cost tracking. CrewAI/AutoGen — мощные, но code-only. Никто не объединяет визуальный билдер + multi-tenancy + аудируемость + контроль затрат.
- **Требования регуляторов растут**: EU AI Act (2025) требует прозрачности решений AI-систем. Audit trail — не фича, а необходимость.

---

## 4. Целевая аудитория

### Основная: разработчики и тех-лиды в стартапах (50-200 человек)
- **Задача**: быстро построить агентную систему для продукта (поддержка, аналитика, автоматизация).
- **Текущий инструмент**: пишут на LangChain/LangGraph вручную, отлаживают через print().
- **Боль**: 3-6 недель на инфраструктуру вместо бизнес-логики.

### Вторичная: AI-консультанты и агентства
- **Задача**: строить агентные системы для клиентов, каждый клиент — отдельный тенант.
- **Текущий инструмент**: кастомный код на каждый проект.
- **Боль**: нет переиспользования, каждый проект с нуля.

### Третичная: корпоративные команды с compliance-требованиями
- **Задача**: внедрить AI-агентов с полным аудитом решений.
- **Текущий инструмент**: внутренние решения, дорогие и медленные.
- **Боль**: нет готового инструмента с audit trail и cost controls.

---

## 5. Архитектура

### Диаграмма слоёв

```
┌─────────────────────────────────────────────────┐
│              Frontend (React + React Flow)       │
│  Builder Canvas │ Dashboard │ Logs │ Settings    │
├─────────────────────────────────────────────────┤
│              API Layer (FastAPI)                  │
│  REST endpoints │ WebSocket (live execution)     │
├─────────────────────────────────────────────────┤
│           Orchestration (LangGraph)              │
│  StateGraph compilation │ Agent execution        │
├─────────────────────────────────────────────────┤
│           Data Layer (PostgreSQL)                 │
│  Tenants │ Workflows │ Executions │ Logs         │
├─────────────────────────────────────────────────┤
│           Infrastructure (Docker)                │
│  Backend container │ Frontend container │ DB     │
└─────────────────────────────────────────────────┘
```

### Стек с обоснованием

| Технология | Роль | Почему именно она |
|------------|------|-------------------|
| FastAPI | Backend API | Async-native, автодокументация OpenAPI, DI из коробки, Python-экосистема для AI |
| LangGraph | Оркестрация агентов | Единственный фреймворк с поддержкой циклических графов + состояние + checkpoints |
| SQLAlchemy Async | ORM | Async-поддержка, зрелый, гибкие запросы, Alembic для миграций |
| PostgreSQL | База данных | jsonb для хранения графов, надёжность, масштабируемость, Row-Level Security |
| React (JS) | Frontend | Широкая экосистема, React Flow для графов, без TypeScript (по требованию) |
| React Flow | Визуальный граф | Лучшая библиотека для node-based UI, drag-and-drop, кастомные ноды |
| Tailwind CSS | Стили | Utility-first, быстрая разработка UI, консистентный дизайн |
| Docker | Деплой | Воспроизводимая среда, docker-compose для локальной разработки |
| Alembic | Миграции | Стандарт для SQLAlchemy, автогенерация миграций, откат |

### Модули с входами/выходами

| Модуль | Вход | Выход |
|--------|------|-------|
| Auth & Tenants | email, password, tenant_name | JWT-токен, tenant context |
| Workflow Builder UI | drag-and-drop действия пользователя | JSON-определение графа (nodes + edges) |
| Workflow Engine | JSON-определение графа | LangGraph StateGraph, результат исполнения |
| Agent Runtime | system_prompt, model, tools, input | agent_output, token_usage, decisions_log |
| Tool Registry | tool_name, config (API URL, headers) | callable tool для агента |
| Execution Logger | agent_step, tokens, decisions | execution_log запись в БД |
| Dashboard & Analytics | tenant_id, date_range | агрегированные метрики, графики |

---

## 6. Монетизация

| План | Цена | Воркфлоу | Агентов/граф | Запусков/мес | Фичи |
|------|------|----------|--------------|--------------|-------|
| Free | $0 | 2 | 3 | 100 | Базовый builder, логи 7 дней |
| Pro | $29/мес | 20 | 10 | 5,000 | Все паттерны (parallel, cyclic), логи 90 дней, экспорт |
| Team | $99/мес | Безлимит | 20 | 50,000 | Multi-user tenant, RBAC, API access, приоритетная поддержка |
| Enterprise | Custom | Безлимит | Безлимит | Безлимит | SSO, выделенная инфраструктура, SLA, audit export |

**Гейтинг фич**:
- Free: только linear паттерн, без API-доступа, без экспорта логов.
- Pro: все паттерны исполнения, webhook-интеграции, CSV-экспорт логов.
- Team: RBAC (owner, editor, viewer), API-ключи для программного запуска, JSON-экспорт.
- Enterprise: SSO (SAML/OIDC), dedicated DB, compliance-отчёты.

---

## 7. Конкуренты

| Конкурент | Что делает | Чего не хватает |
|-----------|-----------|-----------------|
| LangFlow | Визуальный builder для LangChain | Нет multi-tenancy, нет cost tracking, нет audit trail, только LangChain |
| Flowise | Open-source UI для LangChain | Нет tenant isolation, нет control costs, single-user |
| CrewAI | Multi-agent framework (Python) | Code-only, нет визуального builder, нет SaaS-фич |
| AutoGen (Microsoft) | Multi-agent conversations | Нет UI, нет multi-tenancy, сложная настройка |
| n8n | Workflow automation | Не специализирован на AI-агентах, нет LLM cost tracking |
| Dify.ai | LLM app builder | Ограниченная оркестрация, нет cyclic graphs, слабый multi-tenancy |

**Наше преимущество**: единственная платформа, объединяющая визуальный drag-and-drop builder + LangGraph (циклические графы) + полный multi-tenancy + cost tracking + audit trail.

---

## 8. План запуска

### Фаза 1 — MVP (недели 1-4)
**Цель**: работающий прототип с core-функционалом.
- Auth + tenant creation (email/password)
- Workflow builder (canvas + node config)
- Workflow engine (linear + parallel)
- Базовые роли агентов (retriever, analyzer, validator)
- Execution logs (шаги, токены, стоимость)
- **Метрика**: можно создать и запустить воркфлоу из 3 агентов

### Фаза 2 — Расширение (недели 5-6)
**Цель**: продвинутые паттерны и аналитика.
- Cyclic execution pattern (swarm)
- Tool registry (подключение внешних API)
- Dashboard с графиками стоимости и метриками
- Memory configuration (short-term, long-term)
- **Метрика**: cyclic workflow работает, дашборд показывает cost breakdown

### Фаза 3 — Production-ready (недели 7-8)
**Цель**: готовность к деплою и первым пользователям.
- RBAC (owner, editor, viewer) для Team-плана
- Webhook-интеграции (on_complete, on_error)
- Экспорт логов (CSV, JSON)
- Rate limiting и cost limits per tenant
- Docker production setup
- **Метрика**: платформа стабильна при 100 concurrent executions

---

## 9. Риски

| Риск | Вероятность | Импакт | Митигация |
|------|-------------|--------|-----------|
| LLM API costs спираль — тенанты генерируют неконтролируемые расходы | Высокая | Высокий | Hard cost limits per tenant, budget alerts, автоматическая остановка при превышении лимита |
| LangGraph breaking changes — API меняется между версиями | Средняя | Средний | Пинить версию, абстрагировать через adapter layer (`app/core/graph_compiler.py`) |
| Утечка данных между тенантами | Низкая | Критический | tenant_id в каждом запросе через middleware, тесты изоляции в CI, penetration testing |
| Производительность при масштабе — медленные запросы при 1000+ воркфлоу | Средняя | Средний | Async everywhere (SQLAlchemy async, FastAPI async), connection pooling, индексы на tenant_id + created_at |
| LLM provider downtime (OpenAI, Anthropic) | Средняя | Средний | Fallback на альтернативного провайдера, retry с exponential backoff, очередь задач |
| Сложность onboarding — пользователи не понимают как строить графы | Средняя | Высокий | Шаблоны готовых воркфлоу (support bot, data pipeline, content reviewer), интерактивный tutorial |

---

## 10. Техдетали

### Структура репозитория

```
Multi-Tenant Agentic Workflow Platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, middleware, CORS
│   │   ├── core/
│   │   │   ├── config.py            # Settings (Pydantic BaseSettings)
│   │   │   ├── security.py          # JWT, password hashing
│   │   │   ├── dependencies.py      # DI: get_db, get_current_tenant
│   │   │   └── graph_compiler.py    # JSON definition -> LangGraph StateGraph
│   │   ├── models/
│   │   │   ├── tenant.py            # Tenant SQLAlchemy model
│   │   │   ├── user.py              # User model (belongs to tenant)
│   │   │   ├── workflow.py          # Workflow model (definition as jsonb)
│   │   │   ├── agent_config.py      # Agent configuration model
│   │   │   ├── execution.py         # Execution run model
│   │   │   └── execution_log.py     # Step-by-step log model
│   │   ├── schemas/
│   │   │   ├── auth.py              # Login/Register schemas
│   │   │   ├── workflow.py          # Workflow CRUD schemas
│   │   │   ├── execution.py         # Execution schemas
│   │   │   └── analytics.py         # Dashboard schemas
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # POST /auth/signup, /auth/login
│   │   │   │   ├── tenants.py       # CRUD tenants
│   │   │   │   ├── workflows.py     # CRUD workflows + execute
│   │   │   │   ├── executions.py    # GET logs, status
│   │   │   │   ├── agents.py        # Agent config endpoints
│   │   │   │   ├── tools.py         # Tool registry endpoints
│   │   │   │   └── analytics.py     # Dashboard data
│   │   │   └── deps.py              # Route dependencies
│   │   ├── services/
│   │   │   ├── workflow_service.py   # Workflow business logic
│   │   │   ├── execution_service.py  # Execution orchestration
│   │   │   ├── agent_service.py      # Agent runtime
│   │   │   └── tool_service.py       # Tool execution
│   │   └── engine/
│   │       ├── compiler.py           # Graph JSON -> LangGraph
│   │       ├── executor.py           # Run compiled graph
│   │       ├── agents/
│   │       │   ├── base.py           # BaseAgent class
│   │       │   ├── retriever.py      # Retriever agent
│   │       │   ├── analyzer.py       # Analyzer agent
│   │       │   ├── validator.py      # Validator agent
│   │       │   └── escalator.py      # Escalator agent
│   │       └── tools/
│   │           ├── base.py           # BaseTool interface
│   │           ├── api_tool.py       # HTTP API tool
│   │           └── db_tool.py        # Database query tool
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                 # Migration files
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx                   # Router, auth context
│   │   ├── index.js                  # Entry point
│   │   ├── api/
│   │   │   └── client.js             # Axios instance с JWT
│   │   ├── components/
│   │   │   ├── builder/
│   │   │   │   ├── Canvas.jsx        # React Flow canvas
│   │   │   │   ├── AgentNode.jsx     # Custom node для агента
│   │   │   │   ├── EdgeConfig.jsx    # Edge configuration
│   │   │   │   └── Sidebar.jsx       # Node palette + settings
│   │   │   ├── execution/
│   │   │   │   ├── RunPanel.jsx      # Live execution view
│   │   │   │   └── LogViewer.jsx     # Step-by-step logs
│   │   │   ├── dashboard/
│   │   │   │   ├── CostChart.jsx     # Token cost graphs
│   │   │   │   └── MetricsGrid.jsx   # KPI cards
│   │   │   └── common/
│   │   │       ├── Layout.jsx        # App shell
│   │   │       ├── ProtectedRoute.jsx
│   │   │       └── LoadingSpinner.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── WorkflowListPage.jsx
│   │   │   ├── BuilderPage.jsx
│   │   │   ├── ExecutionPage.jsx
│   │   │   └── DashboardPage.jsx
│   │   ├── hooks/
│   │   │   ├── useAuth.js
│   │   │   ├── useWorkflow.js
│   │   │   └── useWebSocket.js
│   │   └── utils/
│   │       ├── graphValidation.js    # Validate graph before save
│   │       └── costCalculator.js     # Estimate execution cost
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.yml                # PostgreSQL + Backend + Frontend
├── .env.example
├── CLAUDE.md
├── TECH_SPEC.md
├── PROJECT_IDEA.md
└── .claude/
    ├── agents/
    ├── rules/
    └── skills/
```

### Ключевые таблицы БД

```sql
-- Тенанты (клиенты платформы)
tenants: id (uuid PK), name (text NOT NULL), plan (text DEFAULT 'free'),
         max_workflows (int DEFAULT 2), max_agents_per_workflow (int DEFAULT 3),
         monthly_token_budget (int DEFAULT 100000), created_at (timestamptz)

-- Пользователи
users: id (uuid PK), tenant_id (uuid FK -> tenants.id NOT NULL),
       email (text UNIQUE NOT NULL), password_hash (text NOT NULL),
       role (text DEFAULT 'editor'), created_at (timestamptz)

-- Воркфлоу (определения графов)
workflows: id (uuid PK), tenant_id (uuid FK -> tenants.id NOT NULL),
           name (text NOT NULL), description (text),
           definition (jsonb NOT NULL),  -- {nodes: [...], edges: [...]}
           execution_pattern (text DEFAULT 'linear'),  -- linear | parallel | cyclic
           is_active (boolean DEFAULT true), created_at (timestamptz), updated_at (timestamptz)

-- Конфигурации агентов
agent_configs: id (uuid PK), tenant_id (uuid FK), workflow_id (uuid FK),
               name (text NOT NULL), role (text NOT NULL),  -- retriever | analyzer | validator | escalator
               system_prompt (text NOT NULL), model (text DEFAULT 'gpt-4o'),
               tools (jsonb DEFAULT '[]'), memory_type (text DEFAULT 'buffer'),
               max_tokens (int DEFAULT 4096), temperature (float DEFAULT 0.7)

-- Зарегистрированные инструменты
tool_registry: id (uuid PK), tenant_id (uuid FK), name (text NOT NULL),
               tool_type (text NOT NULL),  -- api | database | file
               config (jsonb NOT NULL),  -- {url, headers, method} или {connection_string, query}
               is_active (boolean DEFAULT true)

-- Запуски воркфлоу
executions: id (uuid PK), tenant_id (uuid FK), workflow_id (uuid FK),
            status (text DEFAULT 'pending'),  -- pending | running | completed | failed | cancelled
            input_data (jsonb), output_data (jsonb),
            total_tokens (int DEFAULT 0), total_cost (float DEFAULT 0.0),
            started_at (timestamptz), completed_at (timestamptz)

-- Логи (каждый шаг агента)
execution_logs: id (uuid PK), execution_id (uuid FK), agent_config_id (uuid FK),
                step_number (int NOT NULL), action (text NOT NULL),
                input_data (jsonb), output_data (jsonb),
                tokens_used (int DEFAULT 0), cost (float DEFAULT 0.0),
                decision_reasoning (text),  -- почему агент принял это решение
                duration_ms (int), created_at (timestamptz)
```

### AI Pipeline (Workflow Execution)

```
User нажимает "Run"
  → Frontend POST /api/v1/executions {workflow_id, input_data}
    → Backend создаёт execution (status: pending)
    → graph_compiler.py: JSON definition → LangGraph StateGraph
    → executor.py: запускает StateGraph
      → Для каждого агента в графе:
        → agent_service.py: формирует промпт + tools
        → LLM API call (OpenAI / Anthropic / local)
        → execution_log: записывает step, tokens, cost, reasoning
        → Проверка cost limit: если превышен — stop execution
      → По завершении: execution.status = completed, output_data = result
    → WebSocket: уведомляет frontend о каждом шаге в реальном времени
```

### Ключевые технические решения

- **Изоляция тенантов**: `tenant_id` во всех таблицах + middleware `get_current_tenant()` инжектится через FastAPI Depends. Каждый запрос к БД автоматически фильтруется по tenant_id.
- **Graph Compiler**: JSON-определение (из React Flow) транслируется в LangGraph StateGraph. Формат: `{nodes: [{id, type, config}], edges: [{source, target, condition}]}`.
- **Cost Tracking**: каждый LLM-вызов пишет tokens_used и cost в execution_logs. Агрегация по tenant_id для dashboard.
- **WebSocket**: для live-обновления статуса исполнения. Frontend подписывается на `ws://api/v1/executions/{id}/stream`.
- **Retry & Error Handling**: при 429 (rate limit) — exponential backoff. При ошибке агента — пометка шага как failed, escalation к следующему агенту или остановка.
