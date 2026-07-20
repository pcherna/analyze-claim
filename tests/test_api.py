import pytest

import app.main
from app.warranty_coverage import check_warranty_coverage
from tests.conftest import override_agents, unreachable_model
from tests.fixtures import SAMPLE_EXTRACTION, SAMPLE_RO_TEXT, VALID_EXTRACTION


def post_claim(client, ro_text=SAMPLE_RO_TEXT):
    return client.post("/analyze-claim", json={"ro_text": ro_text})


class TestHappyPath:
    def test_valid_claim_returns_200(self, client):
        with override_agents(VALID_EXTRACTION):
            response = post_claim(client)
        assert response.status_code == 200
        body = response.json()
        for field, value in VALID_EXTRACTION.items():
            assert body[field] == value
        # Coverage asserted against the stub so tests don't rot as years pass.
        expected = check_warranty_coverage(
            vin=VALID_EXTRACTION["vin"],
            make=VALID_EXTRACTION["make"],
            model=VALID_EXTRACTION["model"],
            year=VALID_EXTRACTION["year"],
            mileage=VALID_EXTRACTION["mileage"],
            part_number=VALID_EXTRACTION["part_number"],
        )
        assert body["coverage_eligible"] == expected["eligible"]
        assert body["coverage_reason"] == expected["reason"]
        assert "warranty_type" not in body

    def test_part_number_optional(self, client):
        with override_agents({**VALID_EXTRACTION, "part_number": None}):
            response = post_claim(client)
        assert response.status_code == 200
        assert response.json()["part_number"] is None

    def test_unsure_verdict_gives_benefit_of_doubt(self, client):
        with override_agents(VALID_EXTRACTION, {"make_consistent": None, "model_consistent": None, "issues": []}):
            response = post_claim(client)
        assert response.status_code == 200


class TestValidationErrors:
    def test_sample_ro_fails_vin_check_digit(self, client):
        with override_agents(SAMPLE_EXTRACTION):
            response = post_claim(client)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "validation failed" in detail["summary"]
        vin_errors = [e for e in detail["errors"] if e["field"] == "vin"]
        assert len(vin_errors) == 1
        assert "check digit" in vin_errors[0]["message"]

    def test_missing_required_field(self, client):
        with override_agents({**VALID_EXTRACTION, "mileage": None}):
            response = post_claim(client)
        assert response.status_code == 422
        assert any(e["field"] == "mileage" for e in response.json()["detail"]["errors"])

    def test_multiple_failures_reported_together(self, client):
        bad = {**SAMPLE_EXTRACTION, "labor_hours": -1.0}
        with override_agents(bad):
            response = post_claim(client)
        assert response.status_code == 422
        fields = {e["field"] for e in response.json()["detail"]["errors"]}
        assert {"vin", "labor_hours"} <= fields

    def test_coverage_value_error_becomes_422(self, client, monkeypatch):
        def raises(*args, **kwargs):
            raise ValueError("Unknown make/model: Fnord Zed")

        monkeypatch.setattr(app.main, "check_warranty_coverage", raises)
        with override_agents(VALID_EXTRACTION):
            response = post_claim(client)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "Unknown make/model: Fnord Zed" in detail["summary"]
        assert detail["errors"][0]["field"] == "coverage"

    def test_malformed_request_body(self, client):
        response = client.post("/analyze-claim", json={})
        assert response.status_code == 422  # FastAPI's own shape for transport errors


class TestVinCrossValidation:
    def test_year_mismatch(self, client):
        with override_agents({**VALID_EXTRACTION, "year": 2021}):
            response = post_claim(client)
        assert response.status_code == 422
        errors = response.json()["detail"]["errors"]
        year_errors = [e for e in errors if e["field"] == "year"]
        assert len(year_errors) == 1
        assert "VIN" in year_errors[0]["message"]

    def test_make_mismatch_deterministic(self, client):
        # Verdict stays consistent — proves the local WMI check alone fires.
        with override_agents({**VALID_EXTRACTION, "make": "Ford"}):
            response = post_claim(client)
        assert response.status_code == 422
        make_errors = [e for e in response.json()["detail"]["errors"] if e["field"] == "make"]
        assert len(make_errors) == 1
        assert "1G1" in make_errors[0]["message"]
        assert "Chevrolet" in make_errors[0]["message"]

    def test_model_mismatch_from_llm_verdict(self, client):
        verdict = {"make_consistent": True, "model_consistent": False, "issues": ["VDS indicates Bolt EUV"]}
        with override_agents({**VALID_EXTRACTION, "model": "Camaro"}, verdict):
            response = post_claim(client)
        assert response.status_code == 422
        model_errors = [e for e in response.json()["detail"]["errors"] if e["field"] == "model"]
        assert len(model_errors) == 1
        assert "Bolt EUV" in model_errors[0]["message"]

    def test_llm_make_verdict_ignored_when_locally_decided(self, client):
        # WMI 1G1 decided make locally and it matches; a False LLM make verdict
        # must not override the deterministic result.
        verdict = {"make_consistent": False, "model_consistent": True, "issues": ["spurious"]}
        with override_agents(VALID_EXTRACTION, verdict):
            response = post_claim(client)
        assert response.status_code == 200

    def test_unknown_wmi_make_judged_by_llm(self, client):
        # Volkswagen WMI is not in the local table -> LLM verdict decides make.
        from app.validators import compute_vin_check_digit

        base = "WVWAA7AJ0BW000001"
        vin = base[:8] + compute_vin_check_digit(base) + base[9:]
        extraction = {**VALID_EXTRACTION, "vin": vin, "make": "Volkswagen", "model": "Golf", "year": 2011}
        verdict = {"make_consistent": False, "model_consistent": True, "issues": ["WMI is not Volkswagen"]}
        with override_agents(extraction, verdict):
            response = post_claim(client)
        assert response.status_code == 422
        make_errors = [e for e in response.json()["detail"]["errors"] if e["field"] == "make"]
        assert len(make_errors) == 1

    def test_consistency_agent_skipped_when_vin_invalid(self, client):
        with override_agents(
            SAMPLE_EXTRACTION, unreachable_model("consistency agent must not be called for an invalid VIN")
        ):
            response = post_claim(client)
        assert response.status_code == 422
        fields = {e["field"] for e in response.json()["detail"]["errors"]}
        assert fields == {"vin"}

    def test_field_and_vin_issues_reported_together(self, client):
        with override_agents({**VALID_EXTRACTION, "labor_hours": -1.0, "year": 2021}):
            response = post_claim(client)
        assert response.status_code == 422
        fields = {e["field"] for e in response.json()["detail"]["errors"]}
        assert {"labor_hours", "year"} <= fields


def test_no_real_model_requests_possible(client):
    with pytest.raises(RuntimeError):
        post_claim(client)
