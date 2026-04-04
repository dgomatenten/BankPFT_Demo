"""REST API integration tests — /api/v1/*

All API calls require HTTP Basic Auth.  Tests verify:
- 401 returned when credentials are missing or wrong
- 200/201 for happy-path calls
- 400/422 for invalid input
- Correct JSON shape in responses
"""

import json
import base64
import pytest
from datetime import date


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _basic(username="admin", password="admin"):
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────────────────────
# Authentication guard — every endpoint should return 401 without credentials
# ─────────────────────────────────────────────────────────────────────────────

class TestApiAuth:
    ENDPOINTS = [
        ("GET",  "/api/v1/batch/rules"),
        ("GET",  "/api/v1/datafile/formats"),
        ("GET",  "/api/v1/datafile/exports"),
        ("GET",  "/api/v1/ftp/configs"),
        ("GET",  "/api/v1/batch/definitions"),
        ("POST", "/api/v1/batch/allocation"),
        ("POST", "/api/v1/batch/ftp"),
        ("POST", "/api/v1/rules/import"),
        ("POST", "/api/v1/ftp/config/import"),
    ]

    @pytest.mark.parametrize("method,url", ENDPOINTS)
    def test_unauthenticated_returns_401(self, client, method, url):
        fn = getattr(client, method.lower())
        rv = fn(url, content_type="application/json")
        assert rv.status_code == 401

    def test_wrong_password_returns_401(self, client):
        rv = client.get("/api/v1/batch/rules", headers=_basic("admin", "wrongpassword"))
        assert rv.status_code == 401

    def test_unknown_user_returns_401(self, client):
        rv = client.get("/api/v1/batch/rules", headers=_basic("nobody", "any"))
        assert rv.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# GET endpoints — list / info
# ─────────────────────────────────────────────────────────────────────────────

class TestApiGetEndpoints:
    def test_list_rules_returns_list(self, client):
        rv = client.get("/api/v1/batch/rules", headers=_basic())
        assert rv.status_code == 200
        data = rv.get_json()
        assert "rules" in data
        assert isinstance(data["rules"], list)

    def test_list_formats_returns_list(self, client):
        rv = client.get("/api/v1/datafile/formats", headers=_basic())
        assert rv.status_code == 200
        data = rv.get_json()
        assert "formats" in data
        assert isinstance(data["formats"], list)
        if data["formats"]:
            assert "format_id" in data["formats"][0]

    def test_list_exports_returns_list(self, client):
        rv = client.get("/api/v1/datafile/exports", headers=_basic())
        assert rv.status_code == 200
        data = rv.get_json()
        assert "exports" in data

    def test_list_ftp_configs(self, client):
        rv = client.get("/api/v1/ftp/configs", headers=_basic())
        assert rv.status_code == 200
        data = rv.get_json()
        assert "configs" in data
        assert isinstance(data["configs"], list)

    def test_list_batch_definitions(self, client):
        rv = client.get("/api/v1/batch/definitions", headers=_basic())
        assert rv.status_code == 200
        data = rv.get_json()
        assert "definitions" in data

    def test_batch_allocation_status_not_found(self, client):
        rv = client.get("/api/v1/batch/allocation/nonexistent-id", headers=_basic())
        assert rv.status_code == 404

    def test_batch_ftp_status_not_found(self, client):
        rv = client.get("/api/v1/batch/ftp/nonexistent-id", headers=_basic())
        assert rv.status_code == 404

    def test_datafile_batch_not_found(self, client):
        rv = client.get("/api/v1/datafile/batch/nonexistent-id", headers=_basic())
        assert rv.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rules/import
# ─────────────────────────────────────────────────────────────────────────────

