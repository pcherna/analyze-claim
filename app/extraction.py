"""LLM extraction of claim fields — the only module that touches a model.

Provider swap: set ANALYZE_CLAIM_MODEL (e.g. "openai:gpt-...") and the
provider's API key env var (ANTHROPIC_API_KEY / OPENAI_API_KEY / ...), and
add the matching extra: uv add "pydantic-ai-slim[openai]".
"""

import os

from pydantic_ai import Agent

from app.schema import RawExtraction

MODEL = os.environ.get("ANALYZE_CLAIM_MODEL", "anthropic:claude-opus-4-8")

agent = Agent(
    MODEL,
    output_type=RawExtraction,
    instructions=(
        "Extract the requested fields from the automotive repair order text. "
        "Return null for any field not present in the text. "
        "Mileage must be an integer with commas and units stripped. "
    ),
)


async def extract_claim(ro_text: str) -> RawExtraction:
    result = await agent.run(ro_text)
    return result.output
