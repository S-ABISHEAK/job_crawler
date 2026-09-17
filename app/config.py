"""Loads YAML config files from config/ so nothing is hardcoded."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DB_PATH = Path(__file__).resolve().parent.parent / "job_crawler.db"


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_companies() -> list[dict]:
    return _load_yaml("companies.yaml").get("companies", [])


@lru_cache
def get_sources() -> list[dict]:
    return _load_yaml("sources.yaml").get("sources", [])


@lru_cache
def get_keywords() -> dict:
    return _load_yaml("keywords.yaml")


@lru_cache
def get_scoring() -> dict:
    return _load_yaml("scoring.yaml")


def reload_config() -> None:
    """Clear cached config so edits to YAML take effect without a restart."""
    get_companies.cache_clear()
    get_sources.cache_clear()
    get_keywords.cache_clear()
    get_scoring.cache_clear()
