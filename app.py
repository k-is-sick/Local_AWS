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