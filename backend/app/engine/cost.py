"""
Cost calculation for LLM API calls.

Pricing per 1M tokens (as of spec):
- GPT-4o: input $2.50, output $10.00
- GPT-4o-mini: input $0.15, output $0.60
- Claude Sonnet: input $3.00, output $15.00
- Claude Opus: input $15.00, output $75.00
"""

COST_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet": {"input": 3.00, "output": 15.00},
    "claude-opus": {"input": 15.00, "output": 75.00},
}


def _resolve_prices(model: str) -> dict[str, float]:
    if model in COST_PER_1M_TOKENS:
        return COST_PER_1M_TOKENS[model]
    # Match by model family prefix (e.g. "gpt-4o-2024-08-06", "claude-opus-4").
    lowered = (model or "").lower()
    for known, prices in COST_PER_1M_TOKENS.items():
        if lowered.startswith(known):
            return prices
    if "opus" in lowered:
        return COST_PER_1M_TOKENS["claude-opus"]
    if "sonnet" in lowered:
        return COST_PER_1M_TOKENS["claude-sonnet"]
    if lowered.startswith("gpt-4o-mini") or "mini" in lowered:
        return COST_PER_1M_TOKENS["gpt-4o-mini"]
    # Truly unknown: fall back to the most expensive known model so cost/budget
    # accounting never silently under-reports spend.
    return COST_PER_1M_TOKENS["claude-opus"]


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of an LLM call based on model and token counts.

    Returns cost in USD.
    """
    prices = _resolve_prices(model)
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return round(cost, 8)


def estimate_cost(model: str, estimated_input_tokens: int, estimated_output_tokens: int) -> float:
    """Estimate cost before making a call (for budget checks)."""
    return calculate_cost(model, estimated_input_tokens, estimated_output_tokens)
