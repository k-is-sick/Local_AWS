import os
import json
import re

ROOT = "dynamodb_data"
os.makedirs(ROOT, exist_ok=True)


def sanitize_table_name(table: str) -> str:
    # Allow alphanumeric, hyphens, and underscores only
    return re.sub(r"[^a-zA-Z0-9_\-]", "", table)


def table_path(table: str) -> str:
    safe_name = sanitize_table_name(table)
    return os.path.join(ROOT, f"{safe_name}.json")


def list_tables() -> list[str]:
    if not os.path.exists(ROOT):
        return []
    tables = []
    for f in os.listdir(ROOT):
        if f.endswith(".json"):
            tables.append(f[:-5])
    return sorted(tables)


def load_table(table: str) -> dict | None:
    path = table_path(table)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_table(table: str, data: dict) -> None:
    path = table_path(table)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)


def delete_table(table: str) -> bool:
    path = table_path(table)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False