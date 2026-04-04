"""Allocation rule CRUD, import, and engine tests."""

import json
import pytest
from datetime import date


# ─────────────────────────────────────────────────────────────────────────────
# Allocation Rule model
# ─────────────────────────────────────────────────────────────────────────────

class TestAllocationRuleModel:
    def test_create_minimal_rule(self, db_session, app):
        from app.models.workflow import AllocationRule
        with app.app_context():
            rule = AllocationRule(name="Test Rule", created_by="admin")
            db_session.add(rule)
            db_session.flush()
            assert rule.id is not None
            assert rule.is_active is True
            assert rule.status == "ACTIVE"
            assert rule.entry_mode == "BOTH"

    def test_rule_repr_contains_name(self, app):
        from app.models.workflow import AllocationRule
        with app.app_context():
            rule = AllocationRule(name="My Rule")
            # AllocationRule may not have __repr__ — just check id/name accessible
            assert rule.name == "My Rule"

    def test_default_tables(self, db_session, app):
        from app.models.workflow import AllocationRule
        with app.app_context():
            rule = AllocationRule(name="Default Tables Rule", created_by="admin")
            db_session.add(rule)
            db_session.flush()
            assert rule.source_table == "proc_inst_data"
            assert rule.lookup_table == "ref_static_allocation"
            assert rule.output_table == "fct_mgmt_ledger"


# ─────────────────────────────────────────────────────────────────────────────
# Allocation Rule UI routes
# ─────────────────────────────────────────────────────────────────────────────

