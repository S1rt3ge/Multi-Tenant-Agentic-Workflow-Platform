"""
Base agent runtime for executing LLM calls within workflow steps.

Handles:
- OpenAI and Anthropic provider routing
- Exponential backoff retry (max 3 attempts) for 429 errors
- 30s timeout per LLM call
- Tool call processing
- Cost tracking per step
"""

import asyncio
import time
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import AgentConfig
from app.models.tool_registry import ToolRegistry
from app.engine.cost import calculate_cost
from app.engine.tools.executor import execute_tool

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds


async def execute_agent(
    agent_config: AgentConfig,
    state: dict[str, Any],
    db: AsyncSession,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Execute a single agent step.

    Args:
        agent_config: The agent configuration from DB.
        state: Current workflow state dict.
        db: Database session for loading tools.
        tenant_id: Current tenant ID.

    Returns:
        Dict with keys:
            output (str): Agent response text.
            input_tokens (int): Tokens used for input.
            output_tokens (int): Tokens used for output.
            cost (float): Cost in USD.
            duration_ms (int): Duration in milliseconds.
            reasoning (str|None): Decision reasoning if any.
            action (str): 'llm_call' or 'error'.
    """
    start = time.time()

    # Build messages
    messages = _build_messages(agent_config, state)

    # Load tools if agent has tool references
    tool_results = []
    if agent_config.tools:
        tool_results = await _execute_agent_tools(agent_config, state, db, tenant_id)

    # Append tool results to context if any
    if tool_results:
        tool_context = "\n\n--- Tool Results ---\n"
        for tr in tool_results:
            tool_context += f"[{tr['tool_name']}]: {tr['output']}\n"
        messages.append({"role": "user", "content": tool_context})

    # Call LLM with retry
    model = agent_config.model
    try:
        result = await _call_llm_with_retry(
            model=model,
            messages=messages,
            max_tokens=agent_config.max_tokens,
            temperature=agent_config.temperature,
        )
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.error(f"Agent '{agent_config.name}' LLM call failed: {e}")
        return {
            "output": str(e),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "duration_ms": elapsed,
            "reasoning": None,
            "action": "error",
        }

    elapsed = int((time.time() - start) * 1000)

    input_tokens = result.get("input_tokens", 0)
    output_tokens = result.get("output_tokens", 0)
    cost = calculate_cost(model, input_tokens, output_tokens)

    return {
        "output": result.get("content", ""),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "duration_ms": elapsed,
        "reasoning": result.get("reasoning"),
        "action": "llm_call",
    }


def _build_messages(agent_config: AgentConfig, state: dict[str, Any]) -> list[dict[str, str]]:
    """Build the message list for the LLM call."""
    messages = []

    # System prompt
    messages.append({
        "role": "system",
        "content": agent_config.system_prompt,
    })

    # Add previous messages from state (conversation history)
    state_messages = state.get("messages", [])
    for msg in state_messages:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    # Add results from previous agents as context
    results = state.get("results", {})
    if results:
        context_parts = []
        for agent_name, result in results.items():
            if agent_name != agent_config.name:
                context_parts.append(f"[{agent_name}]: {result}")
        if context_parts:
            messages.append({
                "role": "user",
                "content": "Previous agent results:\n" + "\n".join(context_parts),
            })

    return messages


async def _execute_agent_tools(
    agent_config: AgentConfig,
    state: dict[str, Any],
    db: AsyncSession,
    tenant_id: UUID,
) -> list[dict[str, Any]]:
    """Execute tools configured for this agent."""
    results = []

    # agent_config.tools is a list of dicts like [{"id": "...", "name": "..."}]
    for tool_ref in agent_config.tools:
        tool_id = tool_ref.get("id") or tool_ref.get("tool_id")
        tool_name = tool_ref.get("name", "unknown")

        if not tool_id:
            continue

        # Load tool from DB
        try:
            from uuid import UUID as PyUUID
            tid = PyUUID(str(tool_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid tool ID: {tool_id}")
            results.append({
                "tool_name": tool_name,
                "success": False,
                "output": f"Invalid tool ID: {tool_id}",
            })
            continue

        stmt = select(ToolRegistry).where(
            ToolRegistry.id == tid,
            ToolRegistry.tenant_id == tenant_id,
            ToolRegistry.is_active == True,  # noqa: E712
        )
        db_result = await db.execute(stmt)
        tool = db_result.scalar_one_or_none()

        if tool is None:
            logger.warning(f"Tool '{tool_name}' not found, skipping")
            results.append({
                "tool_name": tool_name,
                "success": False,
                "output": f"Tool {tool_name} not found, skipping",
            })
            continue

        # Use the last user message or metadata as tool input
        tool_input = ""
        state_messages = state.get("messages", [])
        if state_messages:
            tool_input = state_messages[-1].get("content", "")

        tool_result = await execute_tool(tool.tool_type, tool.config, tool_input)
        results.append({
            "tool_name": tool.name,
            "success": tool_result.get("success", False),
            "output": tool_result.get("output", ""),
        })

    return results


async def _call_llm_with_retry(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """Call LLM with exponential backoff retry for 429 errors.

    Returns dict with keys: content, input_tokens, output_tokens, reasoning.
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            result = await asyncio.wait_for(
                _call_llm(model, messages, max_tokens, temperature),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            return result
        except asyncio.TimeoutError:
            raise Exception(f"LLM call timed out after {LLM_TIMEOUT_SECONDS}s")
        except RateLimitError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES}), "
                    f"retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                raise Exception(
                    f"LLM rate limited after {MAX_RETRIES} retries: {str(e)}"
                )
        except Exception as e:
            raise

    raise last_error or Exception("LLM call failed")


