"""Extraction and response schemas for /analyze-claim."""

from pydantic import BaseModel, Field


class RawExtraction(BaseModel):
    """Fields the LLM extracts from a repair order.

    Every field is optional here so that missing data comes back as null
    instead of triggering the model's retry loop. Requiredness is enforced
    by the validation layer against REQUIRED_FIELDS below.
    """

    vin: str | None = Field(None, description="17-character Vehicle Identification Number")
    year: int | None = Field(None, description="Vehicle model year, e.g. 2022")
    make: str | None = Field(None, description="Vehicle make, e.g. Chevrolet")
    model: str | None = Field(None, description="Vehicle model, e.g. Bolt EV")
    mileage: int | None = Field(
        None, description="Odometer reading as an integer; strip commas and units, e.g. '12,340' -> 12340"
    )
    repair_description: str | None = Field(None, description="What repair was performed")
    part_number: str | None = Field(None, description="Part number used in the repair")
    labor_hours: float | None = Field(None, description="Labor hours as a decimal number")


# The single place to change which fields are required.
REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "vin",
        "year",
        "make",
        "model",
        "mileage",
        "repair_description",
        # "part_number",  # intentionally optional
        "labor_hours",
    }
)


class VinConsistencyVerdict(BaseModel):
    """LLM judgment of whether the VIN is consistent with the claimed vehicle.

    All fields optional for the same reason as RawExtraction: an unsure model
    returns null instead of triggering a retry loop.
    """

    make_consistent: bool | None = Field(
        None, description="Whether the VIN's WMI is consistent with the claimed make; null if you cannot judge"
    )
    model_consistent: bool | None = Field(
        None, description="Whether the VIN's VDS is consistent with the claimed model; null if uncertain"
    )
    issues: list[str] = Field(default_factory=list, description="Evidence for any false verdict")


class AnalyzeClaimRequest(BaseModel):
    ro_text: str


class ClaimAnalysisResponse(BaseModel):
    vin: str
    year: int
    make: str
    model: str
    mileage: int
    repair_description: str
    part_number: str | None
    labor_hours: float
    coverage_eligible: bool
    coverage_reason: str
