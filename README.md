# AnalyzeMyClaim

FastAPI service with a single endpoint, `POST /analyze-claim`, that takes a free-text
automotive repair order, extracts structured claim fields with an LLM (Pydantic AI +
Anthropic), validates them in plain Python (including the ISO 3779 VIN check digit),
runs a warranty coverage check, and returns the claim plus eligibility.

## Setup

Requires [uv](https://docs.astral.sh/uv/). Dependencies install on first run.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run uvicorn app.main:app --reload
```

## Usage

```bash
curl -s -X POST http://127.0.0.1:8000/analyze-claim \
  -H 'Content-Type: application/json' \
  -d '{"ro_text": "RO# 847291 | VIN: 1G1FY6S0XN0000123 | 2022 Chevrolet Bolt EV | Mileage: 12,340 | Repair: Replaced high-voltage battery module. | Parts: 24299461 (Battery Module Assembly) | Labor: 4.2 hrs"}'
```

**200** — extracted fields plus coverage:

```json
{
  "vin": "1G1FY6S0XN0000123",
  "year": 2022,
  "make": "Chevrolet",
  "model": "Bolt EV",
  "mileage": 12340,
  "repair_description": "Replaced high-voltage battery module",
  "part_number": "24299461",
  "labor_hours": 4.2,
  "coverage_eligible": false,
  "coverage_reason": "Age limit exceeded"
}
```

**422** — validation failure (invalid VIN check digit, missing required field, or a
coverage error), with a summary and per-field details:

```json
{
  "detail": {
    "summary": "Claim validation failed: 1 error(s) in fields vin",
    "errors": [
      {
        "field": "vin",
        "message": "VIN check digit invalid: expected 'X' at position 9, got '0'",
        "value": "1G1FY6S00N0000123"
      }
    ]
  }
}
```

## Structure

| Module | Purpose |
| --- | --- |
| `app/main.py` | Endpoint + orchestration: extract → validate → coverage |
| `app/schema.py` | Extraction schema, `REQUIRED_FIELDS` (the one place to change requiredness), response model |
| `app/extraction.py` | Pydantic AI agent — the only LLM-touching module |
| `app/validators.py` | Per-field validators + VIN check digit; all failures collected |
| `app/errors.py` | 422 shape (summary + per-field errors) |
| `app/warranty_coverage.py` | `check_warranty_coverage()` demo stub — real implementation drops in here |

## Swapping the LLM provider

1. Set `ANALYZE_CLAIM_MODEL` — e.g. `openai:gpt-...` or `google:gemini-...`
   (default: `anthropic:claude-opus-4-8`). No code changes.
2. Set that provider's API key env var (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, ...).
3. Add the provider extra: `uv add "pydantic-ai-slim[openai]"` (or install the full
   `pydantic-ai` package to bundle all providers).

## Tests

```bash
uv run pytest
```

No network or API key needed — the LLM is mocked with Pydantic AI's `FunctionModel`,
and `ALLOW_MODEL_REQUESTS = False` guarantees no real calls escape.
