import os
import json
import logging
import threading
import requests as _requests
from flask import Blueprint, request, send_file, jsonify
from shared import require_permission, arn_s3

log = logging.getLogger(__name__)

s3_bp = Blueprint("s3", __name__, url_prefix="/api/s3")

ROOT = "storage"
os.makedirs(ROOT, exist_ok=True)

LAMBDA_URL = os.environ.get("LAMBDA_URL", "http://minilambda:4569")
_VERSION = "1.0.0"


# ---------- notification config helpers ----------

def _notif_path(bucket):
    return os.path.join(ROOT, bucket, ".notification_config.json")


def _load_notif(bucket):
    p = _notif_path(bucket)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_notif(bucket, cfg):
    with open(_notif_path(bucket), "w") as f:
        json.dump(cfg, f)


def _fire_lambda_trigger(bucket, key, func_name):
    """Called in a background thread — must not raise."""
    payload = {
        "Records": [{
            "eventName": "s3:PutObject",
            "s3": {
                "bucket": {"name": bucket},
                "object": {"key": key}
            }
        }]
    }
    url = f"{LAMBDA_URL}/api/lambda/functions/{func_name}/invoke"
    try:
        resp = _requests.post(url, json=payload, timeout=30)
        log.info("S3 trigger %s/%s → lambda:%s  status=%s", bucket, key, func_name, resp.status_code)
    except Exception as exc:
        log.warning("S3 trigger %s/%s → lambda:%s FAILED: %s", bucket, key, func_name, exc)


@s3_bp.route("/<bucket>", methods=["PUT"])
@require_permission("s3:CreateBucket", lambda r: arn_s3(r.view_args["bucket"]))
def create_bucket(bucket):
    os.makedirs(f"{ROOT}/{bucket}", exist_ok=True)
    return "", 200


@s3_bp.route("", methods=["GET"])
@require_permission("s3:ListAllMyBuckets", lambda r: "arn:localaws:s3:::*")
def list_buckets():
    return {"buckets": os.listdir(ROOT)}


@s3_bp.route("/<bucket>/<key>", methods=["PUT"])
@require_permission("s3:PutObject", lambda r: arn_s3(r.view_args["bucket"], r.view_args["key"]))
def upload(bucket, key):
    path = os.path.join(ROOT, bucket, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(request.data)
    # Fire Lambda trigger async — never blocks upload response
    notif = _load_notif(bucket)
    func_name = notif.get("lambda_function") or notif.get("lambda_function_arn")
    if func_name:
        if "/" in func_name:
            func_name = func_name.split("/")[-1]
        t = threading.Thread(target=_fire_lambda_trigger, args=(bucket, key, func_name), daemon=True)
        t.start()
    return "", 200


@s3_bp.route("/<bucket>", methods=["GET"])
@require_permission("s3:ListBucket", lambda r: arn_s3(r.view_args["bucket"]))
def list_objects(bucket):
    return {"objects": os.listdir(f"{ROOT}/{bucket}")}


@s3_bp.route("/<bucket>/<key>", methods=["GET"])
@require_permission("s3:GetObject", lambda r: arn_s3(r.view_args["bucket"], r.view_args["key"]))
def download(bucket, key):
    return send_file(f"{ROOT}/{bucket}/{key}")


@s3_bp.route("/<bucket>/<key>", methods=["DELETE"])
@require_permission("s3:DeleteObject", lambda r: arn_s3(r.view_args["bucket"], r.view_args["key"]))
def delete_object(bucket, key):
    path = f"{ROOT}/{bucket}/{key}"
    if os.path.exists(path):
        os.remove(path)
        return "", 204
    return "", 404


@s3_bp.route("/<bucket>", methods=["DELETE"])
@require_permission("s3:DeleteBucket", lambda r: arn_s3(r.view_args["bucket"]))
def delete_bucket(bucket):
    path = f"{ROOT}/{bucket}"
    if os.path.exists(path):
        os.rmdir(path)
        return "", 204
    return "", 404


# ---------- notification config routes ----------

@s3_bp.route("/<bucket>/notification", methods=["GET"])
@require_permission("s3:GetBucketNotification", lambda r: arn_s3(r.view_args["bucket"]))
def get_notification(bucket):
    if not os.path.isdir(f"{ROOT}/{bucket}"):
        return jsonify({"error": "bucket not found"}), 404
    return jsonify(_load_notif(bucket))


@s3_bp.route("/<bucket>/notification", methods=["PUT"])
@require_permission("s3:PutBucketNotification", lambda r: arn_s3(r.view_args["bucket"]))
def put_notification(bucket):
    if not os.path.isdir(f"{ROOT}/{bucket}"):
        return jsonify({"error": "bucket not found"}), 404
    cfg = request.get_json(silent=True) or {}
    # Accept {"lambda_function": "<name>"} or {} to clear
    _save_notif(bucket, cfg)
    return jsonify(cfg)


# ---------- health ----------

@s3_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "s3", "version": _VERSION})
