from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app.models import db
from app.models.auth import User, Group
from app.models.workflow import OperationVariable

bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


# ── Groups ─────────────────────────────────────────────

@bp.route("/groups")
@admin_required
def list_groups():
    groups = Group.query.order_by(Group.name).all()
    return render_template("admin/groups.html", groups=groups)


@bp.route("/groups/new", methods=["GET", "POST"])
@admin_required
def new_group():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Group name is required.", "danger")
            return redirect(request.url)
        if Group.query.filter_by(name=name).first():
            flash("Group name already exists.", "danger")
            return redirect(request.url)

        group = Group(
            name=name,
            description=request.form.get("description", "").strip(),
            can_make="can_make" in request.form,
            can_check="can_check" in request.form,
            is_admin="is_admin" in request.form,
        )
        db.session.add(group)
        db.session.commit()
        flash(f"Group '{group.name}' created.", "success")
        return redirect(url_for("admin.list_groups"))

    return render_template("admin/group_form.html", group=None)


@bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_group(group_id):
    group = Group.query.get_or_404(group_id)
    if request.method == "POST":
        group.name = request.form.get("name", "").strip()
        group.description = request.form.get("description", "").strip()
        group.can_make = "can_make" in request.form
        group.can_check = "can_check" in request.form
        group.is_admin = "is_admin" in request.form
        group.is_active = "is_active" in request.form
        db.session.commit()
        flash(f"Group '{group.name}' updated.", "success")
        return redirect(url_for("admin.list_groups"))

    return render_template("admin/group_form.html", group=group)


# ── Users ──────────────────────────────────────────────

@bp.route("/users")
@admin_required
def list_users():
    users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=users)


@bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def new_user():
    groups = Group.query.filter_by(is_active=True).order_by(Group.name).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(request.url)
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(request.url)

        user = User(
            username=username,
            display_name=request.form.get("display_name", "").strip(),
        )
        user.set_password(password)

        group_ids = request.form.getlist("groups")
        for gid in group_ids:
            try:
                g = Group.query.get(int(gid))
            except ValueError:
                continue
            if g:
                user.groups.append(g)

        db.session.add(user)
        db.session.commit()
        flash(f"User '{user.username}' created.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/user_form.html", user=None, groups=groups)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    groups = Group.query.filter_by(is_active=True).order_by(Group.name).all()

    if request.method == "POST":
        user.display_name = request.form.get("display_name", "").strip()
        user.is_active = "is_active" in request.form

        new_pw = request.form.get("password", "").strip()
        if new_pw:
            user.set_password(new_pw)

        user.groups.clear()
        group_ids = request.form.getlist("groups")
        for gid in group_ids:
            try:
                g = Group.query.get(int(gid))
            except ValueError:
                continue
            if g:
                user.groups.append(g)

        db.session.commit()
        flash(f"User '{user.username}' updated.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/user_form.html", user=user, groups=groups)


# ── Operation Variables ────────────────────────────────────

_VALID_TYPES = {"date", "string", "number"}


@bp.route("/op-vars")
@admin_required
def list_op_vars():
    variables = OperationVariable.query.order_by(
        OperationVariable.is_system.desc(), OperationVariable.key
    ).all()
    return render_template("admin/op_vars.html", variables=variables)


@bp.route("/op-vars/new", methods=["GET", "POST"])
@admin_required
def new_op_var():
    if request.method == "POST":
        key = request.form.get("key", "").strip()
        value = request.form.get("value", "").strip()
        description = request.form.get("description", "").strip() or None
        data_type = request.form.get("data_type", "string").strip()

        error = _validate_op_var(key, value, data_type, existing_id=None)
        if error:
            flash(error, "danger")
            return render_template("admin/op_var_form.html", var=None,
                                   valid_types=sorted(_VALID_TYPES))

        var = OperationVariable(
            key=key, value=value, description=description,
            data_type=data_type, is_system=False,
            updated_by=current_user.username,
        )
        db.session.add(var)
        db.session.commit()
        flash(f"Variable '{key}' created.", "success")
        return redirect(url_for("admin.list_op_vars"))

    return render_template("admin/op_var_form.html", var=None,
                           valid_types=sorted(_VALID_TYPES))


@bp.route("/op-vars/<int:var_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_op_var(var_id):
    var = OperationVariable.query.get_or_404(var_id)
    if request.method == "POST":
        key = request.form.get("key", "").strip()
        value = request.form.get("value", "").strip()
        description = request.form.get("description", "").strip() or None
        data_type = request.form.get("data_type", "string").strip()
        is_active = request.form.get("is_active") == "1"

        error = _validate_op_var(key, value, data_type, existing_id=var_id)
        if error:
            flash(error, "danger")
            return render_template("admin/op_var_form.html", var=var,
                                   valid_types=sorted(_VALID_TYPES))

        var.key = key
        var.value = value
        var.description = description
        var.data_type = data_type
        var.is_active = is_active
        var.updated_by = current_user.username
        db.session.commit()
        flash(f"Variable '{key}' updated.", "success")
        return redirect(url_for("admin.list_op_vars"))

    return render_template("admin/op_var_form.html", var=var,
                           valid_types=sorted(_VALID_TYPES))


@bp.route("/op-vars/<int:var_id>/delete", methods=["POST"])
@admin_required
def delete_op_var(var_id):
    var = OperationVariable.query.get_or_404(var_id)
    if var.is_system:
        flash(f"System variable '{var.key}' cannot be deleted.", "danger")
        return redirect(url_for("admin.list_op_vars"))
    key = var.key
    db.session.delete(var)
    db.session.commit()
    flash(f"Variable '{key}' deleted.", "success")
    return redirect(url_for("admin.list_op_vars"))


def _validate_op_var(key: str, value: str, data_type: str, existing_id) -> str | None:
    """Return error message string or None if valid."""
    if not key:
        return "Key is required."
    import re
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
        return "Key must start with a letter or underscore and contain only letters, digits, and underscores."
    if data_type not in _VALID_TYPES:
        return f"Data type must be one of: {', '.join(sorted(_VALID_TYPES))}."
    # Check uniqueness
    conflict = OperationVariable.query.filter_by(key=key).first()
    if conflict and conflict.id != existing_id:
        return f"A variable with key '{key}' already exists."
    # Type validation on value
    if value:
        if data_type == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return "Date value must be in YYYY-MM-DD format."
        elif data_type == "number":
            try:
                float(value)
            except ValueError:
                return "Number value must be a valid numeric string."
    return None
