"""
Shared pytest fixtures for BankPFT test suite.

Every test module that needs the app or a seeded database simply requests:
    - app      → Flask test app (in-memory SQLite, isolated per session)
    - client   → Flask test client (unauthenticated)
    - auth_client → Flask test client pre-authenticated as admin
    - db_session  → the SQLAlchemy session (app context already pushed)
    - seeded_db   → db_session with minimal master data already inserted

UI (browser) test fixtures (require selenium + webdriver-manager):
    - live_server → URL of a live Werkzeug server running the test app
    - browser     → headless Chrome WebDriver (session-scoped; skipped if no chromedriver)
    - logged_in_browser → browser with an active admin session
"""

import base64
import glob
import os
import tempfile
import threading
import time
import pytest
from datetime import date

from app import create_app
from app.models import db as _db
from app.config import Config


# ─────────────────────────────────────────────────────────────────────────────
# Test application configuration — uses an in-memory SQLite database so tests
# never touch the real instance/bankpft.db file.
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    # Disable the dev-key warning in the test environment
    SQLALCHEMY_TRACK_MODIFICATIONS = False


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped app & db — created once per pytest session for speed.
# Each test that mutates data should use function-scoped transactions if needed.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create a Flask application configured for testing."""
    flask_app = create_app(TestConfig)
    yield flask_app


