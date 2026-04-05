# BankPFT — Refactoring Design Document

**Date:** 2026-04-04  
**Status:** Complete — All 7 Phases Done  
**Scope:** `app/services/`, `app/models/`, `app/routes/`, `app/config/`

### Implementation Progress

| Phase | Title | Status | Commit |
|---|---|---|---|
| 1 | JSON-Driven Model Registry | ✅ Complete | `babbc69` |
| 2 | Config Loader → `app/core/config_loader.py` | ✅ Complete | `2e378ec` |
| 3 | Shared Filter Engine → `app/core/filter_engine.py` | ✅ Complete | `17642e6` |
| 4 | DateTime Modernisation → `app/core/time_utils.py` | ✅ Complete | `7d84146` |
| 5 | Model Mixins → `app/models/mixins.py` | ✅ Complete | `1d010ed` |
| 6 | Shared BatchLogger → `app/core/batch_logger.py` | ✅ Complete | `da8e52a` |
| 7 | Value-Cast Documentation | ✅ Complete | `2595b9a` |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Inventory](#2-current-architecture-inventory)
3. [Issues Found](#3-issues-found)
   - 3.1 Triplicated Model Registries
   - 3.2 Repeated Config-Loading Boilerplate
   - 3.3 Parallel Filter Implementations
   - 3.4 `datetime.utcnow()` Deprecation
   - 3.5 Maker/Checker Columns Not Shared via Mixin
   - 3.6 `_BatchLogger` Isolated in One Engine
   - 3.7 Value-Casting Overlap Between Services
4. [Proposed Module Structure](#4-proposed-module-structure)
5. [Change Details](#5-change-details)
   - Phase 1 — Model Registry
   - Phase 2 — Config Loader
   - Phase 3 — Filter Engine
   - Phase 4 — DateTime Modernisation
   - Phase 5 — Model Mixins
   - Phase 6 — Shared BatchLogger
   - Phase 7 — Value-Cast Consolidation
6. [Migration Rules](#6-migration-rules)
7. [Test Strategy](#7-test-strategy)
8. [Out of Scope](#8-out-of-scope)

---

## 1. Executive Summary

The codebase has grown organically through several feature additions (upload, allocation, FTP, data-file import/export, multi-task batch). Each new service was written in isolation, producing three classes of problems that this document addresses:

| Problem class | Files affected | Risk level |
|---|---|---|
| ~~Three separate table→model registry dicts~~ ✅ **Fixed** | `app/config/model_registry.json`, `app/models/registry.py` | Resolved — single JSON file is now the only place to add a model |
| Config-loading boilerplate repeated 6 times | 5 service and route files | Low — functional, but increasing maintenance cost |
| Two independent filter-engine implementations | `allocation_engine`, `datafile_service` | Medium — bug fixes must be applied twice |
| `datetime.utcnow()` deprecated in Python 3.12+ | All service files + all model defaults | Low now, breaking in future Python releases |
| Maker/Checker audit columns declared 5 times | `allocation.py`, `workflow.py` models | Low — no bugs, just repeated boilerplate |
| `_BatchLogger` private to `allocation_engine` | Future re-use blocked | Low — risk if pattern expands |
| Overlapping value-cast helpers | `upload_service`, `datafile_service` | Low — different requirements, but worth documenting |

**Goal:** Introduce shared infrastructure modules so each concern is defined once and imported everywhere. No user-visible behaviour changes. Tests must pass at every phase boundary.

---

## 2. Current Architecture Inventory

### Service Layer

```
app/services/
├── __init__.py            # Maker/Checker state machine (WorkflowError, transition)
├── allocation_engine.py   # run_allocation() — core allocation shredding
├── batch_executor.py      # run_batch()  — multi-task batch orchestrator
├── datafile_service.py    # import_file() / export_data() — fixed & delimited file I/O
├── ftp_engine.py          # run_ftp() — Fund Transfer Pricing MOVING_AVG engine
├── testdata_service.py    # test-data generation helpers
├── test_runner.py         # in-app test suite runner
└── upload_service.py      # process_upload() / validate_upload() — file upload pipeline
```

### Model Layer

```
app/models/
├── __init__.py            # db = SQLAlchemy()
├── allocation.py          # RefStaticAllocation, RefOrgReclass, RefStaticDistribution, RefStaticAlloc,
│                          # FctMgmtLedger, FctMgmtInstrument
├── auth.py                # User, Group
├── datafile.py            # DataFileBatch
├── dimensions.py          # DimCustomer, DimProduct, DimOrgUnit, DimAccount
├── ftp.py                 # RefInterestRate, FtpProductConfig, FtpRun
├── staging.py             # StgInstData, StgGlData, ProcInstData, ProcGlData
├── test_run.py            # TestSuiteRun, TestCaseResult
└── workflow.py            # AllocationRule, BatchRun, BatchDefinition, BatchExecution,
                           # BatchExecutionStep, UploadBatch
```

### Config Layer

```
app/config/
├── allocation_config.json  # source/lookup/output column lists, join type, orphan handling
├── datafile_config.json    # global datafile settings (inbox/outbox paths)
├── filter_config.json      # available filter operators for UI
├── rule_config.json        # source/lookup/output table options for rule form dropdowns
├── upload_config.json      # data-type definitions: column mapping, staging table, validation rules
├── validation_rules.json   # reusable validation rule descriptors
└── datafile/               # one JSON per import/export format (14 files)
```

---

## 3. Issues Found

### 3.1 Triplicated Model Registries

**Three separate `dict[str, type]` mappings** exist across the codebase, all mapping the same table name strings to the same SQLAlchemy model classes:

#### `allocation_engine.py` — three dicts

```python
_SOURCE_MODELS = {
    "proc_inst_data": ProcInstData,
    "proc_gl_data": ProcGlData,
}
_LOOKUP_MODELS = {
    "ref_static_allocation":    RefStaticAllocation,
    "ref_org_reclass":          RefOrgReclass,
    "ref_static_distribution":  RefStaticDistribution,
    "ref_static_alloc":         RefStaticAlloc,
}
_OUTPUT_MODELS = {
    "fct_mgmt_ledger":      FctMgmtLedger,
    "fct_mgmt_instrument":  FctMgmtInstrument,
}
```

#### `upload_service.py`

```python
_STAGING_MODELS = {
    "stg_inst_data":            StgInstData,
    "stg_gl_data":              StgGlData,
    "ref_static_allocation":    RefStaticAllocation,
    "ref_org_reclass":          RefOrgReclass,
    "ref_static_distribution":  RefStaticDistribution,
    "ref_static_alloc":         RefStaticAlloc,
    "ref_interest_rate":        RefInterestRate,
}
```

#### `datafile_service.py`

```python
_TABLE_MODELS = {
    "stg_inst_data":          StgInstData,
    "stg_gl_data":            StgGlData,
    "proc_inst_data":         ProcInstData,
    "proc_gl_data":           ProcGlData,
    "ref_static_allocation":  RefStaticAllocation,
    "fct_mgmt_ledger":        FctMgmtLedger,
    "fct_mgmt_instrument":    FctMgmtInstrument,
}
```

#### `routes/upload.py` (inline local dict)

```python
_PREVIEW_MODELS = {
    "INSTRUMENT":    (StgInstData, []),
    "GL":            (StgGlData, []),
    "ALLOCATION":    (RefStaticAllocation, ["status"]),
    "ORG_RECLASS":   (RefOrgReclass, ["status"]),
    "INTEREST_RATE": (RefInterestRate, ["status"]),
}
```

**Impact:** Every time a new model is added, the developer must update 3–4 separate files. A missed entry causes a silent `None`-lookup that produces a misleading error at runtime.

---

### 3.2 Repeated Config-Loading Boilerplate

The same six-line pattern is repeated in every file that needs a config:

```python
_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "allocation_config.json")
with open(_CFG_PATH) as _f:
    ALLOC_CONFIG = json.load(_f)
```

Files using this pattern and their config files:

| File | Config file(s) loaded |
|---|---|
| `services/allocation_engine.py` | `allocation_config.json` |
| `services/upload_service.py` | `upload_config.json`, `validation_rules.json` |
| `services/datafile_service.py` | `datafile_config.json` + all `datafile/*.json` |
| `routes/rules.py` | `rule_config.json`, `filter_config.json` |

**Impact:** The relative `../config` path is fragile to directory restructuring. Loading at module scope causes an `FileNotFoundError` during testing if configs aren't present. Each file must manage its own path calculation independently.

---

### 3.3 Parallel Filter Implementations

Two independent implementations of the same filtering concept exist:

#### `allocation_engine.py` — `_apply_filters(df, filter_json)`

- Input: **pandas DataFrame** + filter JSON string
- Deserialises filter JSON internally
- Supports: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`, `in`, `not_in`, `contains`, `starts_with`
- Supports AND/OR logic

#### `datafile_service.py` — `_apply_export_filters(rows, filter_cfg)`

- Input: **list of SQLAlchemy model instances** + already-parsed filter dict
- Supports: `eq`, `neq`, `in`, `not_in`, `contains`, `gt`, `gte`, `lt`, `lte`
- Supports AND/OR logic

Both dispatch the same operator set with identical semantics. The `between` and `starts_with` operators exist only in the pandas variant. Any operator fix or addition must be applied to both.

---

### 3.4 `datetime.utcnow()` Deprecation

`datetime.utcnow()` was deprecated in Python 3.12 and is scheduled for removal. It returns a naive datetime (no timezone info), which is inconsistent for a banking application.

**Call-site count by file:**

| File | Call sites |
|---|---|
| `services/allocation_engine.py` | 6 (incl. `_BatchLogger`) |
| `services/ftp_engine.py` | 3 |
| `services/batch_executor.py` | 4 |
| `services/datafile_service.py` | 6 |
| `services/test_runner.py` | 3 |

**Model defaults** — all model files use `default=datetime.utcnow` as column defaults:
- `models/workflow.py` — `UploadBatch`, `AllocationRule`, `BatchRun`, `BatchDefinition`
- `models/allocation.py` — `RefStaticAllocation`, `RefOrgReclass`, `RefStaticDistribution`, `RefStaticAlloc`
- `models/ftp.py` — `RefInterestRate`, `FtpProductConfig`, `FtpRun`
- `models/datafile.py` — `DataFileBatch`
- `models/test_run.py` — `TestSuiteRun`, `TestCaseResult`

**Total deprecated call sites:** ~35

---

### 3.5 Maker/Checker Columns Not Shared via Mixin

All four reference tables in `allocation.py` and `UploadBatch` in `workflow.py` share the same six audit columns:

```python
status      = db.Column(db.String(20), default="DRAFT")
maker_id    = db.Column(db.String(50), nullable=False)
checker_id  = db.Column(db.String(50), nullable=True)
created_at  = db.Column(db.DateTime, default=datetime.utcnow)
updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
comments    = db.Column(db.Text, nullable=True)
```

These are declared independently five times. If column widths or defaults need changing, five files require updates.

---

### 3.6 `_BatchLogger` Isolated in `allocation_engine`

`_BatchLogger` is a private class inside `allocation_engine.py`:

```python
class _BatchLogger:
    def __init__(self, batch_id: str): ...
    def log(self, level: str, message: str): ...
    def close(self): ...
```

It writes structured per-batch `.log` files to `instance/batch_logs/`. The `ftp_engine.py` and `batch_executor.py` do not use it — FTP run errors are stored only in the DB `error_message` field. If file-based logging is wanted for those engines, a copy-paste of `_BatchLogger` would be the path of least resistance.

---

### 3.7 Value-Casting Overlap Between Services

Two type-coercion helpers coexist with overlapping responsibilities:

#### `upload_service.py` — `_cast_value(value, col_cfg)`

- Used for Excel/CSV cell values from pandas DataFrame rows
- Handles: `date`, `integer`, `float`, `string`
- Supports `default` for missing values
- No transform expressions

#### `datafile_service.py` — `_coerce(raw: str, field_cfg: dict)`

- Used for raw text fields from fixed-width / delimited files
- Handles: `date`, `int`, `float`, `string`
- Supports `transform` expressions via `_safe_eval`
- No `default` for missing values (caller handles that)

These are **intentionally different** in scope—upload deals with typed DataFrame values while datafile handles raw strings with transforms. They should remain separate but the overlap should be documented so future developers don't merge them incorrectly.

---

## 4. Proposed Module Structure

The following new files resolve the issues above. All existing files remain in place and are updated to import from the new modules.

A `core/` package is introduced as the **pure infrastructure layer** — utilities with no business-domain knowledge. The rule is strict: `core/` modules may only import from the Python standard library and `app/models/__init__.py` (for the `db` object). They must never import from `app/services/` or `app/routes/`. This makes the layer safe to reuse across any future entry point (REST API, CLI, background worker).

`models/mixins.py` intentionally stays in `models/` rather than `core/` because SQLAlchemy mixins _are_ ORM model definitions — moving them to `core/` would create a circular dependency risk.

```
app/
├── core/                        ← NEW — pure infrastructure, zero domain knowledge
│   ├── __init__.py
│   ├── config_loader.py         # Phase 2 — load_config(name)
│   ├── filter_engine.py         # Phase 3 — apply_df_filters(), apply_row_filters()
│   ├── batch_logger.py          # Phase 6 — BatchLogger class
│   └── time_utils.py            # Phase 4 — utc_now() helper
│
├── models/
│   ├── mixins.py                # Phase 5 — MakerCheckerMixin, TimestampMixin (stays in models/)
│   ├── registry.py              # ✅ DONE (Phase 1)
│   └── ...existing files, updated to use mixins...
│
├── services/                    ← business logic only; imports from core/ and models/
│   └── ...existing files unchanged except import updates...
│
└── config/
    ├── model_registry.json      # ✅ DONE (Phase 1)
    └── ...existing json files unchanged...
```

### Dependency Flow (after refactoring)

```
                        ┌─────────────────────────┐
                        │        app/core/         │  ← imports: stdlib only
                        │  config_loader.py        │     + app.models.db (for mixins: NO)
                        │  filter_engine.py        │
                        │  batch_logger.py         │
                        │  time_utils.py           │
                        └────────────┬────────────┘
                                     │ imported by
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     app/models/               app/services/          app/routes/
     mixins.py                 allocation_engine      rules.py
     registry.py               ftp_engine             upload.py
                               batch_executor
                               upload_service
                               datafile_service
```

**The «no upward imports» rule:** `core/` never imports from `services/` or `routes/`. `models/` never imports from `services/` or `routes/`. Violations should be caught in code review.

---

## 5. Change Details

---

### Phase 1 — JSON-Driven Model Registry ✅ COMPLETE (commit `babbc69`)

**Status:** Implemented and pushed. 123 tests passing.

**Actual implementation** improved on the original proposal by making the registry fully JSON-driven:

- `app/config/model_registry.json` — declares all 15 table entries; `key_column` marks dimension tables; `upload_preview` section replaces the route-level inline dict
- `app/models/registry.py` — reads JSON at startup via `importlib.import_module`, exposes `MODEL_REGISTRY`, `DIMENSION_REGISTRY`, `UPLOAD_PREVIEW_REGISTRY`

**Lines of code removed across 4 files:** ~45 lines of duplicate dict declarations + 9 model import lines

**How to add a new model (after this change):**
```json
// app/config/model_registry.json — the only file to edit
{
  "tables": {
    "new_table_name": { "module": "app.models.new_module", "class": "NewModelClass" }
  }
}
```
No Python file changes required.

---

### Phase 2 — Config Loader (`app/core/config_loader.py`)

**Problem:** Every file that needs a JSON config computes the same relative path and calls `open` / `json.load` directly.

**Solution:** A single `load_config(name)` function in `app/core/config_loader.py` that resolves paths from the canonical config directory at import time. Placing it in `core/` signals that it is pure infrastructure with no domain knowledge.

```python
# app/core/config_loader.py
"""Centralised JSON config loader.

Usage:
    from app.core.config_loader import load_config
    ALLOC_CONFIG = load_config("allocation_config")
    UPLOAD_CONFIG = load_config("upload_config")
    FILTER_CFG = load_config("filter_config")
"""
import json
import os

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def load_config(name: str) -> dict:
    """Load and return a JSON config by base name (without .json extension).

    Searches app/config/ first, then app/config/datafile/.
    Raises FileNotFoundError if config does not exist.
    """
    for search_dir in (_CONFIG_DIR, os.path.join(_CONFIG_DIR, "datafile")):
        path = os.path.join(search_dir, f"{name}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    raise FileNotFoundError(f"Config '{name}.json' not found in {_CONFIG_DIR}")
```

**Files to update:**

| File | Old code | New code |
|---|---|---|
| `allocation_engine.py` | 3-line open block | `ALLOC_CONFIG = load_config("allocation_config")` |
| `upload_service.py` | 6-line open block (2 files) | 2 × `load_config(...)` |
| `datafile_service.py` | 3-line open block + glob loop | `load_config("datafile_config")` + `load_config(fmt_id)` |
| `routes/rules.py` | 6-line open block (2 files) | 2 × `load_config(...)` |

---

### Phase 3 — Filter Engine (`app/core/filter_engine.py`)

**Problem:** Two files implement the same condition-matching logic independently, with minor surface differences.

**Solution:** Extract the shared logic to `app/core/filter_engine.py` with two entry points. It lives in `core/` because it has no knowledge of any specific domain table, rule, or business concept — it is a pure data-filtering utility.

- `apply_df_filters(df, filter_json)` — for pandas DataFrames (allocation engine)
- `apply_row_filters(rows, filter_cfg)` — for SQLAlchemy model instances (datafile export)

```python
# app/core/filter_engine.py
"""Shared filter engine for condition-based data selection.

Two entry points:
  apply_df_filters(df, filter_json)  → pandas DataFrame filtering (str input)
  apply_row_filters(rows, filter_cfg) → SQLAlchemy row-list filtering (dict input)

Both implement the same operator set:
  eq, neq, gt, gte, lt, lte, between, in, not_in, contains, starts_with
"""
import json
import pandas as pd

_OPS_DF = {"eq", "neq", "gt", "gte", "lt", "lte", "between", "in", "not_in", "contains", "starts_with"}
_OPS_ROW = _OPS_DF - {"between", "starts_with"}   # row filter subset currently implemented


def apply_df_filters(df: pd.DataFrame, filter_json: str | None) -> pd.DataFrame:
    """Apply filter_json conditions to a pandas DataFrame.  Returns filtered copy."""
    ...  # implementation moved verbatim from allocation_engine._apply_filters


def apply_row_filters(rows: list, filter_cfg: dict) -> list:
    """Apply filter_cfg conditions to a list of SQLAlchemy model instances."""
    ...  # implementation moved verbatim from datafile_service._apply_export_filters
         # + add missing between / starts_with operators for parity
```

**Files to update:**

| File | Function to remove | Import to add |
|---|---|---|
| `allocation_engine.py` | `_apply_filters()` | `from app.core.filter_engine import apply_df_filters` |
| `datafile_service.py` | `_apply_export_filters()` | `from app.core.filter_engine import apply_row_filters` |

**Tests:** The existing `tests/test_rules.py` imports `_apply_filters` directly from `allocation_engine`. After Phase 3, the import path changes:

```python
# Before
from app.services.allocation_engine import _apply_filters

# After
from app.core.filter_engine import apply_df_filters as _apply_filters
```

---

### Phase 4 — DateTime Modernisation (`app/core/time_utils.py`)

**Problem:** `datetime.utcnow()` is deprecated in Python 3.12+ and returns naive datetimes.

**Solution:** Introduce `app/core/time_utils.py` with a single `utc_now()` function, then replace all call sites. Centralising this in `core/` means a future timezone-strategy change (e.g. switching to a timezone-aware store) is a one-file edit.

```python
# app/core/time_utils.py
"""Timezone-safe datetime utilities.

Usage:
    from app.core.time_utils import utc_now
    started_at = utc_now()
    created_at = db.Column(db.DateTime, default=utc_now)
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
```

All model column defaults change from `default=datetime.utcnow` to `default=utc_now` (the function reference works directly as a SQLAlchemy default callable — no lambda wrapper needed).

All service call sites change from `datetime.utcnow()` to `utc_now()`.

**Files to update:** All 5 service files + all 7 model files listed in §3.4.

---

### Phase 5 — Model Mixins (`app/models/mixins.py`)

**Problem:** Audit columns are repeated in 5 model definitions.

**Solution:** Two SQLAlchemy declaration-level mixins:

```python
# app/models/mixins.py
from datetime import datetime, timezone
from app.models import db


def _utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at and updated_at columns."""
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class MakerCheckerMixin(TimestampMixin):
    """Adds full Maker/Checker audit trail columns."""
    status     = db.Column(db.String(20), default="DRAFT")  # DRAFT→PENDING→APPROVED/REJECTED
    maker_id   = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
    comments   = db.Column(db.Text, nullable=True)
```

**Models to update:**

| Model | Mixin to apply | Columns removed from model |
|---|---|---|
| `RefStaticAllocation` | `MakerCheckerMixin` | status, maker_id, checker_id, created_at, updated_at, comments |
| `RefOrgReclass` | `MakerCheckerMixin` | same 6 |
| `RefStaticDistribution` | `MakerCheckerMixin` | same 6 |
| `RefStaticAlloc` | `MakerCheckerMixin` | same 6 |
| `UploadBatch` | `MakerCheckerMixin` | same 6 (+ maker_comment, checker_comment stay as-is) |
| `AllocationRule` | `TimestampMixin` | created_at, updated_at |
| `BatchRun` | `TimestampMixin` | started_at removed (keep, different semantics) |
| `FtpRun` | `TimestampMixin` | started_at removed (keep) |

**Database impact:** Mixin columns map to the same table columns (SQLAlchemy infers column names from attribute names). No schema migration is needed — this is a Python-layer-only change.

---

### Phase 6 — Shared BatchLogger (`app/core/batch_logger.py`)

**Problem:** `_BatchLogger` is a private class inside `allocation_engine.py` and cannot be reused by other engines without import-coupling.

**Solution:** Move the class to `app/core/batch_logger.py`. It belongs in `core/` because it is pure I/O infrastructure — it writes `.log` files and knows nothing about allocations, FTP, or any other business concept.

```python
# app/core/batch_logger.py
"""File-based structured batch logger.

Writes human-readable .log files to instance/batch_logs/<batch_id>.log.

Usage:
    from app.core.batch_logger import BatchLogger
    logger = BatchLogger(batch_id)
    logger.log("START", "Batch initiated by user_x")
    logger.close()
"""
import os
from app.core.time_utils import utc_now


class BatchLogger:
    def __init__(self, batch_id: str, log_dir: str | None = None):
        ...  # implementation moved verbatim from allocation_engine._BatchLogger

    def log(self, level: str, message: str) -> None:
        ...

    def close(self) -> None:
        ...
```

**Files to update:**

| File | Change |
|---|---|
| `allocation_engine.py` | Remove `_BatchLogger`; replace with `from app.core.batch_logger import BatchLogger` |
| `ftp_engine.py` | (Optional Phase 6b) Add `BatchLogger` for FTP run file logging |
| `batch_executor.py` | (Optional Phase 6b) Add `BatchLogger` for multi-task execution logging |

---

### Phase 7 — Value-Cast Documentation (No Code Change)

As documented in §3.7, `_cast_value` (upload_service) and `_coerce` (datafile_service) serve different purposes and should remain separate. They handle different input types (typed DataFrame cell vs raw string) and have different feature sets (default-handling vs transform expressions).

**Action:** Add a docstring comment to each function cross-referencing the other, so future developers understand the design intent and do not accidentally merge them.

---

## 6. Migration Rules

The following constraints must be observed throughout all phases:

1. **One phase at a time.** Each phase must leave the test suite green before the next phase begins. Do not batch multiple phases into a single commit.

2. **Backward-compatible imports.** If a function is moved (e.g. `_apply_filters` to `core/filter_engine.py`), add a re-export in the original file until all tests are updated:
   ```python
   # allocation_engine.py — temporary compatibility shim
   from app.core.filter_engine import apply_df_filters as _apply_filters  # noqa: F401
   ```

3. **No public API changes.** The signatures of `run_allocation`, `run_ftp`, `run_batch`, `process_upload`, `import_file`, and `export_data` must not change.

4. **Configuration files unchanged.** No JSON config file content is modified as part of this refactoring. Config file names remain the same; only the Python code that loads them changes.

5. **Schema migrations not required.** Mixin columns (Phase 5) use the same attribute names as the current model columns; SQLAlchemy maps them to the same table columns. No `ALTER TABLE` or migration script is needed.

6. **Test import paths update with Phase 3.** The test file `tests/test_rules.py` imports `_apply_filters` from `allocation_engine` directly. This import must be updated when Phase 3 is complete.

---

## 7. Test Strategy

All 123 existing tests must pass at every phase boundary. No new tests are strictly required for the refactoring itself (behaviour is unchanged), though the following additions are recommended:

| Phase | Recommended test |
|---|---|
| Phase 1 | `test_registry.py` — assert every expected table name resolves to a non-None model class |
| Phase 2 | `test_config_loader.py` — assert `load_config("allocation_config")` returns a dict; assert FileNotFoundError for unknown name |
| Phase 3 | Update `test_rules.py` imports; verify all 6 filter operator tests still pass via `filter_engine` |
| Phase 4 | No new tests needed; verify no `DeprecationWarning` is emitted in test runs |
| Phase 5 | No new tests needed; existing model tests verify column presence |
| Phase 6 | `test_batch_logger.py` — assert log file created, log line format, close flushes |

---

## 8. Out of Scope

The following issues were noted during the review but are **not** addressed in this refactoring to keep the scope manageable:

- **Route-level duplication** (`routes/rules.py` import endpoint and `routes/api.py` import endpoint both parse AllocationRule JSON): these share business logic but sit in different layers. A service-level `parse_rule_dict(data)` helper could unify them, but that change touches the API contract and is better handled as a separate initiative.

- **`_safe_eval` in `datafile_service`**: The sandbox evaluator is self-contained and correct. No refactoring is needed.

- **`WorkflowError / transition`** in `services/__init__.py`: Works well and is already centralised. Leaving as-is.

- **Batch executor step dispatch** (`_run_step` in `batch_executor.py`): The if/elif chain that dispatches ALLOCATION / FTP / DATAFILE_IMPORT task types is clear and readable at its current size. Refactoring to a registry pattern is premature.

- **Template duplication**: Rule new/edit forms share HTML structure. Jinja2 template macros could reduce repetition, but this is a UI-layer concern outside the services/models scope of this document.

---

*End of Refactoring Design Document*
