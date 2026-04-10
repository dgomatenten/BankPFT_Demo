# AI Development Guide for BankPFT

This guide details the explicit architectural paradigms that must be followed when building new features, routes, or database implementations within the BankPFT system.

AI Assistants (such as GitHub Copilot, Cursor, or Gemini) should use this file to quickly understand how BankPFT separates concerns between configuration mapping and database tracking.

---

## 1. The Config VS Database Principle

When asked to build a new feature (e.g. extending an allocation mapping variable or introducing a new data-import schema), never map fixed dropdown variables strictly into SQLAlchemy models. 

**Database Models** exist strictly to log **transient runtime state** (e.g. what a user actively submitted, what batch ran, error outputs). Furthermore, the core database engine is **PostgreSQL**. The platform expects developers to embrace PostgreSQL's powerful **JSON/JSONB** data types rather than resorting to over-complicated relational tables arrays when mapping loose hierarchical configurations (such as flexible filter arrays or dimensional parsing payloads).

**JSON Configuration Files** exist to manage **static definitions** external to the database.

#### Example Workflow for Adding a "Region" Upload Option:
1. Do not hardcode a new python route to parse the "Region" file format.
2. Open `app/config/upload_config.json`.
3. Append a new `"REGION"` block defining its required columns, its numeric bounds, and validation checks.
4. The system's central parser (`app/services/upload_service.py`) and Maker/Checker flow will instantly subsume this JSON mapping without requiring any new lines of backend logic.

---

## 2. Model Extensions & Migrations

If an overarching new dimension or entity requirement genuinely forces a database change (such as adding the `transaction_number` dimensionality payload):

1. **Schema DDL**: Use `db/ddl/` to track raw migrations. Standard deployments utilize raw `.sql` execution.
2. **SQLAlchemy Translation**: Append the raw migration column into the appropriate `app/models/` Python file to mirror the physical DDL.
3. **Mixin Usage**: Rely on BankPFT's robust mixin architecture (`app/models/mixins.py`). If the entity requires manual user approval, inject `MakerCheckerMixin` into its class declaration. If the entity needs standard audit metadata, inject `TimestampMixin`.

---

## 3. The Blueprint Execution Contract

All endpoints adhere to a strict Application Factory abstraction wrapped into Blueprints. Do not pollute `__init__.py` with inline routes. 

1. Create or extend the focused Blueprint (e.g. `app/routes/ftp.py`).
2. Implement backend data sanitization exclusively through standard Flask-WTF or custom request body parsing.
3. Call helper engines inside `app/services/` to do the initial dispatching.

**CRITICAL: Orchestration vs. Calculation**
- **The Validation Gateway**: Services must fully validate request payloads and environmental state (e.g. "Is the as-of-date closed?") before execution.
- **The PostgreSQL Engine**: For intensive business logic (such as Rule Engine or heavy allocations), execute natively inside **PostgreSQL Stored Procedures**. 
- **The Python Orchestrator**: Flask acts as the "Brain" that coordinates steps, logs audit traces, and handles rollbacks. Do NOT build heavy in-memory loops in Python where SQL is natively superior.

4. Keep the presentation layer pure – return `render_template` calls drawing from `app/templates/` containing the exact payload context strings needed to render. Let Jinja handle iterative presentation.

---

## 4. Frontend Bootstrap Usage

When instructed to add UI changes:
- Do not build custom CSS files to center divs or color backgrounds.
- Rely 100% on **Bootstrap 5 UI** primitives. Use grids (`row`, `col`), spacing utilities (`mt-3`, `pb-2`), card elements (`card`, `card-header`), and native Bootstrap alerts/badges for conveying system constraints or failure.
- Ensure views adapt to constraints elegantly using `table-responsive` spans for grid outputs.
- **Strict Local Asset Sourcing:** The application is required to use locally hosted Bootstrap files. Under no circumstances should you inject external `<link>` or `<script>` tags referencing outside CDNs (like unpkg or jsdelivr). All web assets must resolve internally.
