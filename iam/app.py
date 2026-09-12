import os
import re
import json
import secrets
import string
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

DB_HOST = os.environ.get("IAM_DB_HOST", os.environ.get("DB_HOST", "iamdb"))
DB_NAME = os.environ.get("IAM_DB_NAME", os.environ.get("DB_NAME", "localawsiam"))
DB_USER = os.environ.get("IAM_DB_USER", os.environ.get("DB_USER", "localawsiam"))
DB_PASSWORD = os.environ.get("IAM_DB_PASSWORD", os.environ.get("DB_PASSWORD", "localawsiam"))


def get_conn():
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    conn.autocommit = True
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS iam_users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS access_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES iam_users(id) ON DELETE CASCADE,
            access_key_id TEXT UNIQUE NOT NULL,
            secret_key TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS policies (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            document JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS user_policies (
            user_id INTEGER REFERENCES iam_users(id) ON DELETE CASCADE,
            policy_id INTEGER REFERENCES policies(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, policy_id)
        );
    """)
    cur.close()
    conn.close()


def gen_access_key_id():
    return "AKIA" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))


def gen_secret_key():
    return secrets.token_urlsafe(30)


# ---------- Policy evaluation ----------

def _match(pattern, value):
    # supports '*' wildcard, e.g. 's3:*' or 'arn:localaws:s3:::bucket/*'
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, value) is not None


def evaluate(statements, action, resource):
    """explicit Deny > explicit Allow > default Deny"""
    allowed = False
    for stmt in statements:
        actions = stmt.get("Action", [])
        resources = stmt.get("Resource", [])
        if isinstance(actions, str):
            actions = [actions]
        if isinstance(resources, str):
            resources = [resources]

        action_match = any(_match(a, action) for a in actions)
        resource_match = any(_match(r, resource) for r in resources)

        if action_match and resource_match:
            if stmt.get("Effect") == "Deny":
                return False  # explicit deny short-circuits
            if stmt.get("Effect") == "Allow":
                allowed = True
    return allowed


# ---------- Users ----------

@app.route("/api/iam/users", methods=["GET", "POST"])
def users():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == "POST":
        username = request.json.get("username")
        if not username:
            return jsonify({"error": "username required"}), 400
        try:
            cur.execute(
                "INSERT INTO iam_users (username) VALUES (%s) RETURNING id, username, created_at",
                (username,),
            )
            user = cur.fetchone()
        except psycopg2.errors.UniqueViolation:
            return jsonify({"error": "username already exists"}), 409
        finally:
            cur.close()
            conn.close()
        return jsonify(user), 201

    cur.execute("SELECT id, username, created_at FROM iam_users ORDER BY id")
    result = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(result)


@app.route("/api/iam/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM iam_users WHERE id = %s", (user_id,))
    cur.close()
    conn.close()
    return jsonify({"deleted": user_id})


# ---------- Access Keys ----------

@app.route("/api/iam/users/<int:user_id>/keys", methods=["GET", "POST"])
def access_keys(user_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == "POST":
        akid = gen_access_key_id()
        secret = gen_secret_key()
        cur.execute(
            """INSERT INTO access_keys (user_id, access_key_id, secret_key)
               VALUES (%s, %s, %s) RETURNING id, access_key_id, secret_key, active, created_at""",
            (user_id, akid, secret),
        )
        key = cur.fetchone()
        cur.close()
        conn.close()
        # secret_key only ever shown on creation, like real AWS
        return jsonify(key), 201

    cur.execute(
        "SELECT id, access_key_id, active, created_at FROM access_keys WHERE user_id = %s",
        (user_id,),
    )
    result = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(result)


@app.route("/api/iam/keys/<string:access_key_id>", methods=["DELETE"])
def delete_key(access_key_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM access_keys WHERE access_key_id = %s", (access_key_id,))
    cur.close()
    conn.close()
    return jsonify({"deleted": access_key_id})


@app.route("/api/iam/keys/<string:access_key_id>/deactivate", methods=["POST"])
def deactivate_key(access_key_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE access_keys SET active = FALSE WHERE access_key_id = %s", (access_key_id,))
    cur.close()
    conn.close()
    return jsonify({"deactivated": access_key_id})


# ---------- Policies ----------

@app.route("/api/iam/policies", methods=["GET", "POST"])
def policies():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == "POST":
        name = request.json.get("name")
        document = request.json.get("document")
        if not name or not document:
            return jsonify({"error": "name and document required"}), 400
        if "Statement" not in document:
            return jsonify({"error": "document must contain 'Statement'"}), 400
        try:
            cur.execute(
                "INSERT INTO policies (name, document) VALUES (%s, %s) RETURNING id, name, document, created_at",
                (name, json.dumps(document)),
            )
            policy = cur.fetchone()
        except psycopg2.errors.UniqueViolation:
            return jsonify({"error": "policy name already exists"}), 409
        finally:
            cur.close()
            conn.close()
        return jsonify(policy), 201

    cur.execute("SELECT id, name, document, created_at FROM policies ORDER BY id")
    result = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(result)


@app.route("/api/iam/policies/<int:policy_id>", methods=["DELETE"])
def delete_policy(policy_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM policies WHERE id = %s", (policy_id,))
    cur.close()
    conn.close()
    return jsonify({"deleted": policy_id})


@app.route("/api/iam/users/<int:user_id>/policies/<int:policy_id>", methods=["PUT", "DELETE"])
def attach_policy(user_id, policy_id):
    conn = get_conn()
    cur = conn.cursor()
    if request.method == "PUT":
        cur.execute(
            "INSERT INTO user_policies (user_id, policy_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, policy_id),
        )
        action = "attached"
    else:
        cur.execute(
            "DELETE FROM user_policies WHERE user_id = %s AND policy_id = %s",
            (user_id, policy_id),
        )
        action = "detached"
    cur.close()
    conn.close()
    return jsonify({action: {"user_id": user_id, "policy_id": policy_id}})


# ---------- Authorize (the core integration endpoint) ----------

@app.route("/api/iam/authorize", methods=["POST"])
def authorize():
    body = request.json or {}
    access_key_id = body.get("access_key_id")
    secret_key = body.get("secret_key")
    action = body.get("action")
    resource = body.get("resource")

    if not all([access_key_id, secret_key, action, resource]):
        return jsonify({"allowed": False, "reason": "missing fields"}), 400

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT user_id, secret_key, active FROM access_keys WHERE access_key_id = %s",
        (access_key_id,),
    )
    key_row = cur.fetchone()

    if not key_row or not key_row["active"] or key_row["secret_key"] != secret_key:
        cur.close()
        conn.close()
        return jsonify({"allowed": False, "reason": "invalid credentials"}), 401

    cur.execute(
        """SELECT p.document FROM policies p
           JOIN user_policies up ON up.policy_id = p.id
           WHERE up.user_id = %s""",
        (key_row["user_id"],),
    )
    all_statements = []
    for row in cur.fetchall():
        doc = row["document"]
        stmts = doc.get("Statement", [])
        if isinstance(stmts, dict):
            stmts = [stmts]
        all_statements.extend(stmts)
    cur.close()
    conn.close()

    allowed = evaluate(all_statements, action, resource)
    return jsonify({"allowed": allowed, "action": action, "resource": resource})


# ---------- Dashboard ----------

@app.route("/")
def dashboard():
    return render_template("iamconsole.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "iam", "version": "1.0.0"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4568)