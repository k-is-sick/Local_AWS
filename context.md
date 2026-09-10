# LocalAWS — Comprehensive System Context & Multi-Service Architecture

## 1. Project Overview & Vision

**LocalAWS** is a lightweight, self-hosted local emulation suite for core Amazon Web Services (AWS). Designed to run entirely on developer machines without third-party monoliths (like LocalStack), LocalAWS provides a clean, transparent, and modular micro-cloud environment for learning, testing, and developing cloud applications offline with zero infrastructure costs.

The platform provides both:
1. **RESTful APIs**: Emulating standard AWS service operations (S3, DynamoDB, EC2, and IAM).
2. **Interactive Web Consoles**: An intuitive, unified web management interface mirroring the AWS Management Console workflow.

---

## 2. Multi-Service Architecture & Port Mapping

```
                                  +---------------------------------------------+
                                  |         Developer / Web Browser / CLI       |
                                  +---------------------------------------------+
                                                         |
                 +-----------------------+---------------+-----------------------+
                 |                       |                                       |
                 v HTTP :4566            v HTTP :4567                            v HTTP :4568
+--------------------------------+ +-----------------------------+ +-----------------------------+
| LocalAWS Gateway & S3/DynamoDB | | EC2 Service Engine          | | IAM Policy & Identity Engine|
|                                | |                             | |                             |
| - Session Auth & PostgreSQL    | | - Docker-in-Docker Instance | | - User & Access Key DB      |
| - S3 Object Store (/api/s3)    | |   Lifecycle Management      | | - JSON Policy Evaluator     |
| - DynamoDB Store (/api/dynamo) | | - Web Terminal Console      | | - Authorize API Endpoint    |
| - Services Console Directory   | |   (ttyd WebSocket terminal) | |   (/api/iam/authorize)      |
+--------------------------------+ +-----------------------------+ +-----------------------------+
                 |                                                               |
                 +--------------------> Authorization Check --------------------+
                                      (X-Access-Key-Id / Secret)
```

### Port Allocation:
| Service | Port | Description |
|---|---|---|
| **LocalAWS Gateway / S3 / DynamoDB** | `4566` | Central authentication, services dashboard, S3 storage, DynamoDB table engine |
| **EC2 Service** | `4567` | Docker-backed virtual machine simulator with web terminal (`ttyd`) |
| **IAM Service** | `4568` | Policy engine, access key management, permission authorization |
| **PostgreSQL Database** | `5432` | Identity and state storage (`localaws` and `localawsiam`) |

---

## 3. Global Conventions & Standards

To ensure complete interoperability across all service components:

1. **Global Variable & Identifier Naming**:
   - The global project and service identifier is strictly `localaws` (never `miniaws` or `minis3`).
   - Database name: `localaws` / `localawsiam`
   - Database user: `localaws` / `localawsiam`
   - Docker container/service names: `localaws`, `db`, `miniec2`, `miniiam`
   - Default secret key & configuration tokens use `localaws` conventions.

2. **Unified Authentication & Dual-Mode Authorization**:
   - **Console / Web Browser**: Authenticated via Flask session cookies (`session.get("user_email")`).
   - **Programmatic / API Clients**: Authenticated via IAM headers `X-Access-Key-Id` and `X-Secret-Key`.
   - Authorization decorator pattern (`require_permission`):
     - If API key headers are present, request authorizes against IAM `/api/iam/authorize` (`action`, `resource`).
     - Otherwise, falls back to session cookie verification.

3. **Resource ARN Formats**:
   - **S3**: `arn:localaws:s3:::<bucket_name>/<object_key>`
   - **DynamoDB**: `arn:localaws:dynamodb:::table/<table_name>`
   - **EC2**: `arn:localaws:ec2:::instance/<instance_id>`

---

## 4. Service Deep-Dives

### A. Authentication & Services Hub (`app.py`, port 4566)
- **Database**: PostgreSQL `users` table (`email`, hashed password with werkzeug).
- **Console**: `/services` lists all active services (S3, DynamoDB, IAM, EC2, Lambda) with real-time status badges and account controls.

