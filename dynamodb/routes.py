import os
from functools import wraps
import requests
from flask import Blueprint, request, jsonify, session
from . import storage

dynamo_bp = Blueprint("dynamodb", __name__, url_prefix="/api/dynamodb")


def get_iam_url():
    return os.environ.get("IAM_URL", "http://miniiam:4568")


def call_iam_authorize(access_key_id, secret_key, action, resource):
    urls = [get_iam_url(), "http://localhost:4568", "http://127.0.0.1:4568"]
    for url in urls:
        try:
            resp = requests.post(
                f"{url}/api/iam/authorize",
                json={
                    "access_key_id": access_key_id,
                    "secret_key": secret_key,
                    "action": action,
                    "resource": resource,
                },
                timeout=3,
            )
            return resp.json()
        except requests.RequestException:
            continue
    return None


def require_permission(action, resource_fn=None):
    """
    Integrates IAM policy authorization with web session support:
    - If X-Access-Key-Id / X-Secret-Key headers are present, evaluates against IAM service.
    - Otherwise, falls back to session-based cookie authentication.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            akid = request.headers.get("X-Access-Key-Id")
            secret = request.headers.get("X-Secret-Key")
            if akid and secret:
                resource = resource_fn(request) if resource_fn else "arn:localaws:dynamodb:::*"
                data = call_iam_authorize(akid, secret, action, resource)
                if data is None:
                    return jsonify({"error": "IAM service unreachable"}), 503
                if not data.get("allowed"):
                    return jsonify({"error": "access denied"}), 403
                return f(*args, **kwargs)
            if session.get("user_email") is None:
                return jsonify({"error": "Not logged in"}), 401
            return f(*args, **kwargs)
        return wrapped
    return decorator


@dynamo_bp.route("/tables", methods=["GET"])
@require_permission("dynamodb:ListTables", lambda r: "arn:localaws:dynamodb:::table/*")
def list_tables():
    return jsonify({"tables": storage.list_tables()})


@dynamo_bp.route("/tables", methods=["POST"])
@require_permission("dynamodb:CreateTable", lambda r: f"arn:localaws:dynamodb:::table/{((r.get_json(silent=True) or {}).get('table_name') or '').strip()}")
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
@require_permission("dynamodb:DescribeTable", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
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
@require_permission("dynamodb:DeleteTable", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
def delete_table(table):
    if not storage.delete_table(table):
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    return "", 204


@dynamo_bp.route("/tables/<table>/items", methods=["PUT"])
@require_permission("dynamodb:PutItem", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
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
@require_permission("dynamodb:GetItem", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
def get_item(table, key):
    data = storage.load_table(table)
    if data is None:
        return jsonify({"error": f"Table '{table}' not found"}), 404
        
    item = data["items"].get(key)
    if item is None:
        return jsonify({"error": f"Item with key '{key}' not found"}), 404
        
    return jsonify({"item": item})


@dynamo_bp.route("/tables/<table>/items/<path:key>", methods=["DELETE"])
@require_permission("dynamodb:DeleteItem", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
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
@require_permission("dynamodb:Scan", lambda r: f"arn:localaws:dynamodb:::table/{r.view_args.get('table', '*')}")
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