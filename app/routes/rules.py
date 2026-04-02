import json, os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db
from app.models.workflow import AllocationRule
from app.models.allocation import RefStaticAllocation

_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "rule_config.json")
with open(_CFG_PATH) as _f:
    RULE_CONFIG = json.load(_f)

_FILTER_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "filter_config.json")
with open(_FILTER_CFG_PATH) as _f:
    FILTER_CONFIG = json.load(_f)

bp = Blueprint("rules", __name__)


@bp.route("/")
@login_required
def list_rules():
    rules = AllocationRule.query.order_by(AllocationRule.created_at.desc()).all()
    return render_template("rules/list.html", rules=rules)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_rule():
    if request.method == "POST":
        filter_raw      = request.form.get("filter_json", "").strip()
        src_dim_raw     = request.form.get("source_dim_json", "").strip()
        out_dim_raw     = request.form.get("output_dim_json", "").strip()
        generate_offset = request.form.get("generate_offset") == "1"
        rule = AllocationRule(
            name=request.form["name"],
            description=request.form.get("description", ""),
            source_table=request.form.get("source_table", "proc_inst_data"),
            lookup_table=request.form.get("lookup_table", "ref_static_allocation"),
            output_table=request.form.get("output_table", "fct_mgmt_instrument"),
            join_key=request.form.get("join_key", "customer_id"),
            filter_json=filter_raw if filter_raw else None,
            source_dim_json=src_dim_raw if src_dim_raw else None,
            output_dim_json=out_dim_raw if out_dim_raw else None,
            generate_offset=generate_offset,
            offset_account=request.form.get("offset_account", "").strip() or None,
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
        # Accept file upload or pasted JSON text
        raw = ""
        uploaded = request.files.get("rule_file")
        if uploaded and uploaded.filename:
            raw = uploaded.read().decode("utf-8", errors="replace")
        else:
            raw = request.form.get("rule_json", "").strip()

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

        rule = AllocationRule(
            name=data["name"],
            description=data.get("description", ""),
            source_table=data.get("source_table", "proc_inst_data"),
            lookup_table=data.get("lookup_table", "ref_static_allocation"),
            output_table=data.get("output_table", "fct_mgmt_instrument"),
            join_key=data.get("join_key", "customer_id"),
            filter_json=_to_json(data.get("filter_json")),
            source_dim_json=_to_json(data.get("source_dim_json")),
            output_dim_json=_to_json(data.get("output_dim_json")),
            generate_offset=bool(data.get("generate_offset", True)),
            offset_account=data.get("offset_account") or None,
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
    allocations = RefStaticAllocation.query.filter_by(status="APPROVED").all()
    return render_template("rules/detail.html", rule=rule, allocations=allocations)


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

