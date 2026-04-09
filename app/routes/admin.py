from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app.models import db
from app.models.auth import User, Group
from app.models.workflow import OperationVariable, AlertConfig, JsonConfig

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


# ── Alert Configurations ───────────────────────────────────────────────────

_VALID_SEVERITIES = {"danger", "warning", "info"}
_VALID_CHECK_TYPES = {"table_row_check"}


def _available_tables() -> list[str]:
    """Return sorted list of all table names known to the model registry."""
    try:
        from app.models.registry import MODEL_REGISTRY
        return sorted(MODEL_REGISTRY.keys())
    except Exception:
        return []


def _date_columns_for(table_name: str) -> list[str]:
    """Return column names that look like date fields for the given table."""
    try:
        from app.models.registry import MODEL_REGISTRY
        model = MODEL_REGISTRY.get(table_name)
        if model is None:
            return []
        cols = []
        for col in model.__table__.columns:
            if str(col.type).upper().startswith(("DATE", "TIMESTAMP")):
                cols.append(col.name)
        return cols
    except Exception:
        return []


@bp.route("/alert-configs")
@admin_required
def list_alert_configs():
    configs = AlertConfig.query.order_by(AlertConfig.name).all()
    return render_template("admin/alert_configs.html", configs=configs)


@bp.route("/alert-configs/new", methods=["GET", "POST"])
@admin_required
def new_alert_config():
    tables = _available_tables()
    if request.method == "POST":
        err = _validate_alert_config(
            name=request.form.get("name", "").strip(),
            check_type=request.form.get("check_type", "").strip(),
            table_name=request.form.get("table_name", "").strip(),
            date_column=request.form.get("date_column", "").strip(),
            severity=request.form.get("severity", "warning"),
            existing_id=None,
        )
        if err:
            flash(err, "danger")
            return render_template("admin/alert_config_form.html", config=None,
                                   tables=tables, action="new")
        cfg = AlertConfig(
            name=request.form.get("name", "").strip(),
            description=request.form.get("description", "").strip() or None,
            check_type=request.form.get("check_type", "table_row_check"),
            table_name=request.form.get("table_name", "").strip() or None,
            date_column=request.form.get("date_column", "").strip() or None,
            severity=request.form.get("severity", "warning"),
            is_active="is_active" in request.form,
            created_by=current_user.username,
        )
        db.session.add(cfg)
        db.session.commit()
        flash(f"Alert config '{cfg.name}' created.", "success")
        return redirect(url_for("admin.list_alert_configs"))
    return render_template("admin/alert_config_form.html", config=None,
                           tables=tables, action="new")


