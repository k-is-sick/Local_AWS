from flask import Blueprint, request, jsonify, session
from . import storage

dynamo_bp = Blueprint("dynamodb", __name__, url_prefix="/api/dynamodb")


def logged_in():
    return session.get("user_email") is not None


@dynamo_bp.route("/tables", methods=["GET"])
def list_tables():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"tables": storage.list_tables()})


@dynamo_bp.route("/tables", methods=["POST"])
def create_table():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    body = request.get_json(force=True)
    name = body.get("table_name")
    pk = body.get("partition_key")
    sk = body.get("sort_key", None)
    if not name or not pk:
        return jsonify({"error": "table_name and partition_key required"}), 400
    if storage.load_table(name):
        return jsonify({"error": "Table already exists"}), 409
    storage.save_table(name, {
        "meta": {"partition_key": pk, "sort_key": sk},
        "items": {}
    })
    return jsonify({"ok": True, "table": name}), 201


@dynamo_bp.route("/tables/<table>", methods=["GET"])
def describe_table(table):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": "Table not found"}), 404
    return jsonify({"table": table, "meta": data["meta"], "count": len(data["items"])})


@dynamo_bp.route("/tables/<table>", methods=["DELETE"])
def delete_table(table):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    if not storage.delete_table(table):
        return jsonify({"error": "Table not found"}), 404
    return "", 204


@dynamo_bp.route("/tables/<table>/items", methods=["PUT"])
def put_item(table):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": "Table not found"}), 404
    item = request.get_json(force=True)
    pk = data["meta"]["partition_key"]
    sk = data["meta"]["sort_key"]
    if pk not in item:
        return jsonify({"error": f"Missing partition key: {pk}"}), 400
    key = item[pk] if not sk else f"{item[pk]}#{item.get(sk, '')}"
    data["items"][key] = item
    storage.save_table(table, data)
    return jsonify({"ok": True})


@dynamo_bp.route("/tables/<table>/items/<path:key>", methods=["GET"])
def get_item(table, key):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": "Table not found"}), 404
    item = data["items"].get(key)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    return jsonify({"item": item})


@dynamo_bp.route("/tables/<table>/items/<path:key>", methods=["DELETE"])
def delete_item(table, key):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": "Table not found"}), 404
    if key not in data["items"]:
        return jsonify({"error": "Item not found"}), 404
    del data["items"][key]
    storage.save_table(table, data)
    return "", 204


@dynamo_bp.route("/tables/<table>/scan", methods=["GET"])
def scan(table):
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": "Table not found"}), 404
    return jsonify({"items": list(data["items"].values()), "count": len(data["items"])})