class RateLimitError(Exception):
    """Raised when LLM API returns 429."""
    pass


async def _call_llm(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """Call the appropriate LLM provider based on model name.

    Returns dict with: content, input_tokens, output_tokens, reasoning.
    """
    if model.startswith("gpt-"):
        return await _call_openai(model, messages, max_tokens, temperature)
    elif model.startswith("claude-"):
        return await _call_anthropic(model, messages, max_tokens, temperature)
    else:
        raise Exception(f"Unsupported model: {model}")


async def _call_openai(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """Call OpenAI API."""
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")

    try:
        from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimit
    except ImportError:
        raise Exception("openai package not installed")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Map our model names to OpenAI model names
    model_map = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
    }
    openai_model = model_map.get(model, model)

    try:
        response = await client.chat.completions.create(
            model=openai_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        choice = response.choices[0]
        usage = response.usage

        return {
            "content": choice.message.content or "",
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "reasoning": None,
        }
    except OpenAIRateLimit as e:
        raise RateLimitError(str(e))


async def _call_anthropic(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    """Call Anthropic API."""
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.ANTHROPIC_API_KEY:
        raise Exception("ANTHROPIC_API_KEY not configured")

    try:
        from anthropic import AsyncAnthropic, RateLimitError as AnthropicRateLimit
    except ImportError:
        raise Exception("anthropic package not installed")

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Map our model names to Anthropic model names
    model_map = {
        "claude-sonnet": "claude-sonnet-4-20250514",
        "claude-opus": "claude-opus-4-20250514",
    }
    anthropic_model = model_map.get(model, model)

    # Extract system message
    system_prompt = ""
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            chat_messages.append(msg)

    # Anthropic requires at least one user message
    if not chat_messages:
        chat_messages.append({"role": "user", "content": "Please proceed."})

    try:
        response = await client.messages.create(
            model=anthropic_model,
            system=system_prompt,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return {
            "content": content,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "reasoning": None,
        }
    except AnthropicRateLimit as e:
        raise RateLimitError(str(e))
