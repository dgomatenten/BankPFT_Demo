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
        filter_raw = request.form.get("filter_json", "").strip()
        rule = AllocationRule(
            name=request.form["name"],
            description=request.form.get("description", ""),
            source_table=request.form.get("source_table", "proc_inst_data"),
            lookup_table=request.form.get("lookup_table", "ref_static_allocation"),
            output_table=request.form.get("output_table", "fct_mgmt_ledger"),
            join_key=request.form.get("join_key", "customer_id"),
            filter_json=filter_raw if filter_raw else None,
            created_by=current_user.username,
            status="ACTIVE",
        )
        db.session.add(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' created and active.", "success")
        return redirect(url_for("rules.detail", rule_id=rule.id))

    return render_template("rules/new.html", rule_config=RULE_CONFIG, filter_config=FILTER_CONFIG)


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
