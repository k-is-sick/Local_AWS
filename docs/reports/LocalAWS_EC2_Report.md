# LocalAWS — EC2 Service: Project Report

## What We Did
Built an interactive compute emulation engine that uses local Docker containers as virtual instances. Includes an embedded terminal emulator (`ttyd`) per instance, allowing direct shell execution inside instances from a browser console.

## Architecture & Workflow
- **Python Docker SDK**: Runs instances in isolated containers (e.g. `alpine`, `ubuntu`) attached to the `localaws` network.
- **Web Terminal**: Launches a lightweight `ttyd-docker` proxy container for each instance on a dynamic host port.
- **IAM Permission Control**: Evaluates incoming requests carrying `X-Access-Key-Id` against the IAM service.

## Endpoints & Console
- **Web Console**: `http://localhost:4567`
- **Instance Actions**: `/launch`, `/stop/<id>`, `/start/<id>`, `/terminate/<id>`.
- **Navigation**: Top navigation bar links to the central LocalAWS Services Hub (`http://localhost:4566/services`).
