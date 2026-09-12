import os
import sys
import time
import json
import zipfile
import shutil
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
import docker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared import require_permission, arn_lambda

app = Flask(__name__)

DB_HOST = os.environ.get("LAMBDA_DB_HOST", os.environ.get("DB_HOST", "localhost"))
DB_NAME = os.environ.get("LAMBDA_DB_NAME", os.environ.get("DB_NAME", "localaws"))
DB_USER = os.environ.get("LAMBDA_DB_USER", os.environ.get("DB_USER", "localaws"))
DB_PASSWORD = os.environ.get("LAMBDA_DB_PASSWORD", os.environ.get("DB_PASSWORD", "localaws"))

FUNCTIONS_DIR = "functions"
os.makedirs(FUNCTIONS_DIR, exist_ok=True)

try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None


def get_db():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def init_db():
    for _ in range(10):
        try:
            conn = get_db()
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lambda_functions (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    runtime TEXT NOT NULL DEFAULT 'python3.11',
                    handler TEXT NOT NULL DEFAULT 'handler.handler',
                    timeout INTEGER NOT NULL DEFAULT 15,
                    code_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.close()
            conn.close()
            return
        except Exception:
            time.sleep(2)


@app.route("/api/lambda/functions", methods=["GET"])
@require_permission("lambda:ListFunctions", lambda r: arn_lambda("*"), allow_session=False)
def list_functions():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, runtime, handler, timeout, code_path, created_at FROM lambda_functions ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for r in rows:
            if isinstance(r.get("created_at"), time.struct_time) or hasattr(r.get("created_at"), "isoformat"):
                r["created_at"] = str(r["created_at"])
        return jsonify({"functions": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lambda/functions", methods=["POST"])
@require_permission("lambda:CreateFunction", lambda r: arn_lambda((r.form.get("name") or (r.get_json(silent=True) or {}).get("name") or "").strip()), allow_session=False)
def create_function():
    name = None
    runtime = "python3.11"
    handler = "handler.handler"
    timeout = 15
    code_str = None

    if request.content_type and "multipart/form-data" in request.content_type:
        name = (request.form.get("name") or "").strip()
        runtime = (request.form.get("runtime") or "python3.11").strip()
        handler = (request.form.get("handler") or "handler.handler").strip()
        try:
            timeout = int(request.form.get("timeout", 15))
        except ValueError:
            timeout = 15
        code_str = request.form.get("code")
    else:
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        runtime = (body.get("runtime") or "python3.11").strip()
        handler = (body.get("handler") or "handler.handler").strip()
        try:
            timeout = int(body.get("timeout", 15))
        except ValueError:
            timeout = 15
        code_str = body.get("code")

    if not name:
        return jsonify({"error": "Function 'name' is required"}), 400

    func_dir = os.path.abspath(os.path.join(FUNCTIONS_DIR, name))
    os.makedirs(func_dir, exist_ok=True)

    # Check for uploaded zip file
    if "code_zip" in request.files:
        zip_file = request.files["code_zip"]
        zip_path = os.path.join(func_dir, "package.zip")
        zip_file.save(zip_path)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(func_dir)
        os.remove(zip_path)
    elif code_str:
        # Write inline python code to handler file
        mod_filename = handler.split(".")[0] + ".py"
        with open(os.path.join(func_dir, mod_filename), "w", encoding="utf-8") as f:
            f.write(code_str)
    else:
        # Default starter handler if no code provided
        default_code = """def handler(event, context):
    print("Default Lambda function executed with event:", event)
    return {
        "statusCode": 200,
        "body": "Hello from LocalAWS Lambda!",
        "event": event
    }
"""
        with open(os.path.join(func_dir, "handler.py"), "w", encoding="utf-8") as f:
            f.write(default_code)

    try:
        conn = get_db()
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO lambda_functions (name, runtime, handler, timeout, code_path)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (name) DO UPDATE SET
                 runtime = EXCLUDED.runtime,
                 handler = EXCLUDED.handler,
                 timeout = EXCLUDED.timeout,
                 code_path = EXCLUDED.code_path
               RETURNING id, name, runtime, handler, timeout, code_path, created_at""",
            (name, runtime, handler, timeout, func_dir),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = str(row["created_at"])
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lambda/functions/<name>", methods=["GET"])
@require_permission("lambda:GetFunction", lambda r: arn_lambda(r.view_args["name"]), allow_session=False)
def get_function(name):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, runtime, handler, timeout, code_path, created_at FROM lambda_functions WHERE name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": f"Function '{name}' not found"}), 404
        if hasattr(row.get("created_at"), "isoformat"):
            row["created_at"] = str(row["created_at"])
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lambda/functions/<name>", methods=["DELETE"])
@require_permission("lambda:DeleteFunction", lambda r: arn_lambda(r.view_args["name"]), allow_session=False)
def delete_function(name):
    try:
        conn = get_db()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DELETE FROM lambda_functions WHERE name = %s", (name,))
        cur.close()
        conn.close()

        func_dir = os.path.abspath(os.path.join(FUNCTIONS_DIR, name))
        if os.path.exists(func_dir):
            shutil.rmtree(func_dir)

        return "", 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lambda/functions/<name>/invoke", methods=["POST"])
@require_permission("lambda:InvokeFunction", lambda r: arn_lambda(r.view_args["name"]), allow_session=False)
def invoke_function(name):
    event_data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name, runtime, handler, timeout, code_path FROM lambda_functions WHERE name = %s", (name,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return jsonify({"error": f"Function '{name}' not found"}), 404

        code_path = os.path.abspath(row["code_path"])
        handler = row["handler"]
        timeout_sec = row.get("timeout", 15)

        host_base = os.environ.get("HOST_FUNCTIONS_DIR")
        if host_base:
            host_mount = os.path.join(host_base, name).replace("\\", "/")
        else:
            host_mount = code_path

        start_time = time.time()

        if docker_client:
            # Run in isolated short-lived python container
            runner_cmd = (
                "import json, os, sys, importlib; "
                "sys.path.insert(0, '/app'); "
                "mod_name, func_name = os.environ['HANDLER'].rsplit('.', 1); "
                "mod = importlib.import_module(mod_name); "
                "func = getattr(mod, func_name); "
                "evt = json.loads(os.environ.get('EVENT', '{}')); "
                "ctx = {'function_name': os.environ.get('NAME')}; "
                "res = func(evt, ctx); "
                "print('---LAMBDA_RESULT_START---'); "
                "print(json.dumps(res))"
            )

            container = docker_client.containers.run(
                image="python:3.11-slim",
                command=["python", "-c", runner_cmd],
                volumes={host_mount: {"bind": "/app", "mode": "ro"}},
                working_dir="/app",
                environment={
                    "HANDLER": handler,
                    "EVENT": json.dumps(event_data),
                    "NAME": name
                },
                detach=True
            )

            try:
                res_code = container.wait(timeout=timeout_sec)
                logs = container.logs().decode("utf-8", errors="replace")
            except Exception as e:
                container.remove(force=True)
                return jsonify({
                    "statusCode": 504,
                    "error": f"Function execution timed out after {timeout_sec} seconds",
                    "logs": str(e)
                }), 504
            finally:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse logs and payload
            payload = None
            if "---LAMBDA_RESULT_START---" in logs:
                parts = logs.split("---LAMBDA_RESULT_START---")
                log_output = parts[0].strip()
                result_raw = parts[1].strip()
                try:
                    payload = json.loads(result_raw)
                except Exception:
                    payload = result_raw
            else:
                log_output = logs.strip()

            return jsonify({
                "statusCode": 200,
                "payload": payload,
                "logs": log_output,
                "execution_time_ms": duration_ms
            })
        else:
            # Fallback inline execution if Docker daemon unavailable
            sys.path.insert(0, code_path)
            mod_name, func_name = handler.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            func = getattr(mod, func_name)
            res = func(event_data, {"function_name": name})
            duration_ms = int((time.time() - start_time) * 1000)
            return jsonify({
                "statusCode": 200,
                "payload": res,
                "logs": "Executed in inline mode",
                "execution_time_ms": duration_ms
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "lambda", "version": "1.0.0"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4569)
