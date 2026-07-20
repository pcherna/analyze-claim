from datetime import datetime

import pytest

from app.warranty_coverage import check_warranty_coverage

CURRENT_YEAR = datetime.now().year
VIN = "1G1FY6S0XN0000123"


def check(year=None, mileage=10_000, part_number="24299461"):
    if year is None:
        year = CURRENT_YEAR - 1  # comfortably within the age limit
    return check_warranty_coverage(VIN, "Chevrolet", "Bolt EV", year, mileage, part_number)


class TestEligibility:
    def test_within_coverage(self):
        result = check()
        assert result["eligible"] is True
        assert result["reason"] == "Within coverage"

    def test_age_limit(self):
        result = check(year=CURRENT_YEAR - 4)
        assert result["eligible"] is False
        assert result["reason"] == "Age limit exceeded"

    def test_age_boundary_just_inside(self):
        assert check(year=CURRENT_YEAR - 3)["eligible"] is True

    def test_mileage_limit(self):
        result = check(mileage=36_001)
        assert result["eligible"] is False
        assert result["reason"] == "Mileage limit exceeded"

    def test_mileage_boundary_inclusive(self):
        assert check(mileage=36_000)["eligible"] is True

    def test_age_takes_precedence_over_mileage(self):
        result = check(year=CURRENT_YEAR - 10, mileage=100_000)
        assert result["reason"] == "Age limit exceeded"


class TestWarrantyType:
    @pytest.mark.parametrize(
        "part_number, expected",
        [
            ("24299460", "Bronze Warranty"),
            ("24299463", "Bronze Warranty"),
            ("24299464", "Silver Warranty"),
            ("24299467", "Silver Warranty"),
            ("24299468", "Gold Warranty"),
            ("24299469", "Gold Warranty"),
            (None, "Bronze Warranty"),
            ("2429946A", "Bronze Warranty"),  # non-digit suffix falls back to Bronze
        ],
    )
    def test_tier_mapping(self, part_number, expected):
        assert check(part_number=part_number)["warranty_type"] == expected


def test_return_shape():
    assert set(check().keys()) == {"eligible", "reason", "warranty_type"}
