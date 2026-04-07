import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db
from app.models.workflow import AllocationRule
from app.models.allocation import RefStaticAllocation
from app.core.config_loader import load_config

RULE_CONFIG = load_config("allocation_rule_form_config")
FILTER_CONFIG = load_config("filter_config")

bp = Blueprint("rules", __name__)


def _parse_rule_form(fallback_join_key: str = "customer_id") -> dict:
    """Extract and normalise shared rule form fields from request.form."""
    entry_mode = request.form.get("entry_mode", "BOTH").strip().upper()
    if entry_mode not in ("BOTH", "DEBIT_ONLY", "CREDIT_ONLY"):
        entry_mode = "BOTH"
    alloc_method = request.form.get("allocation_method", "RATIO").strip().upper()
    if alloc_method not in ("RATIO", "DISTRIBUTION", "STATIC"):
        alloc_method = "RATIO"
    join_keys = request.form.getlist("join_keys")
    join_key = ",".join(k.strip() for k in join_keys if k.strip()) or fallback_join_key
    filter_raw = request.form.get("filter_json", "").strip()
    src_dim_raw = request.form.get("source_dim_json", "").strip()
    out_dim_raw = request.form.get("output_dim_json", "").strip()
    crd_dim_raw = request.form.get("credit_dim_json", "").strip()
    distribution_driver = request.form.get("distribution_driver", "").strip() or None
    return {
        "allocation_method": alloc_method,
        "entry_mode": entry_mode,
        "join_key": join_key,
        "generate_offset": (entry_mode != "CREDIT_ONLY"),
        "filter_json": filter_raw or None,
        "source_dim_json": src_dim_raw or None,
        "output_dim_json": out_dim_raw or None,
        "credit_dim_json": crd_dim_raw or None,
        "distribution_driver": distribution_driver,
    }


