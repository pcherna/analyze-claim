"""Warranty coverage check.

Demo stub — the real implementation will be supplied later and will replace
this module. The caller must guard against ValueError.
"""

from datetime import datetime


def check_warranty_coverage(
    vin: str,
    make: str,
    model: str,
    year: int,
    mileage: int,
    part_number: str | None,
) -> dict:
    """Checks warranty coverage eligibility for a vehicle and repair.

    Returns:
        {
            "eligible": bool,
            "reason": str,
            "warranty_type": str  # e.g. "Bronze Warranty"
        }

    Raises:
        ValueError: If VIN format is invalid or make/model combination is
            unknown. (This demo stub never raises — no make/model registry
            exists yet; the real implementation will.)
    """
    current_year = datetime.now().year
    if current_year - year >= 4:
        eligible, reason = False, "Age limit exceeded"
    elif mileage > 36_000:
        eligible, reason = False, "Mileage limit exceeded"
    else:
        eligible, reason = True, "Within coverage"  # could be enriched, e.g. component-specific terms

    # Tier from the last digit of the part number; missing or non-digit falls
    # back to Bronze.
    warranty_type = "Bronze Warranty"
    if part_number and part_number[-1].isdigit():
        last = int(part_number[-1])
        if 4 <= last <= 7:
            warranty_type = "Silver Warranty"
        elif last >= 8:
            warranty_type = "Gold Warranty"

    return {"eligible": eligible, "reason": reason, "warranty_type": warranty_type}
