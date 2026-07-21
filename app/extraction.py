"""LLM extraction of claim fields — the only module that touches a model.

Provider swap: set ANALYZE_CLAIM_MODEL (e.g. "openai:gpt-...") and the
provider's API key env var (ANTHROPIC_API_KEY / OPENAI_API_KEY / ...), and
add the matching extra: uv add "pydantic-ai-slim[openai]".
"""

import os

from pydantic_ai import Agent

from app.schema import RawExtraction, VinConsistencyVerdict

MODEL = os.environ.get("ANALYZE_CLAIM_MODEL", "anthropic:claude-opus-4-8")

agent = Agent(
    MODEL,
    output_type=RawExtraction,
    instructions=(
        "Extract the requested fields from the automotive repair order text. "
        "Return null for any field not present in the text. "
        "Exception: if the make is unstated but clearly implied by the model "
        "name (e.g. Camry implies Toyota), fill it in. Never infer any field "
        "from the VIN — it is used separately as an independent consistency "
        "check. "
        "Mileage must be an integer with commas and units stripped. "
        "Return the vehicle make as the canonical brand name — e.g. 'Chevrolet' "
        "not 'Chevy', 'Volkswagen' not 'VW', 'Ram' not 'Dodge Ram' for 2011+ "
        "trucks — the brand only, not the parent company."
    ),
)


async def extract_claim(ro_text: str) -> RawExtraction:
    result = await agent.run(ro_text)
    return result.output


consistency_agent = Agent(
    MODEL,
    output_type=VinConsistencyVerdict,
    instructions=(
        "You verify whether a VIN is consistent with a claimed vehicle identity. "
        "You are given the VIN, facts decoded locally from it (authoritative when "
        "present), and the make/model/year claimed in a repair order. Judge "
        "make_consistent and model_consistent from the VIN's WMI and VDS structure. "
        "Return null for any judgment you cannot make confidently — only return "
        "false when the VIN clearly contradicts the claim; give the benefit of "
        "the doubt."
    ),
)


async def check_vin_consistency(
    *,
    vin: str,
    decoded_year: int | None,
    decoded_make: str | None,
    claimed_year: int | None,
    claimed_make: str,
    claimed_model: str,
) -> VinConsistencyVerdict:
    lines = [f"VIN: {vin}"]
    if decoded_year is not None:
        lines.append(f"Locally decoded model year (authoritative): {decoded_year}")
    if decoded_make is not None:
        lines.append(
            f"Locally decoded make (authoritative, already verified): {decoded_make}. "
            "Judge only the model; set make_consistent to null."
        )
    lines.append(
        f"Claimed in repair order: year={claimed_year}, make={claimed_make}, model={claimed_model}"
    )
    result = await consistency_agent.run("\n".join(lines))
    return result.output
