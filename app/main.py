from fastapi import FastAPI

from app.errors import coverage_http_exception, validation_http_exception
from app.extraction import check_vin_consistency, extract_claim
from app.schema import AnalyzeClaimRequest, ClaimAnalysisResponse
from app.validators import (
    consistency_verdict_issues,
    cross_validate_vin,
    validate_extraction,
    vin_basic_ok,
)
from app.vin_decode import decode_make, decode_model_year
from app.warranty_coverage import check_warranty_coverage

app = FastAPI(title="AnalyzeMyClaim")


@app.post("/analyze-claim", response_model=ClaimAnalysisResponse)
async def analyze_claim(req: AnalyzeClaimRequest) -> ClaimAnalysisResponse:
    raw = await extract_claim(req.ro_text)

    issues = validate_extraction(raw)
    # VIN-derived cross-checks only make sense on a VIN that passed basic
    # validation; issues are still collected all-at-once with the rest.
    if vin_basic_ok(raw):
        issues += cross_validate_vin(raw)
        if raw.make is not None and raw.model is not None:
            decoded_make = decode_make(raw.vin)
            verdict = await check_vin_consistency(
                vin=raw.vin,
                decoded_year=decode_model_year(raw.vin),
                decoded_make=decoded_make,
                claimed_year=raw.year,
                claimed_make=raw.make,
                claimed_model=raw.model,
            )
            issues += consistency_verdict_issues(verdict, raw, make_locally_decided=decoded_make is not None)
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
