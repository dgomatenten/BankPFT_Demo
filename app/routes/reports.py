from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db
from app.models.dimensions import DimOrgUnit, DimProduct, DimCustomer, DimAccount
from app.models.staging import StgInstData, ProcInstData, StgGlData, ProcGlData
from app.models.allocation import (
    RefStaticAllocation, FctMgmtLedger, FctMgmtInstrument,
    RefOrgReclass, RefStaticDistribution, RefStaticAlloc,
)
from app.models.workflow import UploadBatch, AllocationRule, BatchRun
from app.models.ftp import RefInterestRate, FtpProductConfig, FtpRun
from sqlalchemy import func, inspect as sa_inspect, and_, literal, text
import os
from app.core.batch_logger import BATCH_LOG_DIR

bp = Blueprint("reports", __name__)


@bp.before_request
@login_required
def require_login():
    pass

ALL_MODELS = {
    "dim_org_unit": DimOrgUnit,
    "dim_product": DimProduct,
    "dim_customer": DimCustomer,
    "dim_account": DimAccount,
    "stg_inst_data": StgInstData,
    "proc_inst_data": ProcInstData,
    "stg_gl_data": StgGlData,
    "proc_gl_data": ProcGlData,
    "ref_static_allocation": RefStaticAllocation,
    "ref_org_reclass": RefOrgReclass,
    "ref_static_distribution": RefStaticDistribution,
    "ref_static_alloc": RefStaticAlloc,
    "fct_mgmt_ledger": FctMgmtLedger,
    "fct_mgmt_instrument": FctMgmtInstrument,
    "upload_batch": UploadBatch,
    "allocation_rule": AllocationRule,
    "batch_run": BatchRun,
    "ref_interest_rate": RefInterestRate,
    "ftp_product_config": FtpProductConfig,
    "ftp_run": FtpRun,
}

VALID_GROUP_BY = {"target_org_unit_id", "source_org_unit_id", "product_code", "customer_id", "entry_type"}


@bp.route("/")
def index():
    return render_template("reports/index.html")


@bp.route("/tables")
def tables():
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("reports.index"))
    table_stats = []
    for name, model in ALL_MODELS.items():
        count = model.query.count()
        table_stats.append({"name": name, "count": count})
    selected = request.args.get("table")
    columns = []
    rows = []
    if selected and selected in ALL_MODELS:
        model = ALL_MODELS[selected]
        mapper = sa_inspect(model)
        columns = [col.key for col in mapper.column_attrs]
        pk_cols = _get_pk_columns(model)
        page = request.args.get("page", 1, type=int)
        per_page = 50
        query = model.query.limit(per_page).offset((page - 1) * per_page).all()
        rows = []
        for obj in query:
            row = {col: getattr(obj, col) for col in columns}
            row["_pk"] = _build_pk_value(row, pk_cols)
            rows.append(row)
        total = model.query.count()
    else:
        pk_cols = []
        page = 1
        per_page = 50
        total = 0
    return render_template(
        "reports/tables.html",
        table_stats=table_stats,
        selected=selected,
        columns=columns,
        pk_cols=pk_cols,
        rows=rows,
        page=page,
        per_page=per_page,
        total=total,
    )


def _get_pk_columns(model):
    """Return list of primary key column names for a model."""
    mapper = sa_inspect(model)
    return [col.name for col in mapper.primary_key]


def _get_row_by_pk(model, pk_value):
    """Look up a single row by its primary key (supports composite keys via '|' separator)."""
    pk_cols = _get_pk_columns(model)
    if len(pk_cols) == 1:
        return db.session.get(model, pk_value)
    else:
        pk_parts = str(pk_value).split("|")
        return db.session.get(model, tuple(pk_parts))


def _build_pk_value(row, pk_cols):
    """Build a PK string for a row dict (pipe-separated for composite keys)."""
    if len(pk_cols) == 1:
        return str(row[pk_cols[0]])
    return "|".join(str(row[c]) for c in pk_cols)


