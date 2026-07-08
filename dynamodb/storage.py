import os
import json

ROOT = "dynamodb_data"
os.makedirs(ROOT, exist_ok=True)


def table_path(table):
    return os.path.join(ROOT, f"{table}.json")


def list_tables():
    return [f.replace(".json", "") for f in os.listdir(ROOT) if f.endswith(".json")]


def load_table(table):
    path = table_path(table)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_table(table, data):
    with open(table_path(table), "w") as f:
        json.dump(data, f)


def delete_table(table):
    path = table_path(table)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False