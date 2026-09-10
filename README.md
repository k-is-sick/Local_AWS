# LocalAWS — Self-Hosted Local Cloud Platform

A lightweight, modular, and self-hosted local emulation suite for Amazon Web Services (AWS) built from scratch using Python, Flask, PostgreSQL, and Docker.

---

## 🚀 Services & Port Mapping

| Service | Port | Description |
|---|---|---|
| **LocalAWS Hub & S3 / DynamoDB** | `4566` | Central login/auth, Services directory, S3 object storage, DynamoDB NoSQL engine, IAM proxy console |
| **EC2 Management Console** | `4567` | Docker-backed virtual machine simulator with live web terminal (`ttyd`) |
| **IAM Policy & Identity Engine** | `4568` | Policy evaluator, user accounts, and programmatic access key management |
| **PostgreSQL Database** | `5432` | Identity and state storage for `localaws` and `localawsiam` |

---

## 📁 Repository Structure

```
LocalAWS/
├── app.py                      # Main LocalAWS application entrypoint & gateway (:4566)
├── context.md                  # Comprehensive architectural specification
├── Dockerfile                  # LocalAWS container definition
├── docker-compose.yaml         # Multi-container orchestration (localaws + postgres)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git exclusion rules
├── .dockerignore               # Docker build context optimization
│
├── dynamodb/                   # DynamoDB Service module (Flask Blueprint)
│   ├── __init__.py             # Exports dynamo_bp
│   ├── routes.py               # REST API endpoints with IAM permission support
│   └── storage.py              # Atomic JSON table storage manager
│
├── templates/                  # Frontend Web Consoles
│   ├── services.html           # Central AWS Management Console Services Directory
│   ├── s3console.html          # S3 Management GUI
│   ├── dynamodb.html           # DynamoDB Management GUI
│   ├── iamconsole.html         # IAM Management GUI
│   ├── landing.html            # Public welcome & feature overview
│   ├── login.html              # Sign-in page
│   ├── signup.html             # Registration page
│   └── coming_soon.html        # Preview page for upcoming modules
│
├── EC2/                        # EC2 Service module (:4567)
│   ├── app.py                  # EC2 controller & container lifecycle manager
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   └── ttyd.Dockerfile
│
├── IAM/                        # IAM Service module (:4568)
│   ├── app.py                  # IAM policy evaluation engine & keys
│   ├── dockerfile
│   └── docker-compose.yaml
│
├── S3/                         # Standalone S3 module reference
│   ├── app.py
│   ├── dockerfile
│   └── docker-compose.yaml
│
├── docs/                       # Project Documentation & Reports
│   └── reports/                # Milestone reports for S3, Auth, DynamoDB, and EC2
│
├── dynamodb_data/              # Local storage for DynamoDB JSON tables
└── storage/                    # Local storage for S3 buckets and files
```

---

## ⚡ Quick Start

### 1. Start the Main Platform (Hub, S3, DynamoDB, Auth, Consoles)
```powershell
docker-compose up -d --build
```
Open **`http://localhost:4566`** in your browser.

### 2. Start IAM Identity & Policy Engine
```powershell
cd IAM
docker-compose up -d --build
```
Accessible at **`http://localhost:4568`** (or through `http://localhost:4566/iamconsole`).

### 3. Start EC2 Service & Terminal Engine
```powershell
cd EC2
docker-compose up -d --build
```
Accessible at **`http://localhost:4567`**.

---

## 🔒 Security & Authorization

All services support dual-mode access:
1. **Web Console**: Authenticated via browser session cookies (`session['user_email']`).
2. **Programmatic / API**: Authenticated via headers `X-Access-Key-Id` and `X-Secret-Key` verified against IAM policies.
