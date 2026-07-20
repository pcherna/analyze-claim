from datetime import datetime

import pytest

from app.schema import RawExtraction, VinConsistencyVerdict
from app.validators import (
    compute_vin_check_digit,
    consistency_verdict_issues,
    cross_validate_vin,
    validate_extraction,
    validate_labor_hours,
    validate_make,
    validate_mileage,
    validate_model,
    validate_part_number,
    validate_repair_description,
    validate_vin,
    validate_year,
    vin_basic_ok,
)

SAMPLE_VIN_INVALID = "1G1FY6S00N0000123"  # check digit should be 'X', has '0'
SAMPLE_VIN_VALID = "1G1FY6S0XN0000123"


class TestVinCheckDigit:
    @pytest.mark.parametrize(
        "vin, expected",
        [
            ("1M8GDM9AXKP042788", "X"),  # canonical 'X' example
            ("11111111111111111", "1"),
            (SAMPLE_VIN_VALID, "X"),
        ],
    )
    def test_known_check_digits(self, vin, expected):
        assert compute_vin_check_digit(vin) == expected

    def test_sample_vin_fails(self):
        assert compute_vin_check_digit(SAMPLE_VIN_INVALID) == "X"
        assert SAMPLE_VIN_INVALID[8] == "0"


class TestValidateVin:
    def test_valid(self):
        assert validate_vin(SAMPLE_VIN_VALID) is None

    def test_lowercase_accepted(self):
        assert validate_vin(SAMPLE_VIN_VALID.lower()) is None

    def test_check_digit_mismatch(self):
        issue = validate_vin(SAMPLE_VIN_INVALID)
        assert issue is not None
        assert issue.field == "vin"
        assert "check digit" in issue.message
        assert "'X'" in issue.message

    def test_wrong_length(self):
        issue = validate_vin("1G1FY6S0X")
        assert issue is not None
        assert "17 characters" in issue.message

    @pytest.mark.parametrize("bad_char", ["I", "O", "Q"])
    def test_forbidden_characters(self, bad_char):
        vin = bad_char + SAMPLE_VIN_VALID[1:]
        issue = validate_vin(vin)
        assert issue is not None
        assert "invalid characters" in issue.message


class TestFieldValidators:
    def test_year_bounds(self):
        current = datetime.now().year
        assert validate_year(1980) is None
        assert validate_year(current + 1) is None
        assert validate_year(1979) is not None
        assert validate_year(current + 2) is not None

    def test_mileage_bounds(self):
        assert validate_mileage(0) is None
        assert validate_mileage(12340) is None
        assert validate_mileage(-1) is not None
        assert validate_mileage(2_000_001) is not None

    def test_labor_hours_bounds(self):
        assert validate_labor_hours(4.2) is None
        assert validate_labor_hours(0) is not None
        assert validate_labor_hours(-1.0) is not None
        assert validate_labor_hours(501) is not None

    @pytest.mark.parametrize("validator", [validate_make, validate_model, validate_repair_description])
    def test_string_fields_reject_blank(self, validator):
        assert validator("   ") is not None
        assert validator("Chevrolet") is None

    def test_part_number(self):
        assert validate_part_number("24299461") is None
        assert validate_part_number("  ") is not None
        assert validate_part_number("x" * 51) is not None


def _valid_extraction(**overrides) -> RawExtraction:
    data = dict(
        vin=SAMPLE_VIN_VALID,
        year=2022,
        make="Chevrolet",
        model="Bolt EV",
        mileage=12340,
        repair_description="Replaced high-voltage battery module",
        part_number="24299461",
        labor_hours=4.2,
    )
    data.update(overrides)
    return RawExtraction(**data)


class TestValidateExtraction:
    def test_valid_extraction_no_issues(self):
        assert validate_extraction(_valid_extraction()) == []

    def test_part_number_optional(self):
        assert validate_extraction(_valid_extraction(part_number=None)) == []

    def test_missing_required_fields_all_reported(self):
        raw = _valid_extraction(vin=None, mileage=None)
        issues = validate_extraction(raw)
        assert {i.field for i in issues} == {"vin", "mileage"}
        assert all("missing" in i.message for i in issues)

    def test_multiple_failures_all_reported(self):
        raw = _valid_extraction(vin=SAMPLE_VIN_INVALID, labor_hours=-1.0, year=1900)
        issues = validate_extraction(raw)
        assert {i.field for i in issues} == {"vin", "labor_hours", "year"}


class TestCrossValidateVin:
    def test_all_consistent(self):
        assert validate_extraction(_valid_extraction()) == []
        assert cross_validate_vin(_valid_extraction()) == []

    def test_year_mismatch(self):
        issues = cross_validate_vin(_valid_extraction(year=2023))
        assert len(issues) == 1
        assert issues[0].field == "year"
        assert "'N'" in issues[0].message

    def test_year_previous_cycle_accepted(self):
        assert cross_validate_vin(_valid_extraction(year=1992)) == []  # 'N' is 1992 too

    def test_make_mismatch(self):
        issues = cross_validate_vin(_valid_extraction(make="Ford"))
        assert len(issues) == 1
        assert issues[0].field == "make"
        assert "1G1" in issues[0].message and "Chevrolet" in issues[0].message

    def test_make_comparison_case_insensitive(self):
        assert cross_validate_vin(_valid_extraction(make="CHEVROLET")) == []

    def test_unknown_wmi_no_make_issue(self):
        base = "WVWAA7AJ0BW000001"  # Volkswagen — not in the local table
        vin = base[:8] + compute_vin_check_digit(base) + base[9:]
        issues = cross_validate_vin(_valid_extraction(vin=vin, make="Volkswagen", year=2011))
        assert issues == []


class TestConsistencyVerdictIssues:
    def _verdict(self, **kwargs):
        return VinConsistencyVerdict(**kwargs)

    def test_all_none_gives_no_issues(self):
        verdict = self._verdict()
        assert consistency_verdict_issues(verdict, _valid_extraction(), make_locally_decided=False) == []

    def test_model_inconsistent(self):
        verdict = self._verdict(model_consistent=False, issues=["VDS says Bolt EUV"])
        issues = consistency_verdict_issues(verdict, _valid_extraction(), make_locally_decided=True)
        assert [i.field for i in issues] == ["model"]
        assert "VDS says Bolt EUV" in issues[0].message

    def test_make_inconsistent_when_not_locally_decided(self):
        verdict = self._verdict(make_consistent=False)
        issues = consistency_verdict_issues(verdict, _valid_extraction(), make_locally_decided=False)
        assert [i.field for i in issues] == ["make"]

    def test_make_verdict_ignored_when_locally_decided(self):
        verdict = self._verdict(make_consistent=False)
        assert consistency_verdict_issues(verdict, _valid_extraction(), make_locally_decided=True) == []


class TestVinBasicOk:
    def test_valid(self):
        assert vin_basic_ok(_valid_extraction()) is True

    def test_invalid_check_digit(self):
        assert vin_basic_ok(_valid_extraction(vin=SAMPLE_VIN_INVALID)) is False

    def test_missing_vin(self):
        assert vin_basic_ok(_valid_extraction(vin=None)) is False
