# LocalAWS — Auth & Services Console: Project Report

## What We Did
Extended the existing self-built S3 clone into a full mini cloud console: added a landing page, email/password sign-up and sign-in backed by PostgreSQL, session-based login protection, and a Services dashboard showing active and modular AWS services (S3, EC2, IAM, DynamoDB, Lambda) — matching the look and flow of the real AWS Management Console, fully custom-built and self-hosted.

## Why We Did It
The goal was to build a personal "ministack" from scratch to understand how cloud control planes work internally — storage, routing, database authentication, and multi-service dashboards.

## Architecture & Workflow
- **Flask**: Serves HTML pages, JSON APIs, and reverse proxies for microservices.
- **PostgreSQL**: Stores user accounts (`email`, hashed password with werkzeug) in a `users` table.
- **Flask Sessions**: Cookie-based authentication protecting service consoles and endpoints.
- **Docker Compose**: Multi-container stack on a shared `localaws` network.

### User Flow
1. Visit `http://localhost:4566` → landing page → Sign in / Create account.
2. Sign-up hashes the password and inserts it into Postgres.
3. On success, a session cookie is set and the user is redirected to `/services`.
4. The Services dashboard presents available cloud services.

## Key Files
```
LocalAWS/
  app.py
  Dockerfile
  docker-compose.yaml
  templates/
    landing.html
    login.html
    signup.html
    services.html
    coming_soon.html
    s3console.html
    dynamodb.html
    iamconsole.html
```

## How To Run It
```bash
docker-compose down
docker-compose up -d --build
```
Open `http://localhost:4566` in your browser.
