import pytest

import app.main
from app.extraction import agent
from app.warranty_coverage import check_warranty_coverage
from tests.conftest import extraction_model
from tests.fixtures import SAMPLE_EXTRACTION, SAMPLE_RO_TEXT, VALID_EXTRACTION


def post_claim(client, ro_text=SAMPLE_RO_TEXT):
    return client.post("/analyze-claim", json={"ro_text": ro_text})


class TestHappyPath:
    def test_valid_claim_returns_200(self, client):
        with agent.override(model=extraction_model(VALID_EXTRACTION)):
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
        with agent.override(model=extraction_model({**VALID_EXTRACTION, "part_number": None})):
            response = post_claim(client)
        assert response.status_code == 200
        assert response.json()["part_number"] is None


class TestValidationErrors:
    def test_sample_ro_fails_vin_check_digit(self, client):
        with agent.override(model=extraction_model(SAMPLE_EXTRACTION)):
            response = post_claim(client)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "validation failed" in detail["summary"]
        vin_errors = [e for e in detail["errors"] if e["field"] == "vin"]
        assert len(vin_errors) == 1
        assert "check digit" in vin_errors[0]["message"]

    def test_missing_required_field(self, client):
        with agent.override(model=extraction_model({**VALID_EXTRACTION, "mileage": None})):
            response = post_claim(client)
        assert response.status_code == 422
        assert any(e["field"] == "mileage" for e in response.json()["detail"]["errors"])

    def test_multiple_failures_reported_together(self, client):
        bad = {**SAMPLE_EXTRACTION, "labor_hours": -1.0}
        with agent.override(model=extraction_model(bad)):
            response = post_claim(client)
        assert response.status_code == 422
        fields = {e["field"] for e in response.json()["detail"]["errors"]}
        assert {"vin", "labor_hours"} <= fields

    def test_coverage_value_error_becomes_422(self, client, monkeypatch):
        def raises(*args, **kwargs):
            raise ValueError("Unknown make/model: Fnord Zed")

        monkeypatch.setattr(app.main, "check_warranty_coverage", raises)
        with agent.override(model=extraction_model(VALID_EXTRACTION)):
            response = post_claim(client)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "Unknown make/model: Fnord Zed" in detail["summary"]
        assert detail["errors"][0]["field"] == "coverage"

    def test_malformed_request_body(self, client):
        response = client.post("/analyze-claim", json={})
        assert response.status_code == 422  # FastAPI's own shape for transport errors


def test_no_real_model_requests_possible(client):
    with pytest.raises(RuntimeError):
        post_claim(client)
