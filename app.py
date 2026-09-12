import os
import time
from flask import Flask, request, session, redirect, render_template, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import requests
import docker

from shared import get_iam_url, call_iam_authorize
from dynamodb import dynamo_bp
from s3 import s3_bp

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get("SECRET_KEY", "localaws-dev-secret")

app.register_blueprint(dynamo_bp)
app.register_blueprint(s3_bp)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "localaws")
DB_USER = os.environ.get("DB_USER", "localaws")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "localaws")


def get_db():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def init_db():
    # retry loop in case postgres isn't ready yet when this container starts
    for attempt in range(15):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            time.sleep(2)


_VERSION = "1.0.0"

SERVICE_CONFIG = {
    "s3": {
        "container_pattern": "localaws",
        "health_url": "http://localhost:4566/api/s3/health",
        "type": "builtin"
    },
    "dynamodb": {
        "container_pattern": "localaws",
        "health_url": "http://localhost:4566/api/dynamodb/health",
        "type": "builtin"
    },
    "ec2": {
        "container_pattern": "miniec2",
        "health_url": "http://miniec2:4567/api/health",
        "alt_health_url": "http://localhost:4567/api/health",
        "type": "container"
    },
    "iam": {
        "container_pattern": "miniiam",
        "health_url": "http://miniiam:4568/api/health",
        "alt_health_url": "http://localhost:4568/api/health",
        "type": "container"
    },
    "lambda": {
        "container_pattern": "minilambda",
        "health_url": "http://minilambda:4569/api/health",
        "alt_health_url": "http://localhost:4569/api/health",
        "type": "container"
    }
}


def get_docker_client():
    try:
        return docker.from_env()
    except Exception:
        return None


def get_container_by_pattern(client, pattern):
    if not client:
        return None
    try:
        containers = client.containers.list(all=True)
        for c in containers:
            if pattern in c.name:
                return c
    except Exception:
        pass
    return None


# ---------- HEALTH & SERVICES CONTROL ----------

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "gateway", "version": _VERSION})


@app.route("/api/services/status")
def services_status():
    client = get_docker_client()
    results = {}
    for name, cfg in SERVICE_CONFIG.items():
        container_state = "unknown"
        if client and cfg.get("container_pattern"):
            c = get_container_by_pattern(client, cfg["container_pattern"])
            if c:
                container_state = c.status

        api_state = "unreachable"
        urls = [cfg["health_url"]]
        if "alt_health_url" in cfg:
            urls.append(cfg["alt_health_url"])

        for u in urls:
            try:
                resp = requests.get(u, timeout=1.5)
                if resp.status_code == 200:
                    api_state = "ok"
                    break
            except Exception:
                pass

        if container_state in ("exited", "stopped"):
            final_status = "stopped"
        elif api_state == "ok":
            final_status = "running"
        elif container_state == "running":
            final_status = "starting"
        else:
            final_status = "running" if api_state == "ok" else "stopped"

        results[name] = {
            "status": final_status,
            "container": container_state,
            "api": api_state,
            "can_control": cfg.get("type") == "container"
        }
    return jsonify(results)


@app.route("/api/services/<name>/start", methods=["POST"])
def start_service(name):
    cfg = SERVICE_CONFIG.get(name)
    if not cfg:
        return jsonify({"error": f"Unknown service {name}"}), 400
    if cfg.get("type") == "builtin":
        return jsonify({"message": "Service is built into gateway and is running"}), 200
    client = get_docker_client()
    if not client:
        return jsonify({"error": "Docker SDK unavailable"}), 500
    c = get_container_by_pattern(client, cfg["container_pattern"])
    if not c:
        return jsonify({"error": f"Container for service {name} not found"}), 404
    try:
        c.start()
        return jsonify({"ok": True, "service": name, "status": "starting"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/services/<name>/stop", methods=["POST"])
def stop_service(name):
    cfg = SERVICE_CONFIG.get(name)
    if not cfg:
        return jsonify({"error": f"Unknown service {name}"}), 400
    if cfg.get("type") == "builtin":
        return jsonify({"error": "Cannot stop built-in service independently"}), 400
    client = get_docker_client()
    if not client:
        return jsonify({"error": "Docker SDK unavailable"}), 500
    c = get_container_by_pattern(client, cfg["container_pattern"])
    if not c:
        return jsonify({"error": f"Container for service {name} not found"}), 404
    try:
        c.stop(timeout=5)
        return jsonify({"ok": True, "service": name, "status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ---------- PAGE ROUTES ----------

@app.route("/")
def landing_page():
    if session.get("user_email"):
        return redirect("/services")
    return render_template("landing.html")


@app.route("/signin")
def signin_page():
    return render_template("login.html")


@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/services")
def services_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("services.html", email=session.get("user_email"))


@app.route("/s3console")
def s3_console_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("s3console.html")


@app.route("/dynamodb")
def dynamodb_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("dynamodb.html")


def get_lambda_url():
    return os.environ.get("LAMBDA_URL", "http://minilambda:4569")


@app.route("/iamconsole")
def iam_console_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("iamconsole.html")


@app.route("/lambdaconsole")
def lambda_console_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("lambdaconsole.html")


@app.route("/api/lambda/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_lambda(subpath):
    urls = [get_lambda_url(), "http://localhost:4569", "http://127.0.0.1:4569"]
    last_err = None
    for url in urls:
        try:
            target_url = f"{url}/api/lambda/{subpath}"
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers={k: v for k, v in request.headers if k.lower() != 'host'},
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=15
            )
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            return (resp.content, resp.status_code, headers)
        except requests.RequestException as e:
            last_err = e
            continue

    return jsonify({"error": "Lambda service is currently offline. Start it via: cd lambda; python app.py"}), 503



@app.route("/api/iam/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_iam(subpath):
    urls = [get_iam_url(), "http://localhost:4568", "http://127.0.0.1:4568"]
    last_err = None
    for url in urls:
        try:
            target_url = f"{url}/api/iam/{subpath}"
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers={k: v for k, v in request.headers if k.lower() != 'host'},
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=5
            )
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            return (resp.content, resp.status_code, headers)
        except requests.RequestException as e:
            last_err = e
            continue

    return jsonify({"error": "IAM service is currently offline. Start it via: cd iam; docker-compose up -d --build"}), 503


@app.route("/coming-soon/<service>")
def coming_soon(service):
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("coming_soon.html", service=service.upper())


# ---------- AUTH API ----------

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (email, generate_password_hash(password)),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "An account with this email already exists"}), 409
    finally:
        cur.close()
        conn.close()

    session["user_email"] = email
    return jsonify({"ok": True, "redirect": "/services"})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not check_password_hash(row[0], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_email"] = email
    return jsonify({"ok": True, "redirect": "/services"})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/"})


@app.route("/api/me")
def api_me():
    if session.get("user_email"):
        return jsonify({"email": session["user_email"]})
    return jsonify({"email": None}), 401


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4566)
