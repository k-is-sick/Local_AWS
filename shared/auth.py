import os
import requests
from functools import wraps
from flask import request, jsonify, session


def get_iam_url():
    return os.environ.get("IAM_URL", "http://miniiam:4568")


def call_iam_authorize(access_key_id, secret_key, action, resource, iam_url=None):
    base_url = iam_url or get_iam_url()
    urls = [base_url, "http://localhost:4568", "http://127.0.0.1:4568"]
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


def require_permission(action, resource_fn=None, allow_session=True):
    """
    Authorization decorator supporting API key authentication (via IAM endpoint)
    and optional web session authentication fallback.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            akid = request.headers.get("X-Access-Key-Id")
            secret = request.headers.get("X-Secret-Key")
            if akid and secret:
                resource = resource_fn(request) if resource_fn else "*"
                data = call_iam_authorize(akid, secret, action, resource)
                if data is None:
                    return jsonify({"error": "IAM service unreachable"}), 503
                if not data.get("allowed"):
                    return jsonify({"error": "access denied"}), 403
                return f(*args, **kwargs)
            if allow_session:
                if session.get("user_email") is None:
                    return jsonify({"error": "Not logged in"}), 401
                return f(*args, **kwargs)
            return f(*args, **kwargs)
        return wrapped
    return decorator
