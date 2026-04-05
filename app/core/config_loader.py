"""Centralised JSON config loader for ``app/config/``.

Usage::

    from app.core.config_loader import load_config

    ALLOC_CONFIG = load_config("allocation_config")
"""

import json
import os

_CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config"))


def load_config(name: str) -> dict:
    """Return the parsed JSON dict for ``app/config/{name}.json``.

    Parameters
    ----------
    name:
        Base name of the config file (without the ``.json`` suffix).

    Raises
    ------
    FileNotFoundError
        If ``app/config/{name}.json`` does not exist.
    """
    path = os.path.join(_CONFIG_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
