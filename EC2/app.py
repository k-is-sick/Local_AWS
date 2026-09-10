from flask import Flask, request, jsonify, render_template_string
import docker, uuid, requests
from functools import wraps

app = Flask(__name__)
client = docker.from_env()
client.images.build(path=".", dockerfile="ttyd.Dockerfile", tag="ttyd-docker")
INSTANCES = {}  # id -> {container_id, ttyd_port}

IAM_URL = "http://miniiam:4568"

def require_permission(action, resource_fn):
    """
    EC2 has no session/login system, so when no API-key headers are present
    the request just proceeds (same as current behavior). Only requests
    carrying X-Access-Key-Id / X-Secret-Key get checked against IAM.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            akid = request.headers.get("X-Access-Key-Id")
            secret = request.headers.get("X-Secret-Key")
            if akid and secret:
                resource = resource_fn(request)
                try:
                    resp = requests.post(f"{IAM_URL}/api/iam/authorize", json={
                        "access_key_id": akid, "secret_key": secret,
                        "action": action, "resource": resource,
                    }, timeout=3)
                    data = resp.json()
                except requests.RequestException:
                    return jsonify({"error": "IAM service unreachable"}), 503
                if not data.get("allowed"):
                    return jsonify({"error": "access denied"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>EC2 Management Console</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: "Amazon Ember", Arial, sans-serif; }
    body { background: #f2f3f3; color: #16191f; font-size: 14px; }

    /* Top nav */
    .topnav {
      background: #232f3e; height: 36px; display: flex; align-items: center;
      padding: 0 16px; gap: 24px;
    }
    .topnav .logo { color: #ff9900; font-weight: bold; font-size: 16px; letter-spacing: 1px; }
    .topnav span { color: #ccc; font-size: 13px; }

    /* Second bar */
    .subnav {
      background: #1a2130; height: 32px; display: flex; align-items: center;
      padding: 0 16px; gap: 20px;
    }
    .subnav a {
      color: #d5dbdb; font-size: 13px; text-decoration: none; padding: 4px 8px;
      border-radius: 3px;
    }
    .subnav a.active { background: #3b4a60; color: #fff; }

    /* Main content */
    .main { padding: 20px 24px; }

    /* Breadcrumb */
    .breadcrumb { font-size: 12px; color: #545b64; margin-bottom: 12px; }
    .breadcrumb a { color: #0073bb; text-decoration: none; }

    /* Page header */
    .page-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 16px;
    }
    .page-header h1 { font-size: 20px; font-weight: 400; color: #16191f; }
    .page-header .count { font-size: 13px; color: #545b64; margin-left: 8px; }

    /* Buttons */
    .btn {
      padding: 6px 16px; border: none; border-radius: 3px; cursor: pointer;
      font-size: 13px; font-weight: 500;
    }
    .btn-primary { background: #ec7211; color: #fff; }
    .btn-primary:hover { background: #d45e00; }
    .btn-secondary {
      background: #fff; color: #16191f; border: 1px solid #aab7b8;
    }
    .btn-secondary:hover { background: #f2f3f3; }
    .btn-danger { background: #fff; color: #d13212; border: 1px solid #d13212; }
    .btn-danger:hover { background: #fdf3f1; }
    .btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .btn-group { display: flex; gap: 8px; }

    /* Filter bar */
    .filterbar {
      background: #fff; border: 1px solid #d5dbdb; border-radius: 4px;
      padding: 10px 14px; display: flex; align-items: center; gap: 10px;
      margin-bottom: 12px;
    }
    .filterbar input {
      border: none; outline: none; font-size: 13px; flex: 1; color: #16191f;
    }
    .filterbar .icon { color: #879596; }

    /* Table */
    .table-wrap {
      background: #fff; border: 1px solid #d5dbdb; border-radius: 4px;
      overflow: hidden;
    }
    .table-toolbar {
      padding: 10px 14px; border-bottom: 1px solid #eaeded;
      display: flex; justify-content: space-between; align-items: center;
    }
    .table-toolbar span { font-size: 13px; font-weight: 600; color: #16191f; }
    table { width: 100%; border-collapse: collapse; }
    thead { background: #fafafa; }
    th {
      padding: 10px 14px; text-align: left; font-size: 12px; font-weight: 600;
      color: #545b64; border-bottom: 1px solid #eaeded; white-space: nowrap;
    }
    td {
      padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #f2f3f3;
      vertical-align: middle;
    }
    tr:hover td { background: #f8f9fa; }
    tr.selected td { background: #f0f7ff; }

    /* State badges */
    .state { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 500; }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .dot-running { background: #1d8102; }
    .dot-stopped { background: #879596; }
    .dot-pending { background: #f89c24; }
    .state-running { color: #1d8102; }
    .state-stopped { color: #545b64; }
    .state-pending { color: #f89c24; }

    /* Instance ID link */
    .iid-link { color: #0073bb; text-decoration: none; font-family: monospace; font-size: 13px; }
    .iid-link:hover { text-decoration: underline; }

    /* Console link */
    .console-btn {
      color: #0073bb; text-decoration: none; font-size: 12px;
      border: 1px solid #0073bb; padding: 3px 10px; border-radius: 3px;
    }
    .console-btn:hover { background: #f0f7ff; }

    /* Action links */
    .action-link { color: #0073bb; text-decoration: none; font-size: 12px; margin-right: 10px; }
    .action-link:hover { text-decoration: underline; }
    .action-link.danger { color: #d13212; }

    /* Modal */
    .modal-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.5); z-index: 100;
      justify-content: center; align-items: center;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: #fff; border-radius: 4px; width: 480px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .modal-header {
      padding: 16px 20px; border-bottom: 1px solid #eaeded;
      display: flex; justify-content: space-between; align-items: center;
    }
    .modal-header h2 { font-size: 16px; font-weight: 600; }
    .modal-close { cursor: pointer; color: #545b64; font-size: 18px; background: none; border: none; }
    .modal-body { padding: 20px; }
    .form-field { margin-bottom: 16px; }
    .form-field label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
    .form-field input, .form-field select {
      width: 100%; padding: 8px 10px; border: 1px solid #aab7b8;
      border-radius: 3px; font-size: 13px;
    }
    .form-field input:focus, .form-field select:focus {
      outline: none; border-color: #0073bb;
      box-shadow: 0 0 0 2px rgba(0,115,187,0.2);
    }
    .form-hint { font-size: 11px; color: #545b64; margin-top: 4px; }
    .modal-footer {
      padding: 14px 20px; border-top: 1px solid #eaeded;
      display: flex; justify-content: flex-end; gap: 10px;
    }

    /* Empty state */
    .empty {
      text-align: center; padding: 60px 20px; color: #545b64;
    }
    .empty h3 { font-size: 16px; margin-bottom: 8px; font-weight: 500; }
    .empty p { font-size: 13px; }

    /* Summary bar */
    .summary { display: flex; gap: 20px; margin-bottom: 16px; }
    .summary-card {
      background: #fff; border: 1px solid #d5dbdb; border-radius: 4px;
      padding: 12px 20px; flex: 1;
    }
    .summary-card .label { font-size: 12px; color: #545b64; margin-bottom: 4px; }
    .summary-card .value { font-size: 22px; font-weight: 400; color: #16191f; }
    .summary-card .value.green { color: #1d8102; }
    .summary-card .value.grey { color: #879596; }

    /* Checkbox */
    .checkbox-col { width: 32px; }
  </style>
</head>
<body>

<!-- Top nav -->
<div class="topnav">
  <a href="http://localhost:4566/services" class="logo" style="text-decoration:none;">&#9827; AWS</a>
  <a href="http://localhost:4566/services" style="color:#fff; text-decoration:none; font-size:13px; font-weight:500; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
    <span style="font-size:14px;">&#9776;</span> Services
  </a>
  <span style="cursor:default;">&#128269;</span>
  <span style="margin-left:auto; color:#ccc; font-size:12px;">LocalAWS Local Console</span>
</div>
<div class="subnav">
  <a href="#" class="active">EC2</a>
  <a href="#">Instances</a>
  <a href="#">Images (AMIs)</a>
  <a href="#">Security Groups</a>
</div>

<!-- Main -->
<div class="main">
  <div class="breadcrumb">
    <a href="#">EC2</a> &rsaquo; <a href="#">Instances</a> &rsaquo; Instances
  </div>

  <div class="page-header">
    <div>
      <span style="font-size:20px; font-weight:400;">Instances</span>
      <span class="count">({{ instances|length }})</span>
    </div>
    <div class="btn-group">
      <button class="btn btn-secondary" onclick="location.reload()">&#8635; Refresh</button>
      <button class="btn btn-primary" onclick="document.getElementById('launchModal').classList.add('open')">
        Launch instance
      </button>
    </div>
  </div>

  <!-- Summary -->
  <div class="summary">
    <div class="summary-card">
      <div class="label">Total instances</div>
      <div class="value">{{ instances|length }}</div>
    </div>
    <div class="summary-card">
      <div class="label">Running</div>
      <div class="value green">{{ instances|selectattr('state','equalto','running')|list|length }}</div>
    </div>
    <div class="summary-card">
      <div class="label">Stopped</div>
      <div class="value grey">{{ instances|selectattr('state','equalto','exited')|list|length }}</div>
    </div>
    <div class="summary-card">
      <div class="label">Region</div>
      <div class="value" style="font-size:14px; margin-top:4px;">local-docker-1</div>
    </div>
  </div>

  <!-- Filter -->
  <div class="filterbar">
    <span class="icon">&#128269;</span>
    <input type="text" id="searchBox" placeholder="Filter instances..." oninput="filterTable()">
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <div class="table-toolbar">
      <span>Instances</span>
      <div class="btn-group">
        <button class="btn btn-secondary" style="font-size:12px; padding:4px 10px;">&#8801; Columns</button>
      </div>
    </div>
    <table id="instanceTable">
      <thead>
        <tr>
          <th class="checkbox-col"><input type="checkbox"></th>
          <th>Instance ID</th>
          <th>Instance state</th>
          <th>Image (AMI)</th>
          <th>Instance type</th>
          <th>Console</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% if instances %}
          {% for i in instances %}
          <tr>
            <td><input type="checkbox"></td>
            <td><a class="iid-link" href="#">i-{{ i.id }}</a></td>
            <td>
              {% if i.state == 'running' %}
                <span class="state state-running">
                  <span class="dot dot-running"></span> Running
                </span>
              {% elif i.state == 'exited' %}
                <span class="state state-stopped">
                  <span class="dot dot-stopped"></span> Stopped
                </span>
              {% else %}
                <span class="state state-pending">
                  <span class="dot dot-pending"></span> {{ i.state }}
                </span>
              {% endif %}
            </td>
            <td>{{ i.image }}</td>
            <td><span style="color:#545b64;">docker.nano</span></td>
            <td>
              {% if i.state == 'running' %}
                <a class="console-btn" href="http://localhost:{{ i.port }}" target="_blank">
                  &#9654; Open console
                </a>
              {% else %}
                <span style="color:#aab7b8; font-size:12px;">— unavailable</span>
              {% endif %}
            </td>
            <td>
              {% if i.state == 'running' %}
                <a class="action-link" href="/stop/{{ i.id }}">Stop</a>
              {% else %}
                <a class="action-link" href="/start/{{ i.id }}">Start</a>
              {% endif %}
              <a class="action-link danger" href="/terminate/{{ i.id }}"
                 onclick="return confirm('Terminate instance i-{{ i.id }}?')">Terminate</a>
            </td>
          </tr>
          {% endfor %}
        {% else %}
          <tr>
            <td colspan="7">
              <div class="empty">
                <h3>No instances found</h3>
                <p>Launch an instance to get started.</p>
              </div>
            </td>
          </tr>
        {% endif %}
      </tbody>
    </table>
  </div>
</div>

<!-- Launch Modal -->
<div class="modal-overlay" id="launchModal">
  <div class="modal">
    <div class="modal-header">
      <h2>Launch an instance</h2>
      <button class="modal-close" onclick="document.getElementById('launchModal').classList.remove('open')">&#x2715;</button>
    </div>
    <form action="/launch" method="post">
      <div class="modal-body">
        <div class="form-field">
          <label>Amazon Machine Image (AMI)</label>
          <select name="image">
            <option value="alpine">Alpine Linux (alpine)</option>
            <option value="ubuntu">Ubuntu (ubuntu)</option>
            <option value="debian">Debian (debian)</option>
            <option value="python:3.11-slim">Python 3.11 Slim</option>
            <option value="node:20-alpine">Node.js 20 Alpine</option>
          </select>
          <div class="form-hint">Selects the Docker image used as the base OS for this instance.</div>
        </div>
        <div class="form-field">
          <label>Instance type</label>
          <input type="text" value="docker.nano" disabled style="background:#f2f3f3; color:#545b64;">
          <div class="form-hint">All local instances are docker.nano (single container).</div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary"
          onclick="document.getElementById('launchModal').classList.remove('open')">Cancel</button>
        <button type="submit" class="btn btn-primary">Launch instance</button>
      </div>
    </form>
  </div>
</div>

<script>
  function filterTable() {
    const q = document.getElementById('searchBox').value.toLowerCase();
    document.querySelectorAll('#instanceTable tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  }
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    rows = []
    for iid, info in INSTANCES.items():
        c = client.containers.get(info["cid"])
        rows.append({"id": iid, "state": c.status, "port": info["port"],  "image": info.get("image","unknown")})
    return render_template_string(PAGE, instances=rows)

@app.route("/launch", methods=["POST"])
@require_permission("ec2:RunInstance", lambda r: "arn:localaws:ec2:::instance/*")
def launch():
    image = request.form.get("image", "alpine")
    iid = str(uuid.uuid4())[:8]

    c = client.containers.run(image, detach=True, tty=True, stdin_open=True,  command="sleep infinity",  name=f"ec2-{iid}",  network="localaws")
    term = client.containers.run(
        "ttyd-docker", detach=True, name=f"ttyd-{iid}",
        ports={"7681/tcp": None},
        command=f"ttyd -W docker exec -it ec2-{iid} sh",
        volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}}
    )
    term.reload()
    port = term.ports["7681/tcp"][0]["HostPort"]
    INSTANCES[iid] = {"cid": c.id, "tid": term.id, "port": port, "image": image}
    return dashboard()

@app.route("/stop/<iid>")
@require_permission("ec2:StopInstance", lambda r: f"arn:localaws:ec2:::instance/{r.view_args['iid']}")
def stop(iid):
    client.containers.get(INSTANCES[iid]["cid"]).stop()
    return dashboard()

@app.route("/start/<iid>")
@require_permission("ec2:StartInstance", lambda r: f"arn:localaws:ec2:::instance/{r.view_args['iid']}")
def start(iid):
    client.containers.get(INSTANCES[iid]["cid"]).start()
    return dashboard()

@app.route("/terminate/<iid>")
@require_permission("ec2:TerminateInstance", lambda r: f"arn:localaws:ec2:::instance/{r.view_args['iid']}")
def terminate(iid):
    info = INSTANCES.pop(iid)
    client.containers.get(info["cid"]).remove(force=True)
    client.containers.get(info["tid"]).remove(force=True)
    return dashboard()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4567)