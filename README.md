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

## Docker

```bash
docker compose up --build
```

Or without compose:

```bash
docker build -t analyzemyclaim .
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY analyzemyclaim
```

Both pass `ANTHROPIC_API_KEY` (and optionally `ANALYZE_CLAIM_MODEL`) through from
your shell environment; the key must be set or the app exits at startup.

The image installs locked dependencies with uv (`uv sync --frozen --no-dev`) and
runs uvicorn as a non-root user on port 8000.

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

## VIN cross-validation

Beyond the check digit, the claimed vehicle identity is verified against the VIN:

- **Year** — VIN position 10 is compared against the claimed year's code locally
  (modulo the 30-year cycle).
- **Make** — the WMI (first 3 chars) is decoded locally for the top 10 North
  American makes (extensible table in `app/vin_decode.py`).
- **Model always, and make for brands outside the table** — judged by a second,
  small LLM call that receives the locally decoded facts. It is instructed to
  flag only clear contradictions (a false pass is preferred over a false
  rejection).

Any mismatch joins the 422 `errors` list, so a 200 means the VIN fully checked out.

## Structure

| Module | Purpose |
| --- | --- |
| `app/main.py` | Endpoint + orchestration: extract → validate → coverage |
| `app/schema.py` | Extraction schema, `REQUIRED_FIELDS` (the one place to change requiredness), response model |
| `app/extraction.py` | Pydantic AI agents (extraction + VIN consistency) — the only LLM-touching module |
| `app/vin_decode.py` | Local VIN decoding: year code (position 10) + WMI make table |
| `app/validators.py` | Per-field validators, VIN check digit, VIN cross-checks; all failures collected |
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

There is a separate set of tests that runs if an API key is set up. To invoke that set:

```bash
uv run ptyest -m llm
```

## Design Decisions, Assumptions, and Notes

- I chose to validate the VIN check-digit in a function rather than LLM, to avoid hallucinations (also helps cost).
- For VIN-year extraction, I chose to do that in a function (simple, helps cost). For VIN-make extraction, since I already have functions I did a function to do the basic work (common makes), with an LLM fallback for less common ones. I'm relying on the LLM for the VIN-model info, so that part exists regardless. (If the LLM was both accurate and cheap-at-scale, splitting the model work feels premature).
- Our clients might prefer HTTP 200 with `success: false` -- easy to change.
- The test cases that use the LLM can be extended as we find cases that fail that in turn make us want to refine the prompt.

## AI Tools Used

- Used Claude Fable 5 to generate the initial version from a plan session. Ways it helped:
  - Claude took care of all easy mechanical issues (project setup/structure, uv, etc.) This let me think about the problem at the most effective and valuable level of detail.
  - Claude spotted some issues in the challenge-spec (duplicate year field in definition, sample VIN having invalid check digit)
  - It suggested using a function rather than LLM to validate the VIN (which was already my thought). When I dove in, I asked it to defer the VIN-model logic to the LLM (though we could have integrated with an API or database if available.)
  - Mostly because I'm keeping a function for VIN validation, I ended up with two LLM calls. I explored the trade-offs of reducing that to one, with Claude.
- Use Claude to drive the creation of test-cases that use the LLM, and dockerizing. Keeps me focused on the real goals.
- Used Claude to generate another test case (we could do more). I had it make "Murano" without explicit "Nissan", nice to be able to test or refine product requirements at a high level. Disappointed that Claude initially used my test case to populate the prompt -- I made it change that.
- Used Cursor editor mostly to view (I started to add vertical bars as delimiters in the LLM extraction fields table, and its AI autocomplete finished the job.)