@bp.route("/tables/<table_name>/edit/<path:pk_value>", methods=["GET", "POST"])
@login_required
def table_edit(table_name, pk_value):
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("reports.tables"))
    if table_name not in ALL_MODELS:
        flash("Unknown table.", "danger")
        return redirect(url_for("reports.tables"))

    model = ALL_MODELS[table_name]
    obj = _get_row_by_pk(model, pk_value)
    if obj is None:
        flash("Row not found.", "danger")
        return redirect(url_for("reports.tables", table=table_name))

    mapper = sa_inspect(model)
    columns = [col.key for col in mapper.column_attrs]
    pk_cols = _get_pk_columns(model)

    if request.method == "POST":
        for col in columns:
            if col in pk_cols:
                continue  # don't allow PK edits
            raw = request.form.get(col, "")
            col_obj = getattr(model, col).property.columns[0]
            if raw == "" or raw == "None":
                if col_obj.nullable:
                    setattr(obj, col, None)
            else:
                col_type = str(col_obj.type)
                try:
                    if "INTEGER" in col_type:
                        setattr(obj, col, int(raw))
                    elif "FLOAT" in col_type:
                        setattr(obj, col, float(raw))
                    elif "BOOLEAN" in col_type:
                        setattr(obj, col, raw.lower() in ("true", "1", "yes"))
                    else:
                        setattr(obj, col, raw)
                except (ValueError, TypeError):
                    setattr(obj, col, raw)
        db.session.commit()
        flash(f"Row updated in {table_name}.", "success")
        return redirect(url_for("reports.tables", table=table_name))

    row_data = {col: getattr(obj, col) for col in columns}
    return render_template(
        "reports/table_edit.html",
        table_name=table_name,
        columns=columns,
        pk_cols=pk_cols,
        row=row_data,
        pk_value=pk_value,
    )


@bp.route("/tables/<table_name>/delete/<path:pk_value>", methods=["POST"])
@login_required
def table_delete(table_name, pk_value):
    if not current_user.is_admin:
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("reports.tables"))
    if table_name not in ALL_MODELS:
        flash("Unknown table.", "danger")
        return redirect(url_for("reports.tables"))

    model = ALL_MODELS[table_name]
    obj = _get_row_by_pk(model, pk_value)
    if obj is None:
        flash("Row not found.", "danger")
    else:
        db.session.delete(obj)
        db.session.commit()
        flash(f"Row deleted from {table_name}.", "success")

    return redirect(url_for("reports.tables", table=table_name))


@bp.route("/operations")
def operations():
    batches = BatchRun.query.order_by(BatchRun.started_at.desc()).all()
    return render_template("reports/operations.html", batches=batches)


@bp.route("/ledger")
def ledger():
    # Pivot: by target_org_unit_id, product_code, customer_id
    group_by = request.args.get("group_by", "target_org_unit_id")
    if group_by not in VALID_GROUP_BY:
        group_by = "target_org_unit_id"
    batch_id = request.args.get("batch_id", None)

    query = db.session.query(
        getattr(FctMgmtLedger, group_by),
        func.sum(FctMgmtLedger.allocated_balance).label("total_balance"),
        func.sum(FctMgmtLedger.allocated_income).label("total_income"),
        func.count(FctMgmtLedger.id).label("row_count"),
    )

    if batch_id:
        query = query.filter(FctMgmtLedger.batch_run_id == batch_id)

    results = query.group_by(getattr(FctMgmtLedger, group_by)).all()
    batches = BatchRun.query.filter_by(status="COMPLETED").order_by(BatchRun.started_at.desc()).all()

    return render_template(
        "reports/ledger.html",
        results=results,
        group_by=group_by,
        batch_id=batch_id,
        batches=batches,
    )


@bp.route("/execution-log/<batch_id>")
def execution_log(batch_id):
    batch = BatchRun.query.get_or_404(batch_id)
    records = FctMgmtLedger.query.filter_by(batch_run_id=batch_id).limit(500).all()
    
    log_content = None
    log_path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
    log_exists = os.path.exists(log_path)
    if log_exists:
        with open(log_path, encoding="utf-8") as _f:
            log_content = _f.read()
    else:
        log_content = f"DEBUG INFO:\nExpected Path: {log_path}\nExists: {log_exists}\nbatch_id: '{batch_id}'\nLength of ID: {len(batch_id)}"
            
    return render_template("reports/execution_log.html", batch=batch, records=records, log_content=log_content)


# ═════════════════════════════════════════════════════════════════════════
# Input → Output Traceability
# ═════════════════════════════════════════════════════════════════════════

