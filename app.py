from flask import Flask, request, send_file, session, redirect, render_template, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
import psycopg2

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

from dynamodb.routes import dynamo_bp
app.register_blueprint(dynamo_bp)

ROOT = "storage"
os.makedirs(ROOT, exist_ok=True)

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


# ---------- S3 API (unchanged logic, now session-protected) ----------

def require_login():
    return session.get("user_email") is not None


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/s3/<bucket>", methods=["PUT"])
def create_bucket(bucket):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    os.makedirs(f"{ROOT}/{bucket}", exist_ok=True)
    return "", 200


@app.route("/api/s3", methods=["GET"])
def list_buckets():
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    return {"buckets": os.listdir(ROOT)}


@app.route("/api/s3/<bucket>/<key>", methods=["PUT"])
def upload(bucket, key):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    path = os.path.join(ROOT, bucket, key)
    with open(path, "wb") as f:
        f.write(request.data)
    return "", 200


@app.route("/api/s3/<bucket>", methods=["GET"])
def list_objects(bucket):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    return {"objects": os.listdir(f"{ROOT}/{bucket}")}


@app.route("/api/s3/<bucket>/<key>", methods=["GET"])
def download(bucket, key):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    return send_file(f"{ROOT}/{bucket}/{key}")


@app.route("/api/s3/<bucket>/<key>", methods=["DELETE"])
def delete_object(bucket, key):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    path = f"{ROOT}/{bucket}/{key}"
    if os.path.exists(path):
        os.remove(path)
        return "", 204
    return "", 404


@app.route("/api/s3/<bucket>", methods=["DELETE"])
def delete_bucket(bucket):
    if not require_login():
        return jsonify({"error": "Not logged in"}), 401
    path = f"{ROOT}/{bucket}"
    if os.path.exists(path):
        os.rmdir(path)
        return "", 204
    return "", 404

@app.route("/dynamodb")
def dynamodb_page():
    if not session.get("user_email"):
        return redirect("/signin")
    return render_template("dynamodb.html")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4566)
