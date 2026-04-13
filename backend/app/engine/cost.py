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


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of an LLM call based on model and token counts.

    Returns cost in USD.
    """
    prices = COST_PER_1M_TOKENS.get(model)
    if prices is None:
        # Unknown model — default to gpt-4o pricing as fallback
        prices = COST_PER_1M_TOKENS["gpt-4o"]

    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return round(cost, 8)


def estimate_cost(model: str, estimated_input_tokens: int, estimated_output_tokens: int) -> float:
    """Estimate cost before making a call (for budget checks)."""
    return calculate_cost(model, estimated_input_tokens, estimated_output_tokens)