_LOOKUP_MODELS = {
    "ref_static_allocation": RefStaticAllocation,
    "ref_org_reclass": RefOrgReclass,
    "ref_static_distribution": RefStaticDistribution,
    "ref_static_alloc": RefStaticAlloc,
}

_LOOKUP_ID_COL = {
    "ref_static_allocation": "allocation_id",
    "ref_org_reclass": "reclass_id",
    "ref_static_distribution": "distribution_id",
    "ref_static_alloc": "alloc_id",
}

_SOURCE_MODELS = {
    "proc_inst_data": ProcInstData,
    "proc_gl_data": ProcGlData,
}

_OUTPUT_MODELS = {
    "fct_mgmt_ledger":     FctMgmtLedger,
    "fct_mgmt_instrument": FctMgmtInstrument,
}


def _get_executed_sql(batch_id: str, rule, as_of_date):
    """Return (sql_source, sql_delete, sql_output) for the trace modals.

    Priority:
      1. sp_alloc_log — real SQL rendered by sp_run_allocation (SP-based runs)
      2. BatchLogger flat-file — SQL-level events logged by allocation_engine.py
      3. Descriptive fallback string so the modal is never blank
    """
    sql_source = sql_delete = sql_output = None

    # ── 1. Try sp_alloc_log ──
    try:
        rows = db.session.execute(
            text(
                "SELECT event_label, sql_text FROM sp_alloc_log "
                "WHERE batch_id = :bid AND sql_text IS NOT NULL "
                "ORDER BY id"
            ),
            {"bid": batch_id},
        ).fetchall()

        label_map = {r.event_label: r.sql_text for r in rows if r.sql_text}
        # Labels written by sp_run_allocation.sql
        sql_source = (
            label_map.get("SOURCE_EXTRACT")    # Phase 5b: full filtered SELECT (new)
            or label_map.get("SOURCE_COUNT")   # Phase 5: bare date-only count (old batches)
            or label_map.get("SOURCE_FILTER")
        )
        sql_delete = label_map.get("DELETE_PRIOR")
        sql_output = (
            label_map.get("DEBIT_INSERT")          # full INSERT … SELECT body
            or label_map.get("CREDIT_INSERT")
        )
    except Exception:
        pass  # sp_alloc_log not deployed or not a SP run — fall through

    # ── 2. Try BatchLogger flat-file (Python engine) ──
    if not sql_source or not sql_output:
        try:
            log_path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                sql_events = [
                    l.split("] ", 2)[-1].strip()      # strip timestamp + level
                    for l in lines
                    if "[SQL" in l
                ]
                # First SQL event = source query, last = INSERT
                if sql_events and not sql_source:
                    sql_source = sql_events[0]
                if len(sql_events) >= 2 and not sql_output:
                    sql_output = sql_events[-1]
                # DELETE is the second-to-last for engine runs
                if len(sql_events) >= 3 and not sql_delete:
                    sql_delete = sql_events[-2]
        except Exception:
            pass

    # ── 3. Descriptive fallback ──
    if not sql_source:
        sql_source = (
            f"-- Source query not yet logged for this batch.\n"
            f"-- Run this batch via ALLOCATION_SP to capture exact SQL.\n\n"
            f"SELECT *\nFROM {rule.source_table}\n"
            f"WHERE as_of_date = '{as_of_date}'\n"
            f"  -- (plus rule-specific filters defined in sp_run_allocation)"
        )
    if not sql_delete:
        sql_delete = (
            f"DELETE FROM {rule.output_table}\n"
            f"WHERE allocation_id = {rule.id}\n"
            f"  AND as_of_date = '{as_of_date}'"
        )
    if not sql_output:
        sql_output = (
            f"-- Output INSERT not yet logged for this batch.\n"
            f"-- Run this batch via ALLOCATION_SP to capture exact SQL.\n\n"
            f"SELECT *\nFROM {rule.output_table}\n"
            f"WHERE batch_run_id = '{batch_id}'\n"
            f"ORDER BY source_account_id, entry_type"
        )

    return sql_source, sql_delete, sql_output


