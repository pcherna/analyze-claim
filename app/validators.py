"""Plain-Python validators for extracted claim fields.

Deliberately permissive sanity checks; every failure is collected so the
caller can report all problems at once.
"""

import re
from datetime import datetime

from app.errors import ValidationIssue
from app.schema import REQUIRED_FIELDS, RawExtraction

# ISO 3779 check-digit transliteration. I, O, Q are not valid VIN characters.
_TRANSLIT = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
    **{str(d): d for d in range(10)},
}
_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
_VIN_CHARSET = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def compute_vin_check_digit(vin: str) -> str:
    """Return the ISO 3779 check digit (position 9) for a 17-char VIN."""
    total = sum(_TRANSLIT[c] * w for c, w in zip(vin, _WEIGHTS))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def validate_vin(vin: str) -> ValidationIssue | None:
    vin = vin.strip().upper()
    if len(vin) != 17:
        return ValidationIssue(field="vin", message=f"VIN must be 17 characters, got {len(vin)}", value=vin)
    if not _VIN_CHARSET.match(vin):
        return ValidationIssue(
            field="vin", message="VIN contains invalid characters (I, O, Q are not allowed)", value=vin
        )
    # Check digit is formally mandatory only for North American VINs, but is
    # enforced universally here per spec.
    expected = compute_vin_check_digit(vin)
    if vin[8] != expected:
        return ValidationIssue(
            field="vin",
            message=f"VIN check digit invalid: expected '{expected}' at position 9, got '{vin[8]}'",
            value=vin,
        )
    return None


def validate_year(year: int) -> ValidationIssue | None:
    current = datetime.now().year
    if not 1980 <= year <= current + 1:
        return ValidationIssue(field="year", message=f"year must be between 1980 and {current + 1}", value=year)
    return None


def validate_make(make: str) -> ValidationIssue | None:
    if not make.strip() or len(make) > 100:
        return ValidationIssue(field="make", message="make must be a non-empty string of at most 100 characters", value=make)
    return None


def validate_model(model: str) -> ValidationIssue | None:
    if not model.strip() or len(model) > 100:
        return ValidationIssue(field="model", message="model must be a non-empty string of at most 100 characters", value=model)
    return None


def validate_mileage(mileage: int) -> ValidationIssue | None:
    if not 0 <= mileage <= 2_000_000:
        return ValidationIssue(field="mileage", message="mileage must be between 0 and 2,000,000", value=mileage)
    return None


def validate_repair_description(desc: str) -> ValidationIssue | None:
    if not desc.strip():
        return ValidationIssue(field="repair_description", message="repair_description must be non-empty", value=desc)
    return None


def validate_part_number(part_number: str) -> ValidationIssue | None:
    if not part_number.strip() or len(part_number) > 50:
        return ValidationIssue(
            field="part_number", message="part_number must be a non-empty string of at most 50 characters", value=part_number
        )
    return None


def validate_labor_hours(hours: float) -> ValidationIssue | None:
    if not 0 < hours <= 500:
        return ValidationIssue(field="labor_hours", message="labor_hours must be a positive number of at most 500", value=hours)
    return None


_FIELD_VALIDATORS = {
    "vin": validate_vin,
    "year": validate_year,
    "make": validate_make,
    "model": validate_model,
    "mileage": validate_mileage,
    "repair_description": validate_repair_description,
    "part_number": validate_part_number,
    "labor_hours": validate_labor_hours,
}


def validate_extraction(raw: RawExtraction) -> list[ValidationIssue]:
    """Run presence checks and all field validators; return every issue found."""
    issues: list[ValidationIssue] = []
    for name in sorted(REQUIRED_FIELDS):
        if getattr(raw, name) is None:
            issues.append(
                ValidationIssue(field=name, message=f"required field '{name}' missing from repair order")
            )
    for name, validator in _FIELD_VALIDATORS.items():
        value = getattr(raw, name)
        if value is None:
            continue  # missing required fields already reported above
        issue = validator(value)
        if issue is not None:
            issues.append(issue)
    return issues
