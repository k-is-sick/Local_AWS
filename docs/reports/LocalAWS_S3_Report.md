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

## How To Run It
```bash
docker-compose up -d --build   # build & start container
docker ps                      # confirm it's running
```

## How To Use It (API Guide)
All requests need `-H "Content-Type: application/octet-stream"` when uploading.

| Action | Command |
|---|---|
| Create bucket | `curl.exe -X PUT http://localhost:4566/mybucket` |
| List buckets | `curl.exe http://localhost:4566/` |
| Upload file | `curl.exe -X PUT http://localhost:4566/mybucket/file.txt -H "Content-Type: application/octet-stream" --data-binary "hello"` |
| List objects | `curl.exe http://localhost:4566/mybucket` |
| Download file | `curl.exe http://localhost:4566/mybucket/file.txt` |
| Delete object | `curl.exe -X DELETE http://localhost:4566/mybucket/file.txt` |
| Delete bucket (must be empty) | `curl.exe -X DELETE http://localhost:4566/mybucket` |

## Key Learnings & Solved Issues
- **Favicon Errors**: Added a dedicated route returning `204` for `/favicon.ico`.
- **PowerShell Curl Alias**: Used `curl.exe` explicitly on Windows instead of PowerShell's built-in `Invoke-WebRequest`.
- **Raw Byte Body Parsing**: Set `-H "Content-Type: application/octet-stream"` on file uploads so Flask parses the raw byte payload without form decoding.
- **Unbuffered Logs**: Enabled `PYTHONUNBUFFERED=1` in Docker Compose for real-time trace logging.