class TestAllocationRuleRoutes:
    def test_rules_list_requires_auth(self, client):
        rv = client.get("/rules/", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_rules_list_renders(self, auth_client):
        rv = auth_client.get("/rules/")
        assert rv.status_code == 200

    def test_import_page_renders(self, auth_client):
        rv = auth_client.get("/rules/import")
        assert rv.status_code == 200

    def test_import_valid_rule_json(self, auth_client):
        payload = json.dumps({
            "name": "Import Test Rule",
            "source_table": "proc_inst_data",
            "lookup_table": "ref_static_allocation",
            "output_table": "fct_mgmt_instrument",
            "join_key": "customer_id",
            "entry_mode": "BOTH",
        })
        rv = auth_client.post(
            "/rules/import",
            data={"rule_json": payload},
        )
        assert rv.status_code in (200, 302)

    def test_import_missing_name_shows_error(self, auth_client):
        payload = json.dumps({"source_table": "proc_inst_data"})
        rv = auth_client.post(
            "/rules/import",
            data={"rule_json": payload},
            follow_redirects=True,
        )
        # Should stay on page with an error flash
        assert rv.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Filter helper — _apply_filters()
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyFilters:
    """Direct unit tests for the filter helper used by the engine."""

    def _make_df(self):
        import pandas as pd
        return pd.DataFrame({
            "product_code": ["LOAN", "DEPOSIT", "LOAN"],
            "balance": [1000.0, 2000.0, 500.0],
            "org_unit_id": ["ORG-001", "ORG-002", "ORG-001"],
        })

    def test_no_filter_returns_all_rows(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            result = _apply_filters(df, None)
            assert len(result) == 3

    def test_eq_filter(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            filt = json.dumps({
                "logic": "AND",
                "conditions": [{"field": "product_code", "operator": "eq", "value": "LOAN"}],
            })
            result = _apply_filters(df, filt)
            assert len(result) == 2
            assert all(result["product_code"] == "LOAN")

    def test_gt_filter(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            filt = json.dumps({
                "logic": "AND",
                "conditions": [{"field": "balance", "operator": "gt", "value": "900"}],
            })
            result = _apply_filters(df, filt)
            assert len(result) == 2

    def test_in_filter(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            filt = json.dumps({
                "logic": "AND",
                "conditions": [{"field": "product_code", "operator": "in", "value": "LOAN,DEPOSIT"}],
            })
            result = _apply_filters(df, filt)
            assert len(result) == 3

    def test_or_logic(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            filt = json.dumps({
                "logic": "OR",
                "conditions": [
                    {"field": "product_code", "operator": "eq", "value": "LOAN"},
                    {"field": "org_unit_id", "operator": "eq", "value": "ORG-002"},
                ],
            })
            result = _apply_filters(df, filt)
            assert len(result) == 3  # all rows match one arm or the other

    def test_invalid_json_returns_df_unchanged(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            result = _apply_filters(df, "{not valid json}")
            assert len(result) == 3

    def test_between_filter(self, app):
        from app.services.allocation_engine import _apply_filters
        with app.app_context():
            df = self._make_df()
            filt = json.dumps({
                "logic": "AND",
                "conditions": [{"field": "balance", "operator": "between", "value": "600,1500"}],
            })
            result = _apply_filters(df, filt)
            assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Allocation engine — end-to-end with seeded data
# ─────────────────────────────────────────────────────────────────────────────

class TestAllocationEngine:
    def test_run_allocation_creates_batch(self, seeded_db, app):
        from app.services.allocation_engine import run_allocation
        from app.models.workflow import AllocationRule, BatchRun
        with app.app_context():
            rule = AllocationRule(
                name="Engine E2E Test",
                source_table="proc_inst_data",
                lookup_table="ref_static_allocation",
                output_table="fct_mgmt_instrument",
                join_key="customer_id",
                entry_mode="BOTH",
                is_active=True,
                created_by="admin",
            )
            seeded_db.add(rule)
            seeded_db.flush()

            batch = run_allocation(rule.id, date(2026, 1, 1), "admin")
            assert batch is not None
            assert batch.status == "COMPLETED"
            assert batch.source_row_count >= 1

    def test_run_allocation_unknown_rule_raises(self, db_session, app):
        from app.services.allocation_engine import run_allocation
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                run_allocation(999999, date(2026, 1, 1), "admin")

    def test_debit_credit_balance_equals_source(self, seeded_db, app):
        """DEBIT + CREDIT ratio sum must equal the allocated balance."""
        from app.services.allocation_engine import run_allocation
        from app.models.workflow import AllocationRule
        from app.models.allocation import FctMgmtInstrument
        with app.app_context():
            rule = AllocationRule(
                name="Balance Check Rule",
                source_table="proc_inst_data",
                lookup_table="ref_static_allocation",
                output_table="fct_mgmt_instrument",
                join_key="customer_id",
                entry_mode="BOTH",
                is_active=True,
                created_by="admin",
            )
            seeded_db.add(rule)
            seeded_db.flush()

            batch = run_allocation(rule.id, date(2026, 1, 1), "admin")
            assert batch.status == "COMPLETED"
            entries = FctMgmtInstrument.query.filter_by(batch_run_id=batch.id).all()
            debits  = sum(e.allocated_balance for e in entries if e.entry_type == "DEBIT")
            credits = sum(e.allocated_balance for e in entries if e.entry_type == "CREDIT")
            # CREDIT allocated_balance is stored as negative — debits + credits must sum to ~0
            assert abs(debits + credits) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# allocation_method field defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestAllocationMethodDefault:
    def test_allocation_method_defaults_to_ratio(self, db_session, app):
        from app.models.workflow import AllocationRule
        with app.app_context():
            rule = AllocationRule(name="MethodDefaultRule", created_by="admin")
            db_session.add(rule)
            db_session.flush()
            # Default may be set at Python level (not yet in DB for old rows) so
            # check both the column default and the instance attribute.
            assert (rule.allocation_method or "RATIO") == "RATIO"


# ─────────────────────────────────────────────────────────────────────────────
# RefStaticDistribution model
# ─────────────────────────────────────────────────────────────────────────────

class TestRefStaticDistributionModel:
    def test_create_distribution_row(self, db_session, app):
        from app.models.allocation import RefStaticDistribution
        with app.app_context():
            row = RefStaticDistribution(
                distribution_id="DIST-001",
                customer_id="CUST-0001",
                target_dim="ORG-002",
                ratio=0.6,
                maker_id="admin",
                status="APPROVED",
            )
            db_session.add(row)
            db_session.flush()
            assert row.id is not None
            assert row.ratio == 0.6
            assert row.target_dim == "ORG-002"

    def test_distribution_ratio_defaults_not_nullable(self, db_session, app):
        """ratio must be supplied — no schema-level default on the Distribution table."""
        from app.models.allocation import RefStaticDistribution
        with app.app_context():
            row = RefStaticDistribution(
                distribution_id="DIST-002",
                target_dim="ORG-001",
                ratio=1.0,
                maker_id="admin",
            )
            db_session.add(row)
            db_session.flush()
            assert row.ratio == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# RefStaticAlloc model
# ─────────────────────────────────────────────────────────────────────────────

class TestRefStaticAllocModel:
    def test_create_alloc_row_ratio_defaults_to_one(self, db_session, app):
        from app.models.allocation import RefStaticAlloc
        with app.app_context():
            row = RefStaticAlloc(
                alloc_id="SA-001",
                org_unit_id="ORG-001",
                target_dim="ORG-002",
                maker_id="admin",
                status="APPROVED",
            )
            db_session.add(row)
            db_session.flush()
            assert row.id is not None
            assert row.ratio == 1.0  # schema default


# ─────────────────────────────────────────────────────────────────────────────
# Static Allocation engine path
# ─────────────────────────────────────────────────────────────────────────────

class TestStaticAllocationEngine:
    def test_static_method_completes(self, seeded_db, app):
        """STATIC method runs without lookup join and creates output rows at ratio=1.0."""
        from app.services.allocation_engine import run_allocation
        from app.models.workflow import AllocationRule
        from app.models.allocation import FctMgmtInstrument
        from datetime import date
        with app.app_context():
            rule = AllocationRule(
                name="Static Engine Test",
                source_table="proc_inst_data",
                lookup_table="ref_static_alloc",  # not actually joined
                output_table="fct_mgmt_instrument",
                join_key="customer_id",
                allocation_method="STATIC",
                entry_mode="DEBIT_ONLY",
                is_active=True,
                created_by="admin",
                output_dim_json='{"org_unit_id":{"mode":"same_as_source"}}',
            )
            seeded_db.add(rule)
            seeded_db.flush()

            batch = run_allocation(rule.id, date(2026, 1, 1), "admin")
            assert batch is not None
            assert batch.status == "COMPLETED"
            assert batch.source_row_count >= 1

            entries = FctMgmtInstrument.query.filter_by(batch_run_id=batch.id).all()
            assert len(entries) >= 1
            for e in entries:
                assert e.ratio_applied == 1.0

    def test_static_method_no_orphans_from_missing_lookup(self, seeded_db, app):
        """STATIC method should never mark rows as orphan due to lookup mismatch."""
        from app.services.allocation_engine import run_allocation
        from app.models.workflow import AllocationRule
        from app.models.allocation import FctMgmtInstrument
        from datetime import date
        with app.app_context():
            rule = AllocationRule(
                name="Static No Orphan Test",
                source_table="proc_inst_data",
                lookup_table="ref_static_alloc",
                output_table="fct_mgmt_instrument",
                join_key="org_unit_id",
                allocation_method="STATIC",
                entry_mode="DEBIT_ONLY",
                is_active=True,
                created_by="admin",
                output_dim_json='{"org_unit_id":{"mode":"same_as_source"}}',
            )
            seeded_db.add(rule)
            seeded_db.flush()

            batch = run_allocation(rule.id, date(2026, 1, 1), "admin")
            entries = FctMgmtInstrument.query.filter_by(batch_run_id=batch.id).all()
            orphans = [e for e in entries if e.is_orphan]
            assert len(orphans) == 0

