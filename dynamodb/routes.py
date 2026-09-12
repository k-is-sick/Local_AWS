import os
from flask import Blueprint, request, jsonify, session
from shared import require_permission, arn_dynamodb
from . import storage

dynamo_bp = Blueprint("dynamodb", __name__, url_prefix="/api/dynamodb")


@dynamo_bp.route("/tables", methods=["GET"])
@require_permission("dynamodb:ListTables", lambda r: arn_dynamodb("*"))
def list_tables():
    return jsonify({"tables": storage.list_tables()})


@dynamo_bp.route("/tables", methods=["POST"])
@require_permission("dynamodb:CreateTable", lambda r: arn_dynamodb(((r.get_json(silent=True) or {}).get("table_name") or "").strip()))
def create_table():
    body = request.get_json(silent=True) or {}
    name = (body.get("table_name") or "").strip()
    pk = (body.get("partition_key") or "").strip()
    sk = (body.get("sort_key") or "").strip() or None

    if not name or not pk:
        return jsonify({"error": "table_name and partition_key are required"}), 400

    if storage.load_table(name) is not None:
        return jsonify({"error": f"Table '{name}' already exists"}), 409

    storage.save_table(name, {
        "meta": {
            "partition_key": pk,
            "sort_key": sk
        },
        "items": {}
    })
    return jsonify({"ok": True, "table": name, "partition_key": pk, "sort_key": sk}), 201


@dynamo_bp.route("/tables/<table>", methods=["GET"])
@require_permission("dynamodb:DescribeTable", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def describe_table(table):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    return jsonify({
        "table": table,
        "meta": data.get("meta", {}),
        "count": len(data.get("items", {}))
    })


@dynamo_bp.route("/tables/<table>", methods=["DELETE"])
@require_permission("dynamodb:DeleteTable", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def delete_table(table):
    if not storage.delete_table(table):
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    return "", 204


@dynamo_bp.route("/tables/<table>/items", methods=["PUT"])
@require_permission("dynamodb:PutItem", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def put_item(table):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    item = request.get_json(silent=True)
    if not isinstance(item, dict):
        return jsonify({"error": "Invalid item payload: expected a JSON object"}), 400

    pk = data["meta"]["partition_key"]
    sk = data["meta"]["sort_key"]

    if pk not in item:
        return jsonify({"error": f"Missing required partition key field: '{pk}'"}), 400

    pk_val = str(item[pk])
    if sk:
        sk_val = str(item.get(sk, ""))
        key = f"{pk_val}#{sk_val}"
    else:
        key = pk_val

    data["items"][key] = item
    storage.save_table(table, data)
    return jsonify({"ok": True, "key": key})


@dynamo_bp.route("/tables/<table>/items/<path:key>", methods=["GET"])
@require_permission("dynamodb:GetItem", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def get_item(table, key):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    item = data["items"].get(key)
    if item is None:
        return jsonify({"error": f"Item with key '{key}' not found"}), 404
        
    return jsonify({"item": item})


@dynamo_bp.route("/tables/<table>/items/<path:key>", methods=["DELETE"])
@require_permission("dynamodb:DeleteItem", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def delete_item(table, key):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    if key not in data["items"]:
        return jsonify({"error": f"Item with key '{key}' not found"}), 404
        
    del data["items"][key]
    storage.save_table(table, data)
    return "", 204


@dynamo_bp.route("/tables/<table>/scan", methods=["GET"])
@require_permission("dynamodb:Scan", lambda r: arn_dynamodb(r.view_args.get("table", "*")))
def scan(table):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    items = list(data.get("items", {}).values())
    return jsonify({
        "table": table,
        "items": items,
        "count": len(items)
    })


@dynamo_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "dynamodb", "version": "1.0.0"})