from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import db
from app.models.workflow import AllocationRule
from app.models.allocation import RefStaticAllocation

bp = Blueprint("rules", __name__)


@bp.route("/")
def list_rules():
    rules = AllocationRule.query.order_by(AllocationRule.created_at.desc()).all()
    return render_template("rules/list.html", rules=rules)


@bp.route("/new", methods=["GET", "POST"])
def new_rule():
    if request.method == "POST":
        rule = AllocationRule(
            name=request.form["name"],
            description=request.form.get("description", ""),
            source_table=request.form.get("source_table", "proc_inst_data"),
            lookup_table=request.form.get("lookup_table", "ref_static_allocation"),
            output_table=request.form.get("output_table", "fct_mgmt_ledger"),
            join_key=request.form.get("join_key", "customer_id"),
            created_by=request.form.get("created_by", "user1"),
            status="ACTIVE",
        )
        db.session.add(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' created and active.", "success")
        return redirect(url_for("rules.detail", rule_id=rule.id))

    return render_template("rules/new.html")


@bp.route("/<int:rule_id>")
def detail(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    allocations = RefStaticAllocation.query.filter_by(status="APPROVED").all()
    return render_template("rules/detail.html", rule=rule, allocations=allocations)


@bp.route("/<int:rule_id>/toggle", methods=["POST"])
def toggle(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    rule.status = "ACTIVE" if rule.is_active else "INACTIVE"
    db.session.commit()
    flash(f"Rule {'activated' if rule.is_active else 'deactivated'}.", "success")
    return redirect(url_for("rules.detail", rule_id=rule_id))


@bp.route("/<int:rule_id>/delete", methods=["POST"])
def delete(rule_id):
    rule = AllocationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash(f"Rule '{rule.name}' deleted.", "success")
    return redirect(url_for("rules.list_rules"))