@bp.route("/alert-configs/<int:cfg_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_alert_config(cfg_id):
    cfg = AlertConfig.query.get_or_404(cfg_id)
    tables = _available_tables()
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        err = _validate_alert_config(
            name=new_name,
            check_type=request.form.get("check_type", "").strip(),
            table_name=request.form.get("table_name", "").strip(),
            date_column=request.form.get("date_column", "").strip(),
            severity=request.form.get("severity", "warning"),
            existing_id=cfg_id,
        )
        if err:
            flash(err, "danger")
            return render_template("admin/alert_config_form.html", config=cfg,
                                   tables=tables, action="edit")
        cfg.name        = new_name
        cfg.description = request.form.get("description", "").strip() or None
        cfg.check_type  = request.form.get("check_type", "table_row_check")
        cfg.table_name  = request.form.get("table_name", "").strip() or None
        cfg.date_column = request.form.get("date_column", "").strip() or None
        cfg.severity    = request.form.get("severity", "warning")
        cfg.is_active   = "is_active" in request.form
        db.session.commit()
        flash(f"Alert config '{cfg.name}' updated.", "success")
        return redirect(url_for("admin.list_alert_configs"))
    return render_template("admin/alert_config_form.html", config=cfg,
                           tables=tables, action="edit")


@bp.route("/alert-configs/<int:cfg_id>/delete", methods=["POST"])
@admin_required
def delete_alert_config(cfg_id):
    cfg = AlertConfig.query.get_or_404(cfg_id)
    name = cfg.name
    db.session.delete(cfg)
    db.session.commit()
    flash(f"Alert config '{name}' deleted.", "success")
    return redirect(url_for("admin.list_alert_configs"))


@bp.route("/alert-configs/date-columns")
@admin_required
def alert_config_date_columns():
    """AJAX: return JSON list of date columns for a given table."""
    from flask import jsonify
    table = request.args.get("table", "")
    return jsonify(_date_columns_for(table))


def _validate_alert_config(name, check_type, table_name, date_column, severity, existing_id) -> str | None:
    if not name:
        return "Name is required."
    conflict = AlertConfig.query.filter_by(name=name).first()
    if conflict and conflict.id != existing_id:
        return f"An alert config named '{name}' already exists."
    if check_type not in _VALID_CHECK_TYPES:
        return f"Check type must be one of: {', '.join(sorted(_VALID_CHECK_TYPES))}."
    if check_type == "table_row_check":
        if not table_name:
            return "Table name is required for a row-check alert."
        if not date_column:
            return "Date column is required for a row-check alert."
    if severity not in _VALID_SEVERITIES:
        return f"Severity must be one of: {', '.join(sorted(_VALID_SEVERITIES))}."
    return None


# ── JSON Configurations ────────────────────────────────────────────────────

import json
import os

_JSON_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config"))


def _discover_config_files() -> list[dict]:
    """Return list of {name, path} for all .json files in app/config/."""
    results = []
    for fn in sorted(os.listdir(_JSON_CONFIG_DIR)):
        if fn.endswith(".json"):
            results.append({
                "name": fn.removesuffix(".json"),
                "path": os.path.join(_JSON_CONFIG_DIR, fn),
                "filename": fn,
            })
    return results


@bp.route("/json-configs")
@admin_required
def list_json_configs():
    db_configs = JsonConfig.query.order_by(JsonConfig.config_name).all()
    file_configs = _discover_config_files()

    # Build lookup of DB configs by name
    db_map = {c.config_name: c for c in db_configs}

    # Merge: show filesystem configs with DB sync status
    merged = []
    for fc in file_configs:
        db_entry = db_map.pop(fc["name"], None)
        merged.append({
            "name": fc["name"],
            "filename": fc["filename"],
            "in_db": db_entry is not None,
            "db_entry": db_entry,
            "in_filesystem": True,
        })
    # Any DB-only configs (not on filesystem)
    for name, db_entry in db_map.items():
        merged.append({
            "name": name,
            "filename": None,
            "in_db": True,
            "db_entry": db_entry,
            "in_filesystem": False,
        })

    return render_template("admin/json_configs.html", configs=merged)


@bp.route("/json-configs/sync-all", methods=["POST"])
@admin_required
def sync_all_json_configs():
    """Load all filesystem JSON configs into the database."""
    file_configs = _discover_config_files()
    loaded = 0
    for fc in file_configs:
        try:
            with open(fc["path"], encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            flash(f"Error reading {fc['filename']}: {e}", "danger")
            continue

        existing = JsonConfig.query.filter_by(config_name=fc["name"]).first()
        if existing:
            existing.config_data = data
            existing.updated_by = current_user.username
        else:
            db.session.add(JsonConfig(
                config_name=fc["name"],
                config_data=data,
                updated_by=current_user.username,
            ))
        loaded += 1

    db.session.commit()
    flash(f"Synced {loaded} config(s) from filesystem to database.", "success")
    return redirect(url_for("admin.list_json_configs"))


@bp.route("/json-configs/<int:cfg_id>")
@admin_required
def view_json_config(cfg_id):
    cfg = JsonConfig.query.get_or_404(cfg_id)
    # Pretty-print the JSON for display
    pretty = json.dumps(cfg.config_data, indent=2, ensure_ascii=False)
    return render_template("admin/json_config_view.html", config=cfg, pretty_json=pretty)


@bp.route("/json-configs/<int:cfg_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_json_config(cfg_id):
    cfg = JsonConfig.query.get_or_404(cfg_id)

    if request.method == "POST":
        raw_json = request.form.get("config_data", "").strip()
        description = request.form.get("description", "").strip() or None
        is_active = "is_active" in request.form

        if not raw_json:
            flash("JSON content is required.", "danger")
            return render_template("admin/json_config_form.html", config=cfg,
                                   raw_json=raw_json)
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "danger")
            return render_template("admin/json_config_form.html", config=cfg,
                                   raw_json=raw_json)

        cfg.config_data = parsed
        cfg.description = description
        cfg.is_active = is_active
        cfg.updated_by = current_user.username
        db.session.commit()
        flash(f"Config '{cfg.config_name}' updated.", "success")
        return redirect(url_for("admin.view_json_config", cfg_id=cfg.id))

    pretty = json.dumps(cfg.config_data, indent=2, ensure_ascii=False)
    return render_template("admin/json_config_form.html", config=cfg, raw_json=pretty)


@bp.route("/json-configs/sync/<config_name>", methods=["POST"])
@admin_required
def sync_json_config(config_name):
    """Load a single filesystem config into the database."""
    path = os.path.join(_JSON_CONFIG_DIR, f"{config_name}.json")
    if not os.path.isfile(path):
        flash(f"Config file '{config_name}.json' not found on filesystem.", "danger")
        return redirect(url_for("admin.list_json_configs"))

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        flash(f"Error reading {config_name}.json: {e}", "danger")
        return redirect(url_for("admin.list_json_configs"))

    existing = JsonConfig.query.filter_by(config_name=config_name).first()
    if existing:
        existing.config_data = data
        existing.updated_by = current_user.username
    else:
        db.session.add(JsonConfig(
            config_name=config_name,
            config_data=data,
            updated_by=current_user.username,
        ))

    db.session.commit()
    flash(f"Config '{config_name}' synced to database.", "success")
    return redirect(url_for("admin.list_json_configs"))


@bp.route("/json-configs/<int:cfg_id>/export", methods=["POST"])
@admin_required
def export_json_config(cfg_id):
    """Write DB config back to the filesystem."""
    cfg = JsonConfig.query.get_or_404(cfg_id)
    path = os.path.join(_JSON_CONFIG_DIR, f"{cfg.config_name}.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg.config_data, fh, indent=4, ensure_ascii=False)
            fh.write("\n")
    except OSError as e:
        flash(f"Error writing {cfg.config_name}.json: {e}", "danger")
        return redirect(url_for("admin.list_json_configs"))

    flash(f"Config '{cfg.config_name}' exported to filesystem.", "success")
    return redirect(url_for("admin.list_json_configs"))


@bp.route("/json-configs/<int:cfg_id>/delete", methods=["POST"])
@admin_required
def delete_json_config(cfg_id):
    cfg = JsonConfig.query.get_or_404(cfg_id)
    name = cfg.config_name
    db.session.delete(cfg)
    db.session.commit()
    flash(f"Config '{name}' removed from database.", "success")
    return redirect(url_for("admin.list_json_configs"))
