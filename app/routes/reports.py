from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import db
from app.models.dimensions import DimOrgUnit, DimProduct, DimCustomer, DimAccount
from app.models.staging import StgInstData, ProcInstData, StgGlData, ProcGlData
from app.models.allocation import RefStaticAllocation, FctMgmtLedger
from app.models.workflow import UploadBatch, AllocationRule, BatchRun
from sqlalchemy import func, inspect as sa_inspect

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
    "fct_mgmt_ledger": FctMgmtLedger,
    "upload_batch": UploadBatch,
    "allocation_rule": AllocationRule,
    "batch_run": BatchRun,
}


@bp.route("/")
def index():
    return render_template("reports/index.html")


@bp.route("/tables")
def tables():
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
def table_edit(table_name, pk_value):
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
def table_delete(table_name, pk_value):
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
    return render_template("reports/execution_log.html", batch=batch, records=records)
