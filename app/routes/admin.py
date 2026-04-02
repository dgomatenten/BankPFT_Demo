from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from app.models import db
from app.models.auth import User, Group

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
            g = Group.query.get(int(gid))
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
            g = Group.query.get(int(gid))
            if g:
                user.groups.append(g)

        db.session.commit()
        flash(f"User '{user.username}' updated.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/user_form.html", user=user, groups=groups)