@pytest.fixture(scope="session")
def db(app):
    """Return the SQLAlchemy db bound to the test app (tables created once)."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope="function")
def db_session(app, db):
    """
    Function-scoped fixture: wrap each test in a transaction that is rolled back
    after the test so tests remain independent.
    """
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        # Override the session to use this connection
        _db.session.remove()
        _db.session.configure(bind=connection)
        yield _db.session
        _db.session.remove()
        transaction.rollback()
        connection.close()
        # Restore default binding
        _db.session.configure(bind=None)


@pytest.fixture(scope="function")
def client(app, db_session):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def auth_headers():
    """HTTP Basic Auth header pre-encoded for admin:admin."""
    creds = base64.b64encode(b"admin:admin").decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture(scope="function")
def auth_client(app, db_session):
    """
    Test client with an active admin session (login via form POST first).
    Use this for UI routes that require flask_login.
    """
    client = app.test_client()
    with app.app_context():
        # Ensure admin user exists (seeded by create_app via _seed_defaults)
        client.post("/auth/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Minimal master data fixture — seeds dimensions + allocation ratio so engine
# tests can run without going through the full upload workflow.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def seeded_db(db_session, app):
    """
    Insert minimal dimension data, one instrument row, and one allocation ratio
    so engine-level tests have something to work with.
    """
    from app.models.dimensions import DimOrgUnit, DimProduct, DimCustomer, DimAccount
    from app.models.staging import ProcInstData
    from app.models.allocation import RefStaticAllocation
    from app.models.auth import User, Group
    from app.models.ftp import RefInterestRate, FtpProductConfig

    # Groups & users are already seeded by create_app, but may not exist in
    # the rolled-back session — add them idempotently.
    if not Group.query.filter_by(name="Admins").first():
        admins = Group(name="Admins", description="Full access", can_make=True, can_check=True, is_admin=True)
        makers = Group(name="Makers", description="Maker", can_make=True)
        checkers = Group(name="Checkers", description="Checker", can_check=True)
        db_session.add_all([admins, makers, checkers])
        db_session.flush()
    else:
        admins = Group.query.filter_by(name="Admins").first()

    if not User.query.filter_by(username="admin").first():
        admin_user = User(username="admin", display_name="Administrator")
        admin_user.set_password("admin")
        admin_user.groups.append(admins)
        db_session.add(admin_user)
        db_session.flush()

    if not User.query.filter_by(username="maker1").first():
        maker_group = Group.query.filter_by(name="Makers").first()
        maker = User(username="maker1", display_name="Maker One")
        maker.set_password("maker1")
        if maker_group:
            maker.groups.append(maker_group)
        db_session.add(maker)
        db_session.flush()

    # Dimensions
    if not DimOrgUnit.query.get("ORG-001"):
        db_session.add(DimOrgUnit(org_unit_id="ORG-001", name="Branch 1", is_leaf=True))
        db_session.add(DimOrgUnit(org_unit_id="ORG-002", name="Branch 2", is_leaf=True))
    if not DimProduct.query.get("PROD-LON"):
        db_session.add(DimProduct(product_code="PROD-LON", name="Personal Loan", category="Retail", is_leaf=True))
    if not DimCustomer.query.get("CUST-0001"):
        db_session.add(DimCustomer(customer_id="CUST-0001", name="Test Customer 1", segment="Retail"))
    if not DimAccount.query.get("ACC-0001"):
        db_session.add(DimAccount(
            account_id="ACC-0001",
            customer_id="CUST-0001",
            product_code="PROD-LON",
            org_unit_id="ORG-001",
        ))
    db_session.flush()

    # Processed instrument data
    if not ProcInstData.query.filter_by(account_id="ACC-0001").first():
        db_session.add(ProcInstData(
            upload_batch_id="test-batch",
            as_of_date=date(2026, 1, 1),
            account_id="ACC-0001",
            customer_id="CUST-0001",
            product_code="PROD-LON",
            org_unit_id="ORG-001",
            balance=100000.0,
            interest_income=500.0,
        ))
    db_session.flush()

    # Allocation ratio — CUST-0001 → ORG-002 at 40%
    if not RefStaticAllocation.query.filter_by(customer_id="CUST-0001").first():
        db_session.add(RefStaticAllocation(
            upload_batch_id="test-batch",
            allocation_id="alloc-test-001",
            customer_id="CUST-0001",
            source_org_unit_id="ORG-001",
            target_org_unit_id="ORG-002",
            ratio=0.4,
            status="APPROVED",
            maker_id="admin",
        ))
    db_session.flush()

    # FTP: interest rate + product config
    if not RefInterestRate.query.filter_by(interest_rate_code="SWAP_RATE").first():
        db_session.add(RefInterestRate(
            effective_date=date(2026, 1, 1),
            interest_rate_code="SWAP_RATE",
            term=5,
            term_mult="Y",
            rate=0.04,
            status="APPROVED",
            maker_id="admin",
        ))
    if not FtpProductConfig.query.filter_by(product_code="PROD-LON").first():
        db_session.add(FtpProductConfig(
            product_code="PROD-LON",
            method="MOVING_AVG",
            rate_code="SWAP_RATE",
            term=5,
            term_mult="Y",
            avg_period=1,
            avg_period_mult="M",
            is_active=True,
        ))
    db_session.flush()

    return db_session


# ─────────────────────────────────────────────────────────────────────────────
# UI / Browser test fixtures
# These require selenium and webdriver-manager (both in requirements.txt).
# All UI fixtures are skipped automatically when chromedriver is not found.
# ─────────────────────────────────────────────────────────────────────────────

def _find_chromedriver():
    """Return path to a usable chromedriver binary, or None."""
    import shutil
    # 1. System PATH
    found = shutil.which("chromedriver")
    if found:
        return found
    # 2. webdriver-manager cache (~/.wdm)
    wdm_root = os.path.expanduser("~/.wdm/drivers/chromedriver")
    matches = sorted(glob.glob(os.path.join(wdm_root, "**/chromedriver"), recursive=True))
    if matches:
        return matches[-1]  # latest cached version
    return None


class UITestConfig(Config):
    """Flask config for the live Werkzeug server used by Selenium tests.

    Uses a temp-file SQLite database (not :memory:) so the connection is
    safely shared across threads. The file is deleted after the session.
    """
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key-ui"

    # Created here at class definition time so the same paths are used for the
    # full session. tempfile.mkstemp returns (fd, path).
    _db_fd, _db_path = tempfile.mkstemp(suffix="_ui_test.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}?check_same_thread=False"
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}


@pytest.fixture(scope="session")
def live_server():
    """Start a live Werkzeug HTTP server for Selenium tests.

    The server runs on 127.0.0.1:5099 in a daemon thread.  The test app uses
    a temp-file SQLite database so it survives across threads.  The admin user
    is seeded by create_app → _seed_defaults() automatically.

    Yields the base URL string, e.g. "http://127.0.0.1:5099".
    """
    from werkzeug.serving import make_server

    flask_app = create_app(UITestConfig)
    server = make_server("127.0.0.1", 5099, flask_app)
    thread = threading.Thread(target=server.serve_forever, name="ui-test-server")
    thread.daemon = True
    thread.start()

    # Brief wait to ensure the server is accepting connections
    time.sleep(0.5)

    yield "http://127.0.0.1:5099"

    server.shutdown()
    # Cleanup temp database
    try:
        os.close(UITestConfig._db_fd)
    except OSError:
        pass
    try:
        os.unlink(UITestConfig._db_path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def browser(live_server):  # noqa: F811 — live_server ensures server is up
    """Session-scoped headless Chrome WebDriver.

    Automatically skipped if no chromedriver is found.  Both the server URL
    and the driver instance are session-scoped for speed — the same browser
    process is reused for all UI tests.
    """
    driver_path = _find_chromedriver()
    if not driver_path:
        pytest.skip("chromedriver not found — install webdriver-manager and run: python -m webdriver_manager.chrome")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        pytest.skip("selenium not installed — run: pip install selenium")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")

    driver = webdriver.Chrome(service=Service(driver_path), options=opts)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def logged_in_browser(browser, live_server):
    """Browser with an active admin session (logged in once per test session)."""
    from selenium.webdriver.common.by import By

    browser.get(f"{live_server}/auth/login")
    browser.find_element(By.NAME, "username").send_keys("admin")
    browser.find_element(By.NAME, "password").send_keys("admin")
    browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(0.5)
    yield browser
