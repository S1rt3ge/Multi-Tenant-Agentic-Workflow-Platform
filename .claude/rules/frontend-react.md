---
description: Правила для frontend React-файлов
globs: ["frontend/**/*.{js,jsx,css}"]
---

# Frontend React Rules

## JavaScript Only
- ТОЛЬКО .js и .jsx файлы. НИКОГДА .ts или .tsx.
- Без TypeScript. Без PropTypes (опционально, но не обязательно).
- Используй JSDoc-комментарии для документации параметров.

## React Patterns
- Функциональные компоненты + hooks. Без class components.
- State management: React Context + useReducer для глобального (auth, tenant). useState для локального.
- Custom hooks в `src/hooks/`: useAuth, useWorkflow, useWebSocket, useApi.
- Компоненты: один компонент = один файл. Название файла = PascalCase.

## Стилизация
- Tailwind CSS для всех стилей. Без отдельных CSS-файлов (кроме global.css для @tailwind directives).
- Utility-first: `className="flex items-center gap-2 p-4 bg-white rounded-lg shadow"`.
- Адаптивность: mobile-first. `sm:`, `md:`, `lg:` breakpoints.

## API Calls
- Через axios instance из `src/api/client.js`.
- Interceptor автоматически добавляет JWT из localStorage.
- При 401 — interceptor пытается refresh token. Если fail — redirect на /login.
- Все API calls в custom hooks или service functions, НЕ в компонентах.

## React Flow (Builder)
- Custom nodes: `AgentNode.jsx` — отдельный компонент с Handle для input/output.
- Canvas state управляется через React Flow hooks: useNodesState, useEdgesState.
- Сохранение: debounce 2s, отправка PUT /workflows/{id} с полным definition.

## Состояния UI
- Каждая страница обрабатывает 4 состояния: loading (skeleton/spinner), loaded (data), empty (no data message), error (error message + retry).
- Loading: React Suspense или условный рендеринг.
- Toasts для уведомлений: success (зелёный), error (красный), info (синий).