### B. Amazon S3 Clone (`storage/` & `/api/s3`, port 4566)
- **Storage Engine**: Local directory `storage/<bucket>/<key>`.
- **API**: Full CRUD for buckets and objects (`GET`, `PUT`, `DELETE`).
- **Console**: `/s3console` — File uploader, object inspector (image and text preview), bucket creation/deletion.

### C. Amazon DynamoDB Clone (`dynamodb/`, `dynamodb_data/`, port 4566)
- **Storage Engine**: Atomic JSON file store under `dynamodb_data/<table_name>.json`.
- **Key Schema**: Supports Partition Key (PK) and composite Partition Key + Sort Key (PK#SK).
- **API**: `/api/dynamodb/tables` (list, create, describe, delete), `/items` (put, get, delete, scan).
- **Console**: `/dynamodb` — Two-panel management UI, JSON item modal editor, key search, and scan viewer.

### D. Amazon IAM Service (`IAM/`, port 4568)
- **Database**: PostgreSQL tables: `iam_users`, `access_keys` (`AKIA...`), `policies`, `user_policies`.
- **Policy Engine**: Evaluates standard AWS JSON statement format (`Effect: Allow/Deny`, `Action`, `Resource` with wildcard matching).
- **API**: `/api/iam/users`, `/api/iam/policies`, `/api/iam/authorize`.
- **Console**: `/iamconsole` — User management, API key generator, policy attachment.

### E. Amazon EC2 Service (`EC2/`, port 4567)
- **Engine**: Python `docker` SDK managing isolated container instances (`alpine`, `ubuntu`, etc.).
- **Console**: Interactive web terminal embedded using `ttyd` container per instance.
- **API**: `/launch`, `/stop/<id>`, `/start/<id>`, `/terminate/<id>`.

---

## 5. Complete Directory Map

```
LocalAWS/
├── app.py                      # Main LocalAWS application entrypoint & gateway (port 4566)
├── context.md                  # Comprehensive architectural specification document
├── Dockerfile                  # LocalAWS container definition
├── docker-compose.yaml         # Multi-container orchestration (localaws + postgres)
│
├── EC2/                        # Original EC2 Service module (port 4567)
│   ├── app.py                  # EC2 Flask server & container lifecycle controller
│   ├── Dockerfile              # EC2 service container
│   ├── docker-compose.yaml     # Standalone EC2 docker compose
│   ├── local_ec2_report.md     # EC2 implementation report
│   └── ttyd.Dockerfile         # Web terminal container
│
├── IAM/                        # Original IAM Service module (port 4568)
│   ├── app.py                  # IAM policy evaluation server
│   ├── dockerfile              # IAM service container
│   └── docker-compose.yaml     # Standalone IAM + Postgres docker compose
│
├── S3/                         # Original standalone S3 module reference
│   ├── app.py                  # Standalone S3 server
│   ├── dockerfile              # S3 container
│   ├── docker-compose.yaml     # S3 docker compose
│   └── index.html              # Standalone S3 UI
│
├── dynamodb/                   # DynamoDB Service module (Flask Blueprint)
│   ├── __init__.py             # Exports dynamo_bp
│   ├── routes.py               # REST API endpoints with IAM permission support
│   └── storage.py              # Atomic JSON table storage manager
│
├── dynamodb_data/              # Host volume for DynamoDB JSON tables
├── storage/                    # Host volume for S3 bucket files
│
└── templates/                  # Frontend HTML Consoles
    ├── services.html           # Central AWS Management Console Services Directory
    ├── s3console.html          # S3 Management GUI
    ├── dynamodb.html           # DynamoDB Management GUI
    ├── iamconsole.html         # IAM Management GUI
    ├── landing.html            # Landing page
    ├── login.html              # Sign-in page
    ├── signup.html             # Account creation page
    └── coming_soon.html        # Preview page for upcoming modules (Lambda)
```

---

## 6. How to Run

### Main Unified Gateway Stack (S3, DynamoDB, Auth, Consoles):
```powershell
docker-compose down
docker-compose up -d --build
```
Open `http://localhost:4566` in your browser.

### EC2 Service:
```powershell
cd EC2
docker-compose up -d --build
```
Open `http://localhost:4567` in your browser.

### IAM Service:
```powershell
cd IAM
docker-compose up -d --build
```
Open `http://localhost:4568` in your browser.
