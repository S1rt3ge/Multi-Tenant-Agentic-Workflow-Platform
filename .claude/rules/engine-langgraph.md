---
description: Правила для LangGraph engine файлов
globs: ["backend/app/engine/**/*.py"]
---

# LangGraph Engine Rules

## Graph Compiler
- Input: `workflow.definition` (JSONB с nodes и edges).
- Output: LangGraph `StateGraph` с typed state.
- State schema: `{messages: list, current_agent: str, results: dict, metadata: dict}`.
- Каждый node в definition -> node function в StateGraph.
- Каждый edge -> transition (add_edge или add_conditional_edges).

## Agent Execution
- Каждый agent node function:
  1. Загружает agent_config (system_prompt, model, tools, temperature, max_tokens).
  2. Формирует messages: [system_prompt] + context из state.
  3. Вызывает LLM через соответствующий provider (OpenAI / Anthropic).
  4. Записывает execution_log (step, tokens, cost, reasoning).
  5. Обновляет state с результатом.
- Tool calls: через tool_service.py. Agent решает какой tool вызвать, executor выполняет.

## Cost Tracking
- После каждого LLM call — рассчитай cost: tokens * price_per_token (по модели).
- Обнови: execution.total_tokens, execution.total_cost, tenant.tokens_used_this_month.
- Проверяй budget ПЕРЕД каждым LLM call. Если превышен — остановить execution.

## Error Handling
- LLM 429 (rate limit): exponential backoff, max 3 retries.
- LLM timeout (>30s): cancel step, log error.
- Cyclic graph: max_iterations = 10. Force stop при превышении.
- Все ошибки записываются в execution_logs с action = "error".

## WebSocket
- Endpoint: `/api/v1/executions/{id}/stream`.
- Events: `{type: "step_start"|"step_complete"|"execution_complete"|"error", data: {...}}`.
- Отправлять event после каждого шага агента.
