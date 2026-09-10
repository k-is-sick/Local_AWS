# Mini-EC2 (Local AWS EC2 Clone) — Project Report

## What We Did
Built a local clone of AWS EC2 using Docker, complete with a browser-based dashboard to launch, stop, start, and terminate "instances," plus a live web terminal (console access) for each running instance — mimicking the AWS EC2 console experience without needing real virtual machines.

## Why We Did It
Following the earlier Mini-S3 clone project, the goal was to extend the local "MiniStack" with an EC2-equivalent service: understand how cloud compute provisioning works under the hood by building it from primitives (Docker containers as instances) rather than using an existing emulator like LocalStack.

## How It Works
- Each **EC2 instance** = a Docker container (e.g. `alpine`, `ubuntu`) kept alive indefinitely
- Each instance gets a paired **ttyd web-terminal container**, which uses `docker exec` to attach a live shell session, exposed on an auto-assigned host port
- A Flask app (`app.py`) serves a simple HTML dashboard for launching/managing instances and exposes the Docker SDK (`docker-py`) to control containers
- "Console access" works by opening `http://localhost:<port>` for an instance, which loads a browser-based terminal connected to that container's shell
- All of this runs inside a `miniec2` container, which talks to the host Docker daemon via a mounted socket (`/var/run/docker.sock`) — letting a container spin up sibling containers

## Project Structure
```
EC2/
  app.py
  Dockerfile
  ttyd.Dockerfile
  docker-compose.yaml
```

## app.py (Final Version)
```python
from flask import Flask, request, jsonify, render_template_string
import docker, uuid

app = Flask(__name__)
client = docker.from_env()
client.images.build(path=".", dockerfile="ttyd.Dockerfile", tag="ttyd-docker")

INSTANCES = {}  # id -> {cid, tid, port}

PAGE = """
<h2>Mini-EC2 Console</h2>
<form action="/launch" method="post">
  <input name="image" value="alpine" placeholder="image">
  <button type="submit">Launch Instance</button>
</form>
<table border=1 cellpadding=5>
<tr><th>ID</th><th>State</th><th>Action</th></tr>
{% for i in instances %}
<tr>
  <td>{{i.id}}</td><td>{{i.state}}</td>
  <td>
    <a href="http://localhost:{{i.port}}" target="_blank">Console</a> |
    <a href="/stop/{{i.id}}">Stop</a> |
    <a href="/start/{{i.id}}">Start</a> |
    <a href="/terminate/{{i.id}}">Terminate</a>
  </td>
</tr>
{% endfor %}
</table>
"""

@app.route("/")
def dashboard():
    rows = []
    for iid, info in INSTANCES.items():
        c = client.containers.get(info["cid"])
        rows.append({"id": iid, "state": c.status, "port": info["port"]})
    return render_template_string(PAGE, instances=rows)

@app.route("/launch", methods=["POST"])
def launch():
    image = request.form.get("image", "alpine")
    iid = str(uuid.uuid4())[:8]

    c = client.containers.run(image, detach=True, tty=True, stdin_open=True,
                               command="sleep infinity", name=f"ec2-{iid}")
    term = client.containers.run(
        "ttyd-docker", detach=True, name=f"ttyd-{iid}",
        ports={"7681/tcp": None},
        command=f"ttyd -W docker exec -it ec2-{iid} sh",
        volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}}
    )
    term.reload()
    port = term.ports["7681/tcp"][0]["HostPort"]
    INSTANCES[iid] = {"cid": c.id, "tid": term.id, "port": port}
    return dashboard()

@app.route("/stop/<iid>")
def stop(iid):
    client.containers.get(INSTANCES[iid]["cid"]).stop()
    return dashboard()

@app.route("/start/<iid>")
def start(iid):
    client.containers.get(INSTANCES[iid]["cid"]).start()
    return dashboard()

@app.route("/terminate/<iid>")
def terminate(iid):
    info = INSTANCES.pop(iid)
    client.containers.get(info["cid"]).remove(force=True)
    client.containers.get(info["tid"]).remove(force=True)
    return dashboard()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4567)
```

## Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
COPY ttyd.Dockerfile .
RUN pip install flask docker
EXPOSE 4567
CMD ["python", "app.py"]
```

## ttyd.Dockerfile
```dockerfile
FROM tsl0922/ttyd:latest
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*
```

## docker-compose.yaml
```yaml
services:
  miniec2:
    build: .
    ports:
      - "4567:4567"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
```

## How To Run It
```powershell
docker-compose up -d --build   # build & start
docker ps                      # confirm it's running
```
Open the dashboard at: `http://localhost:4567`