@bp.route("/traceability")
def traceability():
    """Landing page: list of executed allocation batches and FTP runs."""
    alloc_runs = (
        db.session.query(
            BatchRun,
            AllocationRule.name.label("rule_name"),
            AllocationRule.source_table,
            AllocationRule.lookup_table,
            AllocationRule.allocation_method,
        )
        .join(AllocationRule, AllocationRule.id == BatchRun.rule_id)
        .order_by(BatchRun.started_at.desc())
        .limit(100)
        .all()
    )
    ftp_runs = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(100).all()

    return render_template(
        "reports/traceability.html",
        alloc_runs=alloc_runs,
        ftp_runs=ftp_runs,
    )


@bp.route("/traceability/batch/<batch_id>")
def trace_batch(batch_id):
    """3-panel trace for a single allocation batch: Source / Driver / Output."""
    batch = BatchRun.query.get_or_404(batch_id)
    rule = AllocationRule.query.get_or_404(batch.rule_id)

    account_id = request.args.get("account_id", "").strip()

    # ── Source rows ──
    src_model = _SOURCE_MODELS.get(rule.source_table)
    source_rows = []
    date_col = "as_of_date"
    if src_model:
        sq = src_model.query.filter_by(as_of_date=batch.as_of_date)
        if account_id:
            if hasattr(src_model, "account_id"):
                sq = sq.filter_by(account_id=account_id)
            elif hasattr(src_model, "gl_account"):
                sq = sq.filter_by(gl_account=account_id)
        raw_rows = sq.all()
        if raw_rows:
            import json
            import pandas as pd
            from app.services.allocation_engine import _apply_filters, _apply_source_dim_filters, ALLOC_CONFIG
            
            src_cfg = ALLOC_CONFIG["source_tables"].get(rule.source_table, {})
            cols = src_cfg.get("columns", [c.key for c in src_model.__table__.columns])
            df = pd.DataFrame([{col: getattr(r, col, None) for col in cols} for r in raw_rows])
            
            # Apply source dim filters
            source_dim_cfg = rule.source_dim_json if isinstance(rule.source_dim_json, dict) else (json.loads(rule.source_dim_json) if rule.source_dim_json else {})
            if source_dim_cfg:
                df = _apply_source_dim_filters(df, source_dim_cfg, src_cfg.get("dimension_columns", []))
            
            # Apply general filters
            if rule.filter_json:
                df = _apply_filters(df, rule.filter_json)
                
            # If tracking zero balances
            balance_cols = src_cfg.get("balance_columns", [])
            if getattr(rule, "balance_column", None) and rule.balance_column in balance_cols:
                balance_cols = [rule.balance_column]
            if balance_cols:
                df[balance_cols] = df[balance_cols].fillna(0)
                df = df[df[balance_cols].ne(0).any(axis=1)]

            # Account for aggregate_source
            if getattr(rule, "aggregate_source", False):
                group_cols = []
                agg_funcs = {}
                output_dim_cfg = rule.output_dim_json if isinstance(rule.output_dim_json, dict) else (json.loads(rule.output_dim_json) if rule.output_dim_json else {})
                for col in src_cfg.get("dimension_columns", []):
                    mode = output_dim_cfg.get(col, {}).get("mode", "same_as_source")
                    if mode != "fixed":
                        group_cols.append(col)
                    else:
                        agg_funcs[col] = "max"
                for col in balance_cols:
                    agg_funcs[col] = "sum"
                for k in [jk.strip() for jk in (rule.join_key or "").split(",") if jk.strip()]:
                    if k not in group_cols and k in df.columns:
                        group_cols.append(k)
                for col in src_cfg.get("columns", []):
                    if col not in group_cols and col not in agg_funcs and col in df.columns:
                        agg_funcs[col] = "max"
                if group_cols:
                    df = df.groupby(group_cols, as_index=False).agg(agg_funcs)
                elif agg_funcs:
                    df = df.assign(_dummy=1).groupby('_dummy', as_index=False).agg(agg_funcs).drop(columns=['_dummy'])

            source_rows = df.head(500).to_dict('records')
        else:
            source_rows = []
    # ── Pull REAL executed SQL from sp_alloc_log or batch log file ──
    sql_source, sql_delete, sql_output = _get_executed_sql(
        batch_id, rule, batch.as_of_date
    )

    # ── Driver (lookup) rows ──
    lkp_model = _LOOKUP_MODELS.get(rule.lookup_table)
    driver_rows = []
    if lkp_model:
        dq = lkp_model.query
        if hasattr(lkp_model, "as_of_date"):
            dq = dq.filter(
                (lkp_model.as_of_date == batch.as_of_date)
                | (lkp_model.as_of_date.is_(None))
            )
        id_col = _LOOKUP_ID_COL.get(rule.lookup_table)
        if id_col and hasattr(lkp_model, id_col):
            out_model = _OUTPUT_MODELS.get(rule.output_table, FctMgmtLedger)
            alloc_id_attr = getattr(out_model, "allocation_id", None)
            if alloc_id_attr is not None:
                used_ids = (
                    db.session.query(alloc_id_attr)
                    .filter(out_model.batch_run_id == batch_id)
                    .filter(alloc_id_attr.isnot(None))
                    .distinct()
                    .subquery()
                )
                dq = dq.filter(getattr(lkp_model, id_col).in_(used_ids))
        driver_rows = dq.limit(500).all()

    # Column names for driver table header
    driver_columns = []
    if lkp_model:
        mapper = sa_inspect(lkp_model)
        driver_columns = [c.key for c in mapper.column_attrs
                          if c.key not in ("id", "upload_batch_id", "status",
                                           "maker_id", "checker_id", "created_at",
                                           "updated_at", "checker_comment", "maker_comment")]

    # ── Output rows — pick correct model from rule.output_table ──
    out_model = _OUTPUT_MODELS.get(rule.output_table, FctMgmtLedger)
    oq = out_model.query.filter_by(batch_run_id=batch_id)
    if account_id and hasattr(out_model, "source_account_id"):
        oq = oq.filter_by(source_account_id=account_id)
    output_rows = oq.order_by(
        out_model.source_account_id, out_model.entry_type
    ).limit(500).all()

    # ── Summary — prefer batch metadata (always available) ──
    summary = {
        "source_count":    batch.source_row_count or len(source_rows),
        "driver_count":    len(driver_rows),
        "output_count":    batch.output_row_count or len(output_rows),
        "total_source":    float(batch.source_total or 0),
        "total_allocated": float(batch.output_total or 0),
        "orphan_count":    batch.orphan_count or 0,
    }

    return render_template(
        "reports/trace_alloc.html",
        batch=batch,
        rule=rule,
        source_rows=source_rows,
        driver_rows=driver_rows,
        driver_columns=driver_columns,
        output_rows=output_rows,
        summary=summary,
        sel_account_id=account_id,
        sql_source=sql_source,
        sql_output=sql_output,
        sql_delete=sql_delete,
        out_model_name=rule.output_table,
    )


