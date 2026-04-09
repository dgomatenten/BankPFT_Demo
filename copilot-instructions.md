# BankPFT Copilot Instructions

This document provides definitive instructions for any AI assistant (GitHub Copilot, Cursor, etc.) operating within the BankPFT (Management Allocation System) codebase. 

By strictly adhering to these rules, you will ensure that the Application Factory pattern is upheld, Blueprints remain modular, and all Python code conforms to PEP 8 standards.

## 1. Core Architecture & Routing
- **Application Factory Pattern:** BankPFT is built using the Flask Application Factory pattern. Never instantiate global `app = Flask(__name__)` outside of the factory (`app/__init__.py`). All new integrations must be initialized inside `create_app()`.
- **Blueprints:** All routing must be encapsulated in Blueprints. Create or utilize existing files in `app/routes/`. Register new Blueprints centrally inside `app/__init__.py`. Keep routes strictly focused on HTTP transport and view logic; defer complex domain logic to `app/services/`.

## 2. Python Coding Standards (PEP 8)
- **Formatting:** Strictly adhere to PEP 8 conventions. Use 4 spaces for indentation, limit line length where practical, and use standard Python casing (`snake_case` for variables/functions, `PascalCase` for classes, `UPPER_CASE` for constants).
- **Type Hinting:** Modern Python (`3.10+`) type hints (`-> dict`, `: list[str]`, etc.) must be aggressively used across all service layers, helper methods, and internal logic to provide static analysis tracking.
- **Documentation:** All functions, methods, and classes must include clear docstrings. Detail expected parameters, payload types, and return values.

## 3. Configuration vs. Runtime Separation
- **Config-Driven Pattern:** Never hardcode form options, validation constraints, or logic routing rules inside Python scripts. BankPFT isolates core structural rules into JSON binaries (`app/config/upload_config.json`, `rule_config.json`, `allocation_config.json`).
- **Database Scope:** The database (`app/models/`) is strictly responsible for *runtime state* (e.g. tracking what a user uploaded, saving what values were parsed). *How* things are parsed belongs to JSON.

## 4. Models and Database (SQLAlchemy & PostgreSQL)
- **Database Engine:** The platform is exclusively built around **PostgreSQL**. Do not optimize for SQLite idiosyncrasies or generic ORM defaults when PostgreSQL-specific features provide more power.
- **Stored Procedure Mandate:** The core rule engine and any heavy allocations or business logic MUST be implemented as **PostgreSQL Stored Procedures**. Do NOT build intensive data-processing loops inside Python (e.g. Pandas merges) where database-level execution is natively superior. Let Python be the orchestrator, and PostgreSQL be the engine.
- **Dynamic Configuration (JSONB):** When modeling dynamic rule configurations or loose metadata, natively utilize PostgreSQL's `JSONB` data type (via `sqlalchemy.dialects.postgresql.JSONB`). Do NOT build complex Entity-Attribute-Value (EAV) relational models when a JSON payload fulfills the need.
- **Declarative Base & Mixins:** New models must inherit from `db.Model`. Aggressively utilize existing mixins located in `app/models/mixins.py` (e.g., `MakerCheckerMixin`, `TimestampMixin`) to standardize status properties, creation traces, and group access controls.
- **Data Integrity:** Provide clear, explicit primary keys and relationships (`db.relationship`, `db.ForeignKey`). Ensure nullable flags map accurately to core application logic. 

## 5. View Modals & Templates (Jinja2)
- **Base Extension:** All `.html` files must use `{% extends "layout/base.html" %}`.
- **Local Bootstrap Sourcing:** The frontend heavily utilizes Bootstrap 5. All Bootstrap CSS and JS assets **must be sourced locally** from the internal static folder (`app/static/css/`, `app/static/js/`). Do not inject external CDN links (e.g. `cdn.jsdelivr.net`) inside Jinja templates.
- **Styling constraints:** Rely 100% on standard bootstrap utility classes (`d-flex`, `mt-4`, etc.). Limit vanilla CSS logic where bootstrap utilities can fulfill the goal. Do not use raw JavaScript where standard Flask WTF/form validation checks can occur.

## 6. Execution Lifecycle
When building or touching system pipelines that touch Data Loaders or allocation orchestration:
- Defer batch tracking to `app.models.workflow.BatchRun` and `BatchExecution`.
- Throw handled exceptions. Do not catch generic broad exceptions (`except Exception: pass`). Use system-wide routing validation arrays and Flash messaging (`flash()`) to visually render failures using Bootstrap Alert/Error Grids.

---

## Appendix A: Project Reference Model
The application codebase adheres strictly to the following directory layout. If introducing new logic, place files strictly within their respective domains:

```text
app/
├── __init__.py              # App factory
├── config/                  # Configuration JSON files managing rules and formatting
├── core/                    # Low-level utilities (logging, filtering, time_utils)
├── models/                  # SQLAlchemy ORM (auth, staging, allocation, ftp, workflow)
├── routes/                  # Flask UI blueprints and endpoints
├── services/                # Business logic engines (upload, allocation, testdata)
└── templates/               # Jinja2 / Bootstrap HTML fragments

db/                          # Holds raw .sql PostgreSQL schema definitions
docs/                        # Contains supplemental architectural documents
tests/                       # Pytest unit and integration arrays
```
