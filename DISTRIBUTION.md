# LocalAWS — Executable & Distribution Guide

## Overview

LocalAWS is packaged into a standalone Windows executable (`LocalAWS.exe`) to allow end users to launch the full local AWS emulation suite with a single double-click.

No manual Python installation, git cloning, or command line usage is required.

---

## End-User Prerequisites

1. **Docker Desktop for Windows**:
   - Must be installed and running on the target system.
   - Download link: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

> [!NOTE]
> If `LocalAWS.exe` is started while Docker Desktop is closed or missing, a dialog box will notify the user and automatically offer to open the Docker Desktop download page.

---

## User Execution Flow

1. Double-click `LocalAWS.exe`.
2. The **LocalAWS Launcher GUI** opens:
   - Verifies Docker Desktop daemon status.
   - Extracts and syncs required application files to `%LOCALAPPDATA%\LocalAWS_Runtime`.
   - Executes `docker compose up -d --build` to start all microservice containers (`gateway`, `s3`, `dynamodb`, `ec2`, `iam`, `lambda`, `db`, `iamdb`).
   - Polls `http://localhost:4566/api/health` until the gateway is ready.
   - Automatically opens your default web browser to `http://localhost:4566`.
3. **Controls**:
   - **Open Console**: Re-opens `http://localhost:4566` in browser.
   - **Start Stack**: Starts containers.
   - **Stop Stack**: Stops containers gracefully (`docker compose down`).
   - **Exit**: Prompts to gracefully stop containers before exiting.

---

## Developer Build Instructions

To re-package `LocalAWS.exe` from source:

### Prerequisites:
```powershell
pip install pyinstaller
```

### Build Command:
Run the build script from the repository root:
```powershell
python launcher/build.py
```

Or invoke PyInstaller CLI directly:
```powershell
pyinstaller --name=LocalAWS --onefile --noconsole --clean `
  --add-data "docker-compose.yaml;." `
  --add-data "Dockerfile;." `
  --add-data "app.py;." `
  --add-data "requirements.txt;." `
  --add-data "s3;s3" `
  --add-data "dynamodb;dynamodb" `
  --add-data "ec2;ec2" `
  --add-data "iam;iam" `
  --add-data "lambda;lambda" `
  --add-data "templates;templates" `
  --add-data "shared;shared" `
  launcher/main.py
```

The compiled single-file binary will be generated in `dist/LocalAWS.exe`.