class TestApiRuleImport:
    VALID_RULE = {
        "name": "API Import Rule",
        "source_table": "proc_inst_data",
        "lookup_table": "ref_static_allocation",
        "output_table": "fct_mgmt_instrument",
        "join_key": "customer_id",
        "entry_mode": "BOTH",
    }

    def test_import_valid_rule_returns_201(self, client):
        rv = client.post(
            "/api/v1/rules/import",
            headers=_basic(),
            data=json.dumps(self.VALID_RULE),
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert "rule_id" in data
        assert data["name"] == "API Import Rule"

    def test_import_missing_name_returns_400(self, client):
        body = {k: v for k, v in self.VALID_RULE.items() if k != "name"}
        rv = client.post(
            "/api/v1/rules/import",
            headers=_basic(),
            data=json.dumps(body),
        )
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_import_empty_body_returns_400(self, client):
        rv = client.post(
            "/api/v1/rules/import",
            headers=_basic(),
            data="",
        )
        assert rv.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/ftp/config/import
# ─────────────────────────────────────────────────────────────────────────────

class TestApiFtpConfigImport:
    VALID_CONFIG = {
        "product_code": "API-FTP-TEST",
        "rate_code": "SWAP_RATE",
        "term": 5,
        "term_mult": "Y",
        "avg_period": 1,
        "avg_period_mult": "M",
    }

    def test_import_single_config(self, client):
        rv = client.post(
            "/api/v1/ftp/config/import",
            headers=_basic(),
            data=json.dumps(self.VALID_CONFIG),
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data.get("imported", 0) + data.get("updated", 0) >= 1

    def test_import_array_of_configs(self, client):
        configs = [
            {**self.VALID_CONFIG, "product_code": "API-FTP-ARR1"},
            {**self.VALID_CONFIG, "product_code": "API-FTP-ARR2"},
        ]
        rv = client.post(
            "/api/v1/ftp/config/import",
            headers=_basic(),
            data=json.dumps(configs),
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data.get("imported", 0) + data.get("updated", 0) >= 1

    def test_import_updates_existing_config(self, client):
        # First insert
        client.post(
            "/api/v1/ftp/config/import",
            headers=_basic(),
            data=json.dumps({**self.VALID_CONFIG, "product_code": "API-FTP-UPD"}),
        )
        # Second call — should be an update
        rv = client.post(
            "/api/v1/ftp/config/import",
            headers=_basic(),
            data=json.dumps({**self.VALID_CONFIG, "product_code": "API-FTP-UPD", "term": 3}),
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data.get("updated", 0) >= 1

    def test_import_missing_product_code_returns_422(self, client):
        bad = {k: v for k, v in self.VALID_CONFIG.items() if k != "product_code"}
        rv = client.post(
            "/api/v1/ftp/config/import",
            headers=_basic(),
            data=json.dumps(bad),
        )
        assert rv.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/datafile/import — validation only (no actual file needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestApiDatafileImport:
    def test_missing_format_id_returns_400(self, client):
        rv = client.post(
            "/api/v1/datafile/import",
            headers=_basic(),
            data=json.dumps({"filename": "test.dat"}),
        )
        assert rv.status_code == 400

    def test_path_traversal_filename_rejected(self, client):
        rv = client.post(
            "/api/v1/datafile/import",
            headers=_basic(),
            data=json.dumps({"format_id": "LOAN_FIXED", "filename": "../etc/passwd"}),
        )
        assert rv.status_code == 400

    def test_missing_filename_returns_400(self, client):
        rv = client.post(
            "/api/v1/datafile/import",
            headers=_basic(),
            data=json.dumps({"format_id": "LOAN_FIXED"}),
        )
        assert rv.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/batch/allocation — validation (no actual data seeded here)
# ─────────────────────────────────────────────────────────────────────────────

class TestApiRunAllocation:
    def test_missing_rule_id_returns_400(self, client):
        rv = client.post(
            "/api/v1/batch/allocation",
            headers=_basic(),
            data=json.dumps({"as_of_date": "2026-01-01"}),
        )
        assert rv.status_code == 400

    def test_invalid_rule_id_returns_404_or_400(self, client):
        rv = client.post(
            "/api/v1/batch/allocation",
            headers=_basic(),
            data=json.dumps({"rule_id": 999999, "as_of_date": "2026-01-01"}),
        )
        assert rv.status_code in (400, 404, 422)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/batch/ftp — validation
# ─────────────────────────────────────────────────────────────────────────────

class TestApiRunFtp:
    def test_run_ftp_with_valid_date(self, client):
        rv = client.post(
            "/api/v1/batch/ftp",
            headers=_basic(),
            data=json.dumps({"as_of_date": "2026-01-01"}),
        )
        # Should complete (0 instruments if empty db) — 200 or 422
        assert rv.status_code in (200, 422)
        data = rv.get_json()
        assert "run_id" in data or "error" in data

    def test_run_ftp_without_date_uses_today(self, client):
        rv = client.post(
            "/api/v1/batch/ftp",
            headers=_basic(),
            data=json.dumps({}),
        )
        # Should not crash
        assert rv.status_code in (200, 422)