@bp.route("/traceability/ftp/<ftp_run_id>")
def trace_ftp(ftp_run_id):
    """3-panel trace for a single FTP run: Source / Rate Config / Enriched Output."""
    ftp_run = FtpRun.query.get_or_404(ftp_run_id)

    account_id = request.args.get("account_id", "").strip()

    # ── Source rows ──
    sq = ProcInstData.query.filter_by(as_of_date=ftp_run.as_of_date)
    if account_id:
        sq = sq.filter_by(account_id=account_id)
    source_rows = sq.order_by(ProcInstData.account_id).limit(500).all()

    # ── Driver: product configs + rate curves used ──
    product_configs = FtpProductConfig.query.filter_by(is_active=True).all()

    # Rate rows for that as_of_date
    rate_rows = (
        RefInterestRate.query
        .filter_by(effective_date=ftp_run.as_of_date, status="APPROVED")
        .order_by(RefInterestRate.interest_rate_code, RefInterestRate.term)
        .limit(200)
        .all()
    )

    # ── Output: enriched instruments (base_rate, cost_of_fund filled) ──
    oq = ProcInstData.query.filter_by(as_of_date=ftp_run.as_of_date)
    if account_id:
        oq = oq.filter_by(account_id=account_id)
    output_rows = (
        oq.filter(ProcInstData.base_rate.isnot(None))
        .order_by(ProcInstData.account_id)
        .limit(500)
        .all()
    )

    summary = {
        "source_count": len(source_rows),
        "config_count": len(product_configs),
        "rate_count": len(rate_rows),
        "output_count": len(output_rows),
        "matched": ftp_run.instruments_matched or 0,
        "skipped": ftp_run.instruments_skipped or 0,
    }

    return render_template(
        "reports/trace_ftp.html",
        ftp_run=ftp_run,
        source_rows=source_rows,
        product_configs=product_configs,
        rate_rows=rate_rows,
        output_rows=output_rows,
        summary=summary,
        sel_account_id=account_id,
    )


