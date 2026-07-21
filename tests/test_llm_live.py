"""Tests that call the real model. Deselected by default (pyproject addopts);
run with `pytest -m llm` and a real ANTHROPIC_API_KEY in the environment.

Assertion policy: exact for what the extraction prompt promises
deterministically (mileage normalization, make canonicalization, null for
absent fields); one-sided for consistency judgments, where the prompt tells
the model to give the benefit of the doubt — assert `is not False` for valid
pairings and pin `is False` only on clear contradictions. Never assert on
free-text wording.
"""

import asyncio

import pytest

from app.extraction import check_vin_consistency, extract_claim
from tests.fixtures import SAMPLE_EXTRACTION, SAMPLE_RO_TEXT

pytestmark = [pytest.mark.llm, pytest.mark.usefixtures("live_llm")]


@pytest.fixture(scope="module")
def run():
    """One event loop for the whole module: the agents' shared HTTP client
    binds to the loop it first runs on, so per-test asyncio.run() would break."""
    loop = asyncio.new_event_loop()
    yield loop.run_until_complete
    loop.close()


# A non-canonical make ("Chevy"), comma-and-units mileage, and no part number.
CHEVY_RO_TEXT = (
    "RO# 551203 | 2022 Chevy Bolt EV | VIN 1G1FY6S0XN0000123\n"
    "Odometer: 12,340 mi\n"
    "Repair: Replaced charge port door actuator.\n"
    "Labor: 1.5 hrs"
)

# Almost everything absent — the model must return nulls, not guesses.
MINIMAL_RO_TEXT = "VIN: 1G1FY6S0XN0000123. Replaced 12V battery."

# The model is named ("Murano") but the make never is — the prompt requires
# inferring the make from an unambiguous model name (not from the VIN).
MURANO_RO_TEXT = (
    "RO# 662104 | 2021 Murano Platinum | VIN JN8AZ2BJ4MW123456\n"
    "Odometer: 41,872 mi\n"
    "Repair: Replaced CVT valve body.\n"
    "Labor: 3.8 hrs"
)


class TestExtraction:
    def test_sample_ro_extracts_exact_fields(self, run):
        result = run(extract_claim(SAMPLE_RO_TEXT))
        assert result.vin == SAMPLE_EXTRACTION["vin"]
        assert result.year == SAMPLE_EXTRACTION["year"]
        assert result.make == SAMPLE_EXTRACTION["make"]
        assert result.mileage == SAMPLE_EXTRACTION["mileage"]
        assert result.part_number == SAMPLE_EXTRACTION["part_number"]
        assert result.labor_hours == SAMPLE_EXTRACTION["labor_hours"]
        assert result.model is not None and "bolt" in result.model.lower()
        assert result.repair_description is not None
        assert "battery" in result.repair_description.lower()

    def test_make_canonicalized_and_mileage_normalized(self, run):
        result = run(extract_claim(CHEVY_RO_TEXT))
        assert result.make == "Chevrolet"  # not "Chevy" — the prompt's contract
        assert result.mileage == 12340  # commas and units stripped
        assert result.labor_hours == 1.5
        assert result.part_number is None

    def test_unstated_make_inferred_from_model(self, run):
        result = run(extract_claim(MURANO_RO_TEXT))
        assert result.model is not None and "murano" in result.model.lower()
        assert result.make == "Nissan"
        assert result.year == 2021
        assert result.mileage == 41872

    def test_absent_fields_come_back_null(self, run):
        result = run(extract_claim(MINIMAL_RO_TEXT))
        assert result.vin == "1G1FY6S0XN0000123"
        # No model named either, so the make must stay null — a '1G1' WMI is
        # Chevrolet, and filling that in would violate the never-infer-from-VIN
        # rule.
        assert result.make is None
        assert result.mileage is None
        assert result.labor_hours is None
        assert result.part_number is None
        assert result.repair_description is not None


class TestVinConsistency:
    def test_matching_claim_not_contradicted(self, run):
        verdict = run(
            check_vin_consistency(
                vin="1G1FY6S0XN0000123",
                decoded_year=2022,
                decoded_make="Chevrolet",
                claimed_year=2022,
                claimed_make="Chevrolet",
                claimed_model="Bolt EV",
            )
        )
        # Decoded make supplied → the prompt asks for make_consistent = null,
        # but a harmless True is tolerated; only False would be a bug.
        assert verdict.make_consistent is not False
        assert verdict.model_consistent is not False

    def test_matching_make_judged_from_wmi(self, run):
        # No locally decoded make — the LLM judges the WMI itself (1HG = Honda).
        verdict = run(
            check_vin_consistency(
                vin="1HGCM82633A004352",
                decoded_year=2003,
                decoded_make=None,
                claimed_year=2003,
                claimed_make="Honda",
                claimed_model="Accord",
            )
        )
        assert verdict.make_consistent is not False
        assert verdict.model_consistent is not False

    def test_clear_make_mismatch_flagged(self, run):
        # A Honda Accord VIN claimed as a Ford F-150 — the one case where the
        # benefit-of-the-doubt prompt must still come back False.
        verdict = run(
            check_vin_consistency(
                vin="1HGCM82633A004352",
                decoded_year=2003,
                decoded_make=None,
                claimed_year=2003,
                claimed_make="Ford",
                claimed_model="F-150",
            )
        )
        assert verdict.make_consistent is False
        assert verdict.issues  # a false verdict must carry evidence
