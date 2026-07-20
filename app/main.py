from fastapi import FastAPI

from app.errors import coverage_http_exception, validation_http_exception
from app.extraction import extract_claim
from app.schema import AnalyzeClaimRequest, ClaimAnalysisResponse
from app.validators import validate_extraction
from app.warranty_coverage import check_warranty_coverage

app = FastAPI(title="AnalyzeMyClaim")


@app.post("/analyze-claim", response_model=ClaimAnalysisResponse)
async def analyze_claim(req: AnalyzeClaimRequest) -> ClaimAnalysisResponse:
    raw = await extract_claim(req.ro_text)

    issues = validate_extraction(raw)
    if issues:
        raise validation_http_exception(issues)

    try:
        coverage = check_warranty_coverage(
            vin=raw.vin,
            make=raw.make,
            model=raw.model,
            year=raw.year,
            mileage=raw.mileage,
            part_number=raw.part_number,
        )
    except ValueError as exc:
        raise coverage_http_exception(exc)

    # warranty_type from the coverage result is intentionally not exposed.
    return ClaimAnalysisResponse(
        **raw.model_dump(),
        coverage_eligible=coverage["eligible"],
        coverage_reason=coverage["reason"],
    )