@bp.route("/traceability/detail/<int:output_id>")
def trace_detail(output_id):
    """Drill-down: full chain for a single output row."""
    table = request.args.get("table", "fct_mgmt_ledger")
    if table == "fct_mgmt_instrument":
        out_row = FctMgmtInstrument.query.get_or_404(output_id)
    else:
        out_row = FctMgmtLedger.query.get_or_404(output_id)

    batch = BatchRun.query.get(out_row.batch_run_id)
    rule = AllocationRule.query.get(batch.rule_id) if batch else None

    source_row = None
    if rule:
        src_model = _SOURCE_MODELS.get(rule.source_table)
        if src_model:
            q = src_model.query.filter_by(as_of_date=out_row.as_of_date)
            if hasattr(src_model, "account_id"):
                q = q.filter_by(account_id=out_row.source_account_id)
            elif hasattr(src_model, "gl_account"):
                q = q.filter_by(gl_account=out_row.source_account_id)
            source_row = q.first()

    lookup_row = None
    if rule:
        lkp_model = _LOOKUP_MODELS.get(rule.lookup_table)
        id_col = _LOOKUP_ID_COL.get(rule.lookup_table)
        if lkp_model and id_col and out_row.allocation_id and hasattr(lkp_model, id_col):
            lookup_row = lkp_model.query.filter(
                getattr(lkp_model, id_col) == out_row.allocation_id
            ).first()

    return render_template(
        "reports/trace_detail.html",
        out_row=out_row,
        table=table,
        batch=batch,
        rule=rule,
        source_row=source_row,
        lookup_row=lookup_row,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Traceability: Execution Log Views
# ═══════════════════════════════════════════════════════════════════════════

@bp.route("/traceability/batch/<batch_id>/engine-log")
def trace_engine_log(batch_id):
    """Display the BatchLogger flat-file log for a Python-engine allocation run.

    Parses each line of the format:  [YYYY-MM-DD HH:MM:SS.mmm] [LEVEL   ] message
    and returns a list of dicts for template rendering.
    """
    batch = BatchRun.query.get_or_404(batch_id)
    log_path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")

    log_lines = []
    log_exists = os.path.isfile(log_path)
    if log_exists:
        import re
        _log_re = re.compile(
            r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]\s+\[([A-Z_]+)\s*\]\s+(.*?)$"
        )
        with open(log_path, encoding="utf-8") as fh:
            for raw in fh:
                m = _log_re.match(raw.rstrip())
                if m:
                    log_lines.append({"ts": m.group(1), "level": m.group(2).strip(), "msg": m.group(3)})
                else:
                    log_lines.append({"ts": "", "level": "RAW", "msg": raw.rstrip()})

    return render_template(
        "reports/trace_engine_log.html",
        batch=batch,
        log_lines=log_lines,
        log_exists=log_exists,
        log_path=log_path,
    )


@bp.route("/traceability/batch/<batch_id>/sql-log")
def trace_sql_log(batch_id):
    """Display sp_alloc_log rows for an SP-based allocation run.

    Shows every phase start, the rendered SQL before each EXECUTE, the resulting
    row count, and the final SUMMARY / ERROR row.
    """
    batch = BatchRun.query.get_or_404(batch_id)

    # Check table exists before querying (avoid crashes when DDL not yet applied)
    has_log_table = False
    log_rows = []
    try:
        result = db.session.execute(
            text(
                "SELECT id, phase, event_type, event_label, sql_text, "
                "row_count, message, logged_at "
                "FROM sp_alloc_log WHERE batch_id = :bid ORDER BY id"
            ),
            {"bid": batch_id},
        ).fetchall()
        has_log_table = True
        log_rows = [
            {
                "id":         r[0],
                "phase":      r[1],
                "event_type": r[2],
                "event_label":r[3],
                "sql_text":   r[4],
                "row_count":  r[5],
                "message":    r[6],
                "logged_at":  r[7],
            }
            for r in result
        ]
    except Exception:
        pass  # table not yet created — show friendly message in template

    return render_template(
        "reports/trace_sql_log.html",
        batch=batch,
        log_rows=log_rows,
        has_log_table=has_log_table,
    )
