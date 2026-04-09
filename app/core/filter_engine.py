"""Shared filter engine used by allocation and data-file services.

Two entry points
----------------
``apply_df_filters(df, filter_json)``
    Applies a JSON filter string to a *pandas DataFrame* and returns the
    filtered frame.  Used by the batch allocation engine.

``apply_row_filters(rows, filter_cfg)``
    Applies a pre-parsed filter dict to a *list of SQLAlchemy model
    instances* and returns the filtered list.  Used by the data-file
    export service.
"""

import json

import pandas as pd


def apply_df_filters(df: pd.DataFrame, filter_json: str | dict | None) -> pd.DataFrame:
    """Apply user-defined filter conditions (stored as JSON/dict) to a DataFrame."""
    if not filter_json:
        return df
    if isinstance(filter_json, dict):
        filt = filter_json
    else:
        try:
            filt = json.loads(filter_json)
        except (json.JSONDecodeError, TypeError):
            return df

    conditions = filt.get("conditions", [])
    if not conditions:
        return df

    logic = filt.get("logic", "AND")
    masks = []

    for cond in conditions:
        col = cond.get("field")
        op  = cond.get("operator")
        val = cond.get("value", "")
        if not col or not op or col not in df.columns:
            continue

        series = df[col]

        if op == "eq":
            m = series.astype(str) == val
        elif op == "neq":
            m = series.astype(str) != val
        elif op == "gt":
            m = pd.to_numeric(series, errors="coerce") > float(val)
        elif op == "gte":
            m = pd.to_numeric(series, errors="coerce") >= float(val)
        elif op == "lt":
            m = pd.to_numeric(series, errors="coerce") < float(val)
        elif op == "lte":
            m = pd.to_numeric(series, errors="coerce") <= float(val)
        elif op == "between":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) == 2:
                num = pd.to_numeric(series, errors="coerce")
                m = (num >= float(parts[0])) & (num <= float(parts[1]))
            else:
                continue
        elif op == "in":
            vals = {v.strip() for v in val.split(",")}
            m = series.astype(str).isin(vals)
        elif op == "not_in":
            vals = {v.strip() for v in val.split(",")}
            m = ~series.astype(str).isin(vals)
        elif op == "contains":
            m = series.astype(str).str.contains(val, case=False, na=False)
        elif op == "starts_with":
            m = series.astype(str).str.startswith(val, na=False)
        else:
            continue

        masks.append(m)

    if not masks:
        return df

    if logic == "OR":
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
    else:
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m

    return df[combined].reset_index(drop=True)


def apply_row_filters(rows: list, filter_cfg: dict) -> list:
    """Apply filter_json conditions to a list of SQLAlchemy model instances."""
    conditions = filter_cfg.get("conditions", [])
    if not conditions:
        return rows
    logic = filter_cfg.get("logic", "AND")

    def _matches(row) -> bool:
        results = []
        for c in conditions:
            col, op, val = c.get("field"), c.get("operator"), str(c.get("value", ""))
            attr = str(getattr(row, col, "")) if col else ""
            if op == "eq":
                results.append(attr == val)
            elif op == "neq":
                results.append(attr != val)
            elif op == "in":
                results.append(attr in {v.strip() for v in val.split(",")})
            elif op == "not_in":
                results.append(attr not in {v.strip() for v in val.split(",")})
            elif op == "contains":
                results.append(val.lower() in attr.lower())
            elif op == "gt":
                results.append(float(attr) > float(val))
            elif op == "gte":
                results.append(float(attr) >= float(val))
            elif op == "lt":
                results.append(float(attr) < float(val))
            elif op == "lte":
                results.append(float(attr) <= float(val))
            else:
                results.append(True)
        return all(results) if logic == "AND" else any(results)

    return [r for r in rows if _matches(r)]
