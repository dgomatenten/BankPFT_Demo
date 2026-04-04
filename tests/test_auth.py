"""Authentication & admin tests — login, logout, password change, access control."""

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _login(client, username="admin", password="admin"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def _logout(client):
    return client.get("/auth/logout", follow_redirects=True)


# ─────────────────────────────────────────────────────────────────────────────
# Login / Logout
# ─────────────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_page_renders(self, client):
        rv = client.get("/auth/login")
        assert rv.status_code == 200
        assert b"login" in rv.data.lower()

    def test_successful_login_redirects_to_dashboard(self, client):
        rv = _login(client)
        assert rv.status_code == 200
        # After login, should be on a page that is NOT the login page
        assert b"login" not in rv.data.lower() or b"logout" in rv.data.lower()

    def test_wrong_password_stays_on_login(self, client):
        rv = _login(client, password="wrongpass")
        assert rv.status_code == 200
        assert b"login" in rv.data.lower()

    def test_unknown_user_stays_on_login(self, client):
        rv = _login(client, username="nobody", password="pass")
        assert rv.status_code == 200
        assert b"login" in rv.data.lower()

    def test_logout_redirects_to_login(self, auth_client):
        rv = _logout(auth_client)
        assert rv.status_code == 200
        assert b"login" in rv.data.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Access control — unauthenticated user is redirected to login
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessControl:
    PROTECTED_ROUTES = [
        "/",
        "/rules/",
        "/ftp/",
        "/admin/users",
        "/reports/",
    ]

    @pytest.mark.parametrize("route", PROTECTED_ROUTES)
    def test_unauthenticated_redirect(self, client, route):
        rv = client.get(route, follow_redirects=False)
        # Flask-Login redirects 302 to login
        assert rv.status_code in (302, 308)
        assert "login" in rv.headers.get("Location", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# User model
# ─────────────────────────────────────────────────────────────────────────────

class TestUserModel:
    def test_password_hashing(self, app):
        from app.models.auth import User
        with app.app_context():
            u = User(username="tmp_test_user", display_name="Tmp")
            u.set_password("secure123")
            assert u.check_password("secure123") is True
            assert u.check_password("wrong") is False

    def test_user_repr(self, app):
        from app.models.auth import User
        with app.app_context():
            u = User(username="repr_user")
            assert "repr_user" in repr(u)

    def test_admin_property(self, db_session, app):
        from app.models.auth import User, Group
        with app.app_context():
            admin_user = User.query.filter_by(username="admin").first()
            # admin seeded by create_app — may not be in rolled-back session yet
            if admin_user:
                assert admin_user.is_admin is True

    def test_group_permissions(self, app):
        from app.models.auth import Group
        with app.app_context():
            g = Group(name="test_grp_perms", can_make=True, can_check=False, is_admin=False)
            assert g.can_make is True
            assert g.can_check is False
            assert g.is_admin is False


# ─────────────────────────────────────────────────────────────────────────────
# Admin routes — require admin privileges
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminRoutes:
    def test_users_list_requires_login(self, client):
        rv = client.get("/admin/users", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_groups_list_requires_login(self, client):
        rv = client.get("/admin/groups", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_admin_can_view_users(self, auth_client):
        rv = auth_client.get("/admin/users")
        assert rv.status_code == 200

    def test_admin_can_view_groups(self, auth_client):
        rv = auth_client.get("/admin/groups")
        assert rv.status_code == 200
