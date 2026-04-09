"""
UI Integration tests — BankPFT
================================
These tests run against a live Werkzeug HTTP server (port 5099) using a
headless Chrome browser via Selenium.  They verify:

  * Pages render without JavaScript errors
  * JavaScript interactions behave correctly (filter editor, file preview)
  * Navigation flows complete end-to-end

Requirements: selenium>=4.0, webdriver-manager>=4.0 (both in requirements.txt)

All tests in this file are tagged with the 'ui' mark.  To run only UI tests:
  python -m pytest tests/test_ui.py -v

To skip UI tests and run only unit tests:
  python -m pytest tests/ -v --ignore=tests/test_ui.py

The browser + live_server fixtures are defined in conftest.py and are
automatically skipped when chromedriver is not available.
"""

import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

pytestmark = pytest.mark.ui


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

class TestUILogin:
    """Login page rendering and authentication flow."""

    def test_login_page_title_and_fields(self, browser, live_server):
        """Login page renders with username/password fields and sign-in button."""
        browser.get(f"{live_server}/auth/login")
        assert "BankPFT" in browser.title
        assert browser.find_element(By.NAME, "username")
        assert browser.find_element(By.NAME, "password")
        assert browser.find_element(By.CSS_SELECTOR, "button[type='submit']")

    def test_wrong_password_stays_on_login(self, browser, live_server):
        """Failed login stays on the login page."""
        browser.get(f"{live_server}/auth/login")
        browser.find_element(By.NAME, "username").clear()
        browser.find_element(By.NAME, "username").send_keys("admin")
        browser.find_element(By.NAME, "password").clear()
        browser.find_element(By.NAME, "password").send_keys("wrongpassword")
        browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(0.5)
        assert "/auth/login" in browser.current_url

    def test_successful_login_redirects_away_from_login(self, browser, live_server):
        """Correct credentials redirect to the dashboard."""
        browser.get(f"{live_server}/auth/login")
        browser.find_element(By.NAME, "username").clear()
        browser.find_element(By.NAME, "username").send_keys("admin")
        browser.find_element(By.NAME, "password").clear()
        browser.find_element(By.NAME, "password").send_keys("admin")
        browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(0.5)
        assert "/auth/login" not in browser.current_url

    def test_unauthenticated_access_redirects_to_login(self, browser, live_server):
        """Accessing a protected route without a session redirects to login."""
        # Open a fresh tab with no session by deleting cookies first
        browser.delete_all_cookies()
        browser.get(f"{live_server}/rules/")
        time.sleep(0.3)
        assert "login" in browser.current_url


# ─────────────────────────────────────────────────────────────────────────────
# Navigation
# ─────────────────────────────────────────────────────────────────────────────

class TestUINavigation:
    """Sidebar navigation renders correct labels and each page loads."""

    def test_sidebar_contains_main_nav_links(self, logged_in_browser, live_server):
        """All main nav links are visible in the sidebar after login."""
        logged_in_browser.get(f"{live_server}/")
        nav_text = logged_in_browser.find_element(By.CSS_SELECTOR, "nav, .sidebar, aside").text
        for label in ["Dashboard", "Data Management", "Allocation Rules", "Batch", "Reports"]:
            assert label in nav_text, f"'{label}' not found in sidebar"

    def test_dashboard_loads(self, logged_in_browser, live_server):
        """Dashboard page returns a visible heading."""
        logged_in_browser.get(f"{live_server}/")
        heading = logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2")
        assert heading.is_displayed()

    def test_rules_list_loads(self, logged_in_browser, live_server):
        """Allocation Rules list page loads without error."""
        logged_in_browser.get(f"{live_server}/rules/")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()

    def test_ftp_page_loads(self, logged_in_browser, live_server):
        """Fund Transfer Pricing page loads without error."""
        logged_in_browser.get(f"{live_server}/ftp/")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()

    def test_reports_page_loads(self, logged_in_browser, live_server):
        """Reports index loads without error."""
        logged_in_browser.get(f"{live_server}/reports/")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()

    def test_batch_execution_page_loads(self, logged_in_browser, live_server):
        """Batch execution page loads without error."""
        logged_in_browser.get(f"{live_server}/batch/")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()

    def test_test_suite_page_loads(self, logged_in_browser, live_server):
        """Test Suite page loads without error."""
        logged_in_browser.get(f"{live_server}/tests/")
        assert "Test Suite" in logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").text


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite UI
# ─────────────────────────────────────────────────────────────────────────────

class TestUITestSuiteIndex:
    """Test suite run-history dashboard."""

    def test_run_button_present_and_enabled(self, logged_in_browser, live_server):
        """'Run Full Suite' button is rendered and initially enabled."""
        logged_in_browser.get(f"{live_server}/tests/")
        btn = logged_in_browser.find_element(By.CSS_SELECTOR, "button[type='submit']")
        assert btn.is_enabled()
        assert "Run" in btn.text

    def test_run_history_info_text_present(self, logged_in_browser, live_server):
        """The informational footer text about the test suite is always present."""
        logged_in_browser.get(f"{live_server}/tests/")
        page_text = logged_in_browser.find_element(By.TAG_NAME, "body").text
        # This info line is rendered regardless of whether any runs exist
        assert "pytest" in page_text
        assert "Admins" in page_text or "Admin" in page_text


