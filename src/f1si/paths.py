"""Where f1si keeps its files. Nothing is created on import or by these functions."""

import os
from pathlib import Path


def data_dir() -> Path:
    """Folder holding the DuckDB cache (env `F1SI_DATA_DIR`, default `data`)."""
    return Path(os.environ.get("F1SI_DATA_DIR", "data"))


def db_path(data_dir: Path) -> Path:
    """The DuckDB file inside a data folder."""
    return data_dir / "f1si.duckdb"


def http_cache_dir(data_dir: Path) -> Path:
    """Folder for cached HTTP responses inside a data folder."""
    return data_dir / "http-cache"


def reports_dir() -> Path:
    """Folder for generated plots and reports (env `F1SI_REPORTS_DIR`, default `reports`)."""
    return Path(os.environ.get("F1SI_REPORTS_DIR", "reports"))