@bp.route("/")
@login_required
def list_rules():
    rules = AllocationRule.query.order_by(AllocationRule.created_at.desc()).all()
    return render_template("rules/list.html", rules=rules)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_rule():
    if request.method == "POST":
        form = _parse_rule_form(fallback_join_key="customer_id")
        # For STATIC method, no lookup table / join key needed; keep whatever was submitted
        lookup_table = request.form.get("lookup_table", "ref_static_allocation")
        if form["allocation_method"] == "DISTRIBUTION":
            lookup_table = "ref_static_distribution"
        rule = AllocationRule(
            name=request.form["name"],
            description=request.form.get("description", ""),
            source_table=request.form.get("source_table", "proc_inst_data"),
            lookup_table=lookup_table,
            output_table=request.form.get("output_table", "fct_mgmt_instrument"),
            join_key=form["join_key"],
            filter_json=form["filter_json"],
            source_dim_json=form["source_dim_json"],
            output_dim_json=form["output_dim_json"],
            credit_dim_json=form["credit_dim_json"],
            allocation_method=form["allocation_method"],
            distribution_driver=form["distribution_driver"],
            entry_mode=form["entry_mode"],
            generate_offset=form["generate_offset"],
            created_by=current_user.username,
            status="ACTIVE",
        )
        db.session.add(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' created and active.", "success")
        return redirect(url_for("rules.detail", rule_id=rule.id))

    return render_template("rules/new.html", rule_config=RULE_CONFIG, filter_config=FILTER_CONFIG)


@bp.route("/import", methods=["GET", "POST"])
@login_required
def import_rule():
    """Create an AllocationRule from an uploaded/pasted JSON definition."""
    if request.method == "POST":
        # Accept pasted/JS-populated textarea first; fall back to raw file bytes
        raw = request.form.get("rule_json", "").strip()
        if not raw:
            uploaded = request.files.get("rule_file")
            if uploaded and uploaded.filename:
                raw = uploaded.read().decode("utf-8", errors="replace").strip()

        if not raw:
            flash("No JSON provided.", "warning")
            return render_template("rules/import.html")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            flash(f"Invalid JSON: {exc}", "danger")
            return render_template("rules/import.html")

        if not data.get("name"):
            flash("JSON must contain a 'name' field.", "danger")
            return render_template("rules/import.html")

        # Serialise nested dicts back to JSON strings if needed
        def _to_json(v):
            if v is None:
                return None
            return json.dumps(v) if isinstance(v, dict) else str(v)

        # join_key: accept string "customer_id", comma-separated "a,b", or list ["a","b"]
        raw_jk = data.get("join_key", data.get("join_keys", "customer_id"))
        if isinstance(raw_jk, list):
            join_key_val = ",".join(str(k).strip() for k in raw_jk if str(k).strip())
        else:
            join_key_val = str(raw_jk).strip() or "customer_id"

        raw_method = (data.get("allocation_method") or "RATIO").strip().upper()
        if raw_method not in ("RATIO", "DISTRIBUTION", "STATIC"):
            raw_method = "RATIO"
        import_lookup = data.get("lookup_table", "ref_static_allocation")
        if raw_method == "DISTRIBUTION":
            import_lookup = "ref_static_distribution"

        rule = AllocationRule(
            name=data["name"],
            description=data.get("description", ""),
            source_table=data.get("source_table", "proc_inst_data"),
            lookup_table=import_lookup,
            output_table=data.get("output_table", "fct_mgmt_instrument"),
            join_key=join_key_val,
            filter_json=_to_json(data.get("filter_json")),
            source_dim_json=_to_json(data.get("source_dim_json")),
            output_dim_json=_to_json(data.get("output_dim_json")),
            credit_dim_json=_to_json(data.get("credit_dim_json")),
            allocation_method=raw_method,
            distribution_driver=data.get("distribution_driver") or None,
            entry_mode=(
                data.get("entry_mode") or
                ("BOTH" if data.get("generate_offset", True) else "DEBIT_ONLY")
            ),
            generate_offset=bool(data.get("generate_offset", True)),
            created_by=current_user.username,
            status="ACTIVE",
        )
        db.session.add(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' imported successfully.", "success")
        return redirect(url_for("rules.detail", rule_id=rule.id))

    return render_template("rules/import.html")


@bp.route("/<int:rule_id>")
@login_required
def detail(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    allocations = (
        RefStaticAllocation.query.filter_by(status="APPROVED").all()
        if rule.lookup_table == "ref_static_allocation"
        else []
    )
    return render_template("rules/detail.html", rule=rule, allocations=allocations)


@bp.route("/<int:rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_rule(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    if request.method == "POST":
        form = _parse_rule_form(fallback_join_key=rule.join_key)
        lookup_table = request.form.get("lookup_table", rule.lookup_table)
        if form["allocation_method"] == "DISTRIBUTION":
            lookup_table = "ref_static_distribution"
        rule.name           = request.form["name"]
        rule.description    = request.form.get("description", "")
        rule.source_table   = request.form.get("source_table", rule.source_table)
        rule.lookup_table   = lookup_table
        rule.output_table   = request.form.get("output_table", rule.output_table)
        rule.join_key       = form["join_key"]
        rule.filter_json    = form["filter_json"]
        rule.source_dim_json = form["source_dim_json"]
        rule.output_dim_json = form["output_dim_json"]
        rule.credit_dim_json = form["credit_dim_json"]
        rule.allocation_method = form["allocation_method"]
        rule.distribution_driver = form["distribution_driver"]
        rule.entry_mode     = form["entry_mode"]
        rule.generate_offset = form["generate_offset"]
        db.session.commit()
        flash(f"Rule '{rule.name}' updated.", "success")
        return redirect(url_for("rules.detail", rule_id=rule.id))

    return render_template("rules/edit.html", rule=rule,
                           rule_config=RULE_CONFIG, filter_config=FILTER_CONFIG)


@bp.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    rule.status = "ACTIVE" if rule.is_active else "INACTIVE"
    db.session.commit()
    flash(f"Rule {'activated' if rule.is_active else 'deactivated'}.", "success")
    return redirect(url_for("rules.detail", rule_id=rule_id))


@bp.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
def delete(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash(f"Rule '{rule.name}' deleted.", "success")
    return redirect(url_for("rules.list_rules"))