## How To Use It
1. Enter an image name (e.g. `alpine`, `ubuntu`) in the dashboard form
2. Click **Launch Instance** — spins up a new container + paired terminal
3. Click **Console** next to any running instance to open a live browser shell
4. Use **Stop / Start / Terminate** to manage the instance lifecycle

## Issues Faced & Fixes

**1. `additional properties 'miniec2' not allowed`**
*Cause:* `docker-compose.yaml` was missing the parent `services:` key, or `miniec2` wasn't indented under it.
*Fix:* ensured proper YAML structure with `services:` at column 0 and 2-space indentation.

**2. Wrong build context path**
*Cause:* `build: ./ec2` pointed to a nonexistent subfolder since the EC2 project files were placed directly in the project root.
*Fix:* changed to `build: .` matching the actual folder layout.

**3. JSON body not parsing in curl (PowerShell)**
*Cause:* PowerShell quote escaping mangled the JSON payload.
*Fix:* used proper escaped quotes or single-quoted JSON in `curl.exe` calls.

**4. `port is already allocated` (port 7700 stuck)**
*Cause:* a stale Docker Desktop port-forwarding process held port 7700 on the Windows host even after containers using it were removed.
*Fix:* stopped hardcoding ports entirely — used `ports={"7681/tcp": None}` so Docker auto-assigns a free host port for each instance's terminal, avoiding all future port collisions.

**5. Accidentally deleted the running app container**
*Cause:* a cleanup command `docker rm -f $(docker ps -aq --filter "name=ec2-")` matched `ec2-miniec2-1` in addition to the intended `ec2-<instance>` containers, since the filter substring overlapped.
*Fix:* rebuilt with `docker-compose up -d --build` — no data loss since instances are disposable by design.

**6. `failed to connect to the docker API ... dockerDesktopLinuxEngine`**
*Cause:* Docker Desktop itself wasn't running.
*Fix:* started Docker Desktop manually and waited for "Engine running" before retrying compose commands.

**7. Console stuck on "Reconnecting..." loop**
*Cause (two-part):*
- ttyd was opened without the `-W` (writable) flag, making sessions read-only and unstable
- the instance container's default process (e.g. Alpine's shell) exited immediately since nothing was keeping it alive, killing the `docker exec` session ttyd depended on
*Fix:* added `-W` to the ttyd command, and changed instance containers to run `sleep infinity` as their main process so they stay alive indefinitely.

**8. No working CLI shown in the console (still reconnecting)**
*Cause:* the official `tsl0922/ttyd` image does not include the `docker` CLI, so its `docker exec ...` command failed instantly every time.
*Fix:* created a custom `ttyd.Dockerfile` that installs `docker-cli` (initially attempted via `apk`, which failed since the base image is Debian-based, not Alpine — corrected to `apt-get install docker.io`) and built it as a custom image (`ttyd-docker`) used for every terminal container.

**9. `Cannot locate specified Dockerfile: ttyd.Dockerfile`**
*Cause:* `ttyd.Dockerfile` existed on the host but wasn't copied into the `miniec2` container, so the in-container build call couldn't find it.
*Fix:* added `COPY ttyd.Dockerfile .` to the main `Dockerfile`.

**10. `docker-compose down` didn't stop instance/terminal containers**
*Cause:* `ec2-*` and `ttyd-*` containers were created dynamically via the Docker SDK, not declared in compose, so compose has no knowledge of them.
*Fix:* clean them up manually with a filtered `docker rm -f` when needed; understood as expected behavior, not a bug.

## Final State
A working browser-based Mini-EC2 dashboard: launch any Docker image as an "instance," get an auto-assigned live web terminal for console access, and manage instance lifecycle (start/stop/terminate) — all running locally without real virtualization.

---

# How-To Guide (For a New Person)

### 1. Prerequisites
- Docker Desktop installed and running (confirm "Engine running" status)
- Windows: use PowerShell; always call `curl.exe` explicitly (not the `curl` alias)

### 2. Folder Setup
Create this structure:
```
EC2/
  app.py
  Dockerfile
  ttyd.Dockerfile
  docker-compose.yaml
```
Paste in the final file contents shown above.

### 3. Build & Run
```powershell
cd EC2
docker-compose up -d --build
```
Check it started:
```powershell
docker ps
```

### 4. Use the Dashboard
Open a browser: `http://localhost:4567`
- Type an image name (`alpine`, `ubuntu`, etc.) and click **Launch Instance**
- Click **Console** to get a live terminal inside that instance
- Use **Stop / Start / Terminate** as needed

### 5. Cleaning Up
Compose only manages the `miniec2` app container. Instances and terminals are created dynamically and must be cleaned manually:
```powershell
docker rm -f $(docker ps -aq --filter "name=ttyd-")
docker rm -f $(docker ps -aq --filter "name=ec2-instance-id-here")
```
⚠️ Be precise with filters — a broad filter like `name=ec2-` can also match the app container `ec2-miniec2-1` and delete it by accident.

