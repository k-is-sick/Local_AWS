# LocalAWS (Mini S3 Clone) — Project Report

## What We Did
Built a self-made local clone of AWS S3 from scratch — not using LocalStack — to learn how S3-like storage works under the hood. The result is a small Flask HTTP server, containerized with Docker, that supports creating buckets, uploading/downloading objects, listing contents, and deleting buckets/objects.

## Why We Did It
The goal was to understand and build the mechanics of an S3 clone ourselves (a personal "ministack"), rather than running an existing emulator. This gives full visibility into how S3 operations map to simple file system actions.

## How It Works
- Each **bucket** = a folder under `storage/`
- Each **object** = a file inside that bucket folder
- A Flask app exposes REST routes mimicking S3 verbs (PUT to create/upload, GET to list/download, DELETE to remove)
- Docker volume mount (`./storage:/app/storage`) keeps data persistent on the host disk, even if the container is rebuilt or removed

## Project Structure
```
LocalAWS/
  app.py
  Dockerfile
  docker-compose.yaml
  storage/        <- buckets & objects live here
```

## app.py (Final Version)
```python
from flask import Flask, request, send_file
import os

app = Flask(__name__)
ROOT = "storage"
os.makedirs(ROOT, exist_ok=True)

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/<bucket>", methods=["PUT"])
def create_bucket(bucket):
    os.makedirs(f"{ROOT}/{bucket}", exist_ok=True)
    return "", 200

@app.route("/", methods=["GET"])
def list_buckets():
    return {"buckets": os.listdir(ROOT)}

@app.route("/<bucket>/<key>", methods=["PUT"])
def upload(bucket, key):
    path = os.path.join(ROOT, bucket, key)
    with open(path, "wb") as f:
        f.write(request.data)
    return "", 200

@app.route("/<bucket>", methods=["GET"])
def list_objects(bucket):
    return {"objects": os.listdir(f"{ROOT}/{bucket}")}

@app.route("/<bucket>/<key>", methods=["GET"])
def download(bucket, key):
    return send_file(f"{ROOT}/{bucket}/{key}")

@app.route("/<bucket>/<key>", methods=["DELETE"])
def delete_object(bucket, key):
    path = f"{ROOT}/{bucket}/{key}"
    if os.path.exists(path):
        os.remove(path)
        return "", 204
    return "", 404

@app.route("/<bucket>", methods=["DELETE"])
def delete_bucket(bucket):
    path = f"{ROOT}/{bucket}"
    if os.path.exists(path):
        os.rmdir(path)
        return "", 204
    return "", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4566)
```

## Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
RUN pip install flask
EXPOSE 4566
CMD ["python", "app.py"]
```

## docker-compose.yaml
```yaml
services:
  minis3:
    build: .
    environment:
      - PYTHONUNBUFFERED=1
    ports:
      - "4566:4566"
    volumes:
      - "./storage:/app/storage"
```

## How To Run It
```bash
docker-compose up -d --build   # build & start container
docker ps                      # confirm it's running
```

## How To Use It (API Guide)
All requests need `-H "Content-Type: application/octet-stream"` when uploading (see Issues below).

| Action | Command |
|---|---|
| Create bucket | `curl.exe -X PUT http://localhost:4566/mybucket` |
| List buckets | `curl.exe http://localhost:4566/` |
| Upload file | `curl.exe -X PUT http://localhost:4566/mybucket/file.txt -H "Content-Type: application/octet-stream" --data-binary "hello"` |
| List objects | `curl.exe http://localhost:4566/mybucket` |
| Download file | `curl.exe http://localhost:4566/mybucket/file.txt` |
| Delete object | `curl.exe -X DELETE http://localhost:4566/mybucket/file.txt` |
| Delete bucket (must be empty) | `curl.exe -X DELETE http://localhost:4566/mybucket` |

## Issues Faced & Fixes

**1. Favicon errors in logs**
Browser auto-requests `/favicon.ico`, treated as a missing bucket → 500 error.
*Fix:* added a dedicated route returning `204` for `/favicon.ico`.

**2. PowerShell `curl` isn't real curl**
`curl -X ...` failed because PowerShell aliases `curl` to `Invoke-WebRequest`, which doesn't support `-X`.
*Fix:* use `curl.exe` explicitly to get the real curl binary.

**3. Uploaded files were 0 bytes**
Despite the request returning `200 OK`, files on disk were empty.
*Root cause:* curl.exe defaults to `Content-Type: application/x-www-form-urlencoded` when using `--data`/`--data-binary` without an explicit header. Flask parses that content type as form data, consuming the request body — leaving `request.data` empty.
*Fix:* explicitly set `-H "Content-Type: application/octet-stream"` on all upload requests, forcing Flask to treat the body as raw bytes.

**4. Print statements not appearing in Docker logs**
Debug `print()` calls inside the Flask app weren't showing up in `docker-compose logs`.
*Root cause:* Python buffers stdout by default when not attached to an interactive terminal (as is the case in a container).
*Fix:* added `PYTHONUNBUFFERED=1` to the compose file's environment, forcing immediate flush of all output.

**5. Container removed during rebuild — data safe?**
Running `docker-compose down` removes the container, raising concern that data was lost.
*Clarification:* the container is disposable; data lives in the `./storage` host-mounted volume, which persists independently of the container lifecycle.

## Final State
A working, containerized S3-like local server with full CRUD support for buckets and objects, debug code removed, and a clean reproducible setup via Docker Compose.
