# LocalAWS — Auth & Services Console: Project Report

## What We Did
Extended the existing self-built S3 clone into a full mini cloud console: added a landing page, email/password sign-up and sign-in backed by PostgreSQL, session-based login protection, and a Services dashboard showing four service icons (S3, EC2, Lambda, DynamoDB) — matching the look and flow of the real AWS console, but fully custom-built and self-hosted.

## Why We Did It
The original goal was never to use LocalStack, but to build our own "ministack" from scratch to understand how these systems work internally — storage, routing, and now authentication and a multi-service entry point, just like a real cloud provider's console.

## How It Works

**Architecture:**
- **Flask** — serves both the HTML pages and the JSON API
- **PostgreSQL** — stores user accounts (email + hashed password) in a `users` table
- **Flask sessions (cookies)** — track logged-in state; all S3 routes now require a valid session
- **Docker Compose** — runs two containers: `minis3` (the app) and `db` (Postgres), networked together automatically

**User flow:**
1. Visit `http://localhost:4566` → landing page → Sign in / Create account
2. Sign-up sends email + password to `/api/signup`, which hashes the password (`werkzeug.security`) and inserts it into Postgres
3. On success, a session cookie is set and the user is redirected to `/services`
4. The Services page shows 4 cards: clicking **S3** opens the real working console (`/s3console`); the other three show a "Coming Soon" page
5. The S3 console talks to `/api/s3/...` endpoints, all of which check `session.get("user_email")` before responding

## Project Structure
```
LocalAWS/
  app.py
  Dockerfile
  docker-compose.yaml
  storage/                  <- buckets & objects (persisted via volume)
  templates/
    landing.html
    login.html
    signup.html
    services.html
    coming_soon.html
    s3console.html
```

## How To Run It
```bash
docker-compose down
docker-compose up -d --build
docker ps                     # confirm both minis3 and db are running
```
Open `http://localhost:4566` in a browser — never open any `.html` file directly from disk, always go through the running server.

## Issues Faced & Fixes

**1. Old standalone `index.html` still being used**
After adding auth, the browser kept showing the old unauthenticated S3 UI.
*Cause:* an old `index.html` file was still present and being opened directly instead of the new `templates/s3console.html` served by Flask.
*Fix:* deleted the old file; confirmed access only through `http://localhost:4566`, not `file://`.

**2. `psycopg2.OperationalError: password authentication failed`, connecting to `localhost`**
*Cause:* `app.py` was being run directly on Windows (`python app.py`) instead of inside Docker. Outside the container, the `DB_HOST=db` environment variable from `docker-compose.yaml` doesn't apply, so it fell back to `localhost`, which has no matching Postgres user locally.
*Fix:* run the whole stack via `docker-compose up -d --build` instead of running `app.py` directly — Docker's internal network resolves `db` to the Postgres container correctly.

**3. Buckets failed to load: `404 NOT FOUND` on `/api/s3/`**
*Cause:* the frontend called `api("/")` for the bucket-list request, which combined with `ENDPOINT = "/api/s3"` produced `/api/s3/` — a different path than the registered Flask route `/api/s3` (no trailing slash).
*Fix:* changed the call to `api("")`, producing the correct `/api/s3` request.

**4. Edits not taking effect**
*Cause:* changes to `templates/*.html` or `app.py` don't apply automatically — Docker uses the image built at `docker-compose up --build` time, and only `./storage` is live-mounted.
*Fix:* always run `docker-compose down && docker-compose up -d --build` after any code change, then hard-refresh the browser (Ctrl+Shift+R) to clear cached JS.

## How-To Guide (For Someone New To This Project)

**1. Prerequisites:** Docker Desktop installed and running.

**2. Get the code:** all files live in `LocalAWS/` — `app.py`, `Dockerfile`, `docker-compose.yaml`, and a `templates/` folder with all the HTML pages.

**3. Start everything:**
```bash
docker-compose up -d --build
```
This builds the Flask app image and starts both the app and a Postgres database container.

**4. Use the console:**
- Go to `http://localhost:4566`
- Click **Create new account**, enter any email + a password (6+ characters)
- You'll land on the **Services** page with 4 icons
- Click **S3** to manage buckets and files (create/delete buckets, upload/download/delete/inspect files)
- EC2, Lambda, and DynamoDB currently show a "Coming Soon" page, since only S3 is implemented

**5. Making changes:**
- Backend logic lives in `app.py` (Flask routes)
- Frontend pages live in `templates/*.html`
- After any change, rebuild: `docker-compose down && docker-compose up -d --build`
- Hard-refresh the browser afterward to avoid stale cached files

**6. Checking logs / debugging:**
```bash
docker-compose logs -f minis3   # app logs, including Python tracebacks
docker-compose logs -f db       # Postgres logs
```

**7. Data persistence:**
- Uploaded files live in `./storage` on the host machine (safe across rebuilds)
- User accounts live inside the Postgres container's `pgdata` Docker volume (also safe across rebuilds, but wiped if you run `docker-compose down -v`)

## Final State
A working local cloud console: landing page, Postgres-backed signup/login with session protection, a services dashboard with 4 icons, and a fully functional S3 clone (buckets, objects, upload/download/delete, file inspection) reachable only after authentication.