### 6. Common Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| `port already allocated` | Stale port binding on host | Use `ports={"X/tcp": None}` for auto-assignment |
| Console stuck reconnecting | ttyd missing `-W` flag, or container's main process exited | Add `-W`; run instance with `sleep infinity` |
| No CLI / instant reconnect | `docker` CLI missing inside ttyd image | Use custom `ttyd.Dockerfile` with `docker.io` installed |
| `Cannot connect to docker API` | Docker Desktop not running | Start Docker Desktop, wait for it to fully load |
| `docker-compose down` doesn't remove instances | SDK-created containers aren't tracked by compose | Clean up manually via `docker rm -f` |

### 7. Key Concept to Remember
This is **not** real virtualization — instances are Docker containers, not VMs. It's a lightweight, fast way to simulate EC2-like provisioning and console access locally. For true VM-level isolation (closer to real EC2), a future iteration would need QEMU/KVM + noVNC instead of Docker containers + ttyd.

---

# Mini-S3 + Mini-EC2 Integration Report

## What We Did
Connected the Mini-S3 and Mini-EC2 services together so that an EC2 instance (a running container) can talk to the S3 service (another container) over an internal network — just like a real AWS EC2 instance accessing an S3 bucket.

## Why We Did It
By default, Docker containers are isolated from each other unless explicitly connected. Two separate `docker-compose` projects (S3 and EC2) each create their own private networks, so they can't see each other. We fixed this by putting both on a shared Docker network.

## How It Works
Think of it like this: both services are now on the same "LAN." Inside that LAN, containers find each other by name (e.g. `minis3`) instead of IP address — Docker handles the DNS automatically. So from inside an EC2 instance's terminal you can type `curl http://minis3:4566/` and it just works.

## What We Changed

**S3 `docker-compose.yaml`** — added a named shared network:
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
    networks:
      - ministack

networks:
  ministack:
    name: ministack
```

**EC2 `docker-compose.yaml`** — joined the same network (marked `external: true` because S3 creates it):
```yaml
services:
  miniec2:
    build: .
    ports:
      - "4567:4567"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
    networks:
      - ministack

networks:
  ministack:
    name: ministack
    external: true
```

**EC2 `app.py`** — added `network="ministack"` when launching instances so they also join the shared network:
```python
c = client.containers.run(image, detach=True, tty=True, stdin_open=True,
                           command="sleep infinity", name=f"ec2-{iid}",
                           network="ministack")
```

## How To Start Everything
Always start S3 first — it creates the shared network:
```powershell
cd D:\Local_AWS\S3
docker-compose up -d --build

cd D:\Local_AWS\EC2
docker-compose up -d --build
```

## How To Use It
1. Open `http://localhost:4567` — EC2 dashboard
2. Launch an instance (e.g. Alpine)
3. Click **Open Console**
4. Install curl (Alpine doesn't have it by default):
   ```sh
   apk add curl
   ```
5. Talk to S3 from inside the EC2 instance:
   ```sh
   curl http://minis3:4566/                                      # list buckets
   curl -X PUT http://minis3:4566/mybucket                       # create bucket
   curl -X PUT http://minis3:4566/mybucket/hi.txt \
     -H "Content-Type: application/octet-stream" \
     --data-binary "hello from ec2"                              # upload file
   curl http://minis3:4566/mybucket/hi.txt                       # download file
   ```

## How To Stop Everything
```powershell
cd D:\Local_AWS\EC2
docker rm -f $(docker ps -aq --filter "name=ttyd-")
docker rm -f $(docker ps -aq --filter "name=ec2-")
docker-compose down

cd D:\Local_AWS\S3
docker-compose down
```

## Issues Faced & Fixes

**1. EC2 instances couldn't reach Mini-S3**
*Cause:* each compose project creates its own isolated network by default.
*Fix:* created a named shared network (`ministack`) in S3's compose file, and joined it as `external: true` in EC2's compose file. Also passed `network="ministack"` when launching instance containers via the SDK.

**2. `curl` not found inside Alpine instance**
*Cause:* Alpine is a ~5MB minimal image with almost nothing pre-installed.
*Fix:* `apk add curl` inside the console before making requests. Alternatively launch with `ubuntu` or `python:3.11-slim` images which have more tools available.

## Key Concept
`minis3` in the curl URL is the Docker **container name**, not a hostname you configured manually. Docker's internal DNS automatically resolves container names to their IP addresses within the same network — this is exactly how microservices talk to each other in real AWS (e.g. ECS containers on the same VPC).