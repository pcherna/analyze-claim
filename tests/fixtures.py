"""Sample repair orders and their expected extractions."""

SAMPLE_RO_TEXT = (
    "RO# 847291 | VIN: 1G1FY6S00N0000123|\n"
    "2022 Chevrolet Bolt EV | Mileage: 12,340 |\n"
    "Complaint: Battery warning light on, reduced range. |\n"
    "Repair: Replaced high-voltage battery module. |\n"
    "Parts: 24299461 (Battery Module Assembly) |\n"
    "Labor: 4.2 hrs | Tech: M. Rodriguez"
)

# What the LLM is expected to extract from SAMPLE_RO_TEXT. The VIN
# deliberately fails the ISO 3779 check digit (expected 'X' at position 9).
SAMPLE_EXTRACTION = {
    "vin": "1G1FY6S00N0000123",
    "year": 2022,
    "make": "Chevrolet",
    "model": "Bolt EV",
    "mileage": 12340,
    "repair_description": "Replaced high-voltage battery module",
    "part_number": "24299461",
    "labor_hours": 4.2,
}

# Same claim with the check digit corrected — the happy-path fixture.
VALID_EXTRACTION = {**SAMPLE_EXTRACTION, "vin": "1G1FY6S0XN0000123"}