# ─────────────────────────────────────────────────────────────────────────────
# JavaScript: Filter Editor
# ─────────────────────────────────────────────────────────────────────────────

class TestUIFilterEditor:
    """JavaScript filter editor component on the rule create/edit page."""

    def test_filter_editor_renders(self, logged_in_browser, live_server):
        """Filter editor card is visible on the rule-new page."""
        logged_in_browser.get(f"{live_server}/rules/new")
        editor = logged_in_browser.find_element(By.ID, "filter-editor")
        assert editor.is_displayed()

    def test_no_filters_message_shown_initially(self, logged_in_browser, live_server):
        """The 'no filters' placeholder text is visible before any condition is added."""
        logged_in_browser.get(f"{live_server}/rules/new")
        msg = logged_in_browser.find_element(By.ID, "no-filters-msg")
        assert msg.is_displayed()

    def test_add_condition_button_adds_a_row(self, logged_in_browser, live_server):
        """Clicking 'Add Condition' inserts a new filter row into the DOM."""
        logged_in_browser.get(f"{live_server}/rules/new")
        rows_before = logged_in_browser.find_elements(By.CSS_SELECTOR, ".filter-row")
        assert len(rows_before) == 0

        btn = logged_in_browser.find_element(By.ID, "add-filter-btn")
        logged_in_browser.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(0.2)
        logged_in_browser.execute_script("arguments[0].click();", btn)
        time.sleep(0.3)

        rows_after = logged_in_browser.find_elements(By.CSS_SELECTOR, ".filter-row")
        assert len(rows_after) == 1

    def test_remove_button_removes_row(self, logged_in_browser, live_server):
        """Clicking the remove (×) button on a filter row deletes that row."""
        logged_in_browser.get(f"{live_server}/rules/new")
        add_btn = logged_in_browser.find_element(By.ID, "add-filter-btn")
        logged_in_browser.execute_script("arguments[0].scrollIntoView(true);", add_btn)
        time.sleep(0.2)
        logged_in_browser.execute_script("arguments[0].click();", add_btn)
        logged_in_browser.execute_script("arguments[0].click();", add_btn)
        time.sleep(0.3)
        assert len(logged_in_browser.find_elements(By.CSS_SELECTOR, ".filter-row")) == 2

        remove_btn = logged_in_browser.find_element(By.CSS_SELECTOR, ".remove-filter-btn")
        logged_in_browser.execute_script("arguments[0].click();", remove_btn)
        time.sleep(0.3)
        assert len(logged_in_browser.find_elements(By.CSS_SELECTOR, ".filter-row")) == 1

    def test_no_filters_message_hidden_after_add(self, logged_in_browser, live_server):
        """The 'no filters' placeholder is hidden once a condition row is added."""
        logged_in_browser.get(f"{live_server}/rules/new")
        msg = logged_in_browser.find_element(By.ID, "no-filters-msg")
        assert msg.is_displayed()

        btn = logged_in_browser.find_element(By.ID, "add-filter-btn")
        logged_in_browser.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(0.2)
        logged_in_browser.execute_script("arguments[0].click();", btn)
        time.sleep(0.3)
        assert not msg.is_displayed()

    def test_logic_radio_buttons_present(self, logged_in_browser, live_server):
        """AND / OR logic radio buttons are present in the filter editor."""
        logged_in_browser.get(f"{live_server}/rules/new")
        and_btn = logged_in_browser.find_element(By.ID, "logic-and")
        or_btn  = logged_in_browser.find_element(By.ID, "logic-or")
        assert and_btn.is_selected()   # AND is checked by default
        assert not or_btn.is_selected()


# ─────────────────────────────────────────────────────────────────────────────
# JavaScript: File Upload Preview (Rule & FTP imports)
# ─────────────────────────────────────────────────────────────────────────────

class TestUIFileUploadPages:
    """Import pages render their file input and JSON textarea."""

    def test_rule_import_page_has_file_input_and_textarea(self, logged_in_browser, live_server):
        """Rule JSON import page contains a file input and a JSON text area."""
        logged_in_browser.get(f"{live_server}/rules/import")
        assert logged_in_browser.find_element(By.ID, "rule_file_input").is_displayed()
        assert logged_in_browser.find_element(By.ID, "rule_json_area").is_displayed()

    def test_ftp_config_import_page_has_file_input_and_textarea(self, logged_in_browser, live_server):
        """FTP config JSON import page contains a file input and a JSON text area."""
        logged_in_browser.get(f"{live_server}/ftp/config/import")
        assert logged_in_browser.find_element(By.ID, "config_file_input").is_displayed()
        assert logged_in_browser.find_element(By.ID, "config_json_area").is_displayed()


# ─────────────────────────────────────────────────────────────────────────────
# Admin pages
# ─────────────────────────────────────────────────────────────────────────────

class TestUIAdminPages:
    """Admin-only pages load for the admin user."""

    def test_users_page_loads(self, logged_in_browser, live_server):
        """Users management page renders a heading."""
        logged_in_browser.get(f"{live_server}/admin/users")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()

    def test_groups_page_loads(self, logged_in_browser, live_server):
        """Groups management page renders a heading."""
        logged_in_browser.get(f"{live_server}/admin/groups")
        assert logged_in_browser.find_element(By.CSS_SELECTOR, "h1, h2").is_displayed()
