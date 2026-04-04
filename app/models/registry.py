"""JSON-driven model registry.

All table-name → SQLAlchemy model mappings are declared in
``app/config/model_registry.json``.  This module reads that file once at
import time and exposes three ready-to-use registries:

    MODEL_REGISTRY          dict[str, type]
        Maps every table name to its SQLAlchemy model class.
        Used by allocation_engine, datafile_service, and upload_service.

    DIMENSION_REGISTRY      dict[str, tuple[type, str]]
        Subset of MODEL_REGISTRY for dimension tables only.
        Each value is (ModelClass, primary_key_column_name).
        Used by upload_service for dimension-lookup validation.

    UPLOAD_PREVIEW_REGISTRY dict[str, tuple[type, list[str]]]
        Maps upload data-type strings (INSTRUMENT, GL, …) to
        (ModelClass, extra_preview_columns).
        Used by routes/upload.py to render staged-data previews.

To register a new model, add one entry to model_registry.json — no Python
changes required.
"""

from __future__ import annotations

import importlib
import json
import os

_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "model_registry.json")


def _build_registries() -> tuple[
    dict[str, type],
    dict[str, tuple[type, str]],
    dict[str, tuple[type, list[str]]],
]:
    with open(_JSON_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)

    model_registry: dict[str, type] = {}
    dimension_registry: dict[str, tuple[type, str]] = {}

    for table_name, meta in cfg["tables"].items():
        mod = importlib.import_module(meta["module"])
        cls = getattr(mod, meta["class"])
        model_registry[table_name] = cls
        if "key_column" in meta:
            dimension_registry[table_name] = (cls, meta["key_column"])

    upload_preview_registry: dict[str, tuple[type, list[str]]] = {}
    for data_type, preview_meta in cfg.get("upload_preview", {}).items():
        table = preview_meta["table"]
        cls = model_registry[table]
        extra_cols = preview_meta.get("extra_cols", [])
        upload_preview_registry[data_type] = (cls, extra_cols)

    return model_registry, dimension_registry, upload_preview_registry


MODEL_REGISTRY, DIMENSION_REGISTRY, UPLOAD_PREVIEW_REGISTRY = _build_registries()
