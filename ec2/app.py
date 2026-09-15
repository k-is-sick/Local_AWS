from flask import Flask, request, jsonify, render_template_string
import docker, uuid, requests
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared import require_permission, arn_ec2

app = Flask(__name__)
client = docker.from_env()
client.images.build(path=".", dockerfile="ttyd.Dockerfile", tag="ttyd-docker")
INSTANCES = {}  # id -> {container_id, ttyd_port}


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EC2 Compute - LocalAWS Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
  <style>
    /* LOCKED DESIGN SYSTEM TOKENS */
    :root {
      --bg-main: #0e1117;
      --bg-surface: #161b22;
      --bg-surface-hover: #1c2129;
      --bg-card: #13171f;
      --border-default: #2e3745;
      --border-subtle: #242b35;
      --border-focus: #ff9900;
      
      --text-main: #d6dde5;
      --text-muted: #8b94a3;
      --text-dim: #5c6575;
      
      --accent-orange: #ff9900;
      --accent-orange-hover: #e68a00;
      
      --status-running: #3fb950;
      --status-running-bg: rgba(63, 185, 80, 0.12);
      
      --status-checking: #d29922;
      --status-checking-bg: rgba(210, 153, 34, 0.12);
      
      --status-stopped: #f85149;
      --status-stopped-bg: rgba(248, 81, 73, 0.12);
      
      --status-muted: #8b94a3;
      --status-muted-bg: rgba(139, 148, 163, 0.12);

      --radius-sm: 2px;
      --radius-md: 4px;
      --radius-lg: 6px;

      --font-sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --font-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-main);
      color: var(--text-main);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      -webkit-font-smoothing: antialiased;
    }

    a { color: inherit; text-decoration: none; }

    /* TOP IDENTITY BAR */
    .top-header {
      height: 48px;
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-default);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand-group { display: flex; align-items: center; gap: 12px; }

    .brand-logo {
      width: 22px; height: 22px; background: #090c10;
      border: 1px solid #d97706; border-radius: var(--radius-sm);
      display: flex; align-items: center; justify-content: center;
      font-family: var(--font-mono); font-weight: 700; font-size: 13px;
      color: var(--accent-orange); line-height: 1;
    }

    .brand-wordmark {
      font-size: 14px; font-weight: 600; color: #fff;
      letter-spacing: -0.2px; display: flex; align-items: center; gap: 8px;
    }

    .brand-badge {
      font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);
      background: rgba(255, 255, 255, 0.05); padding: 2px 6px;
      border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);
    }

    .nav-breadcrumb {
      display: flex; align-items: center; gap: 8px; font-size: 13px;
      color: var(--text-muted); margin-left: 8px; padding-left: 12px;
      border-left: 1px solid var(--border-subtle);
    }

    .nav-breadcrumb a {
      color: var(--text-muted); transition: color 0.15s ease;
      display: flex; align-items: center; gap: 5px;
    }

    .nav-breadcrumb a:hover { color: var(--accent-orange); }
    .nav-breadcrumb .separator { color: var(--text-dim); font-size: 11px; }
    .nav-breadcrumb .current { color: var(--text-main); font-weight: 500; }

    .header-right { display: flex; align-items: center; gap: 16px; }

    .service-chip-ec2 {
      font-family: var(--font-mono); font-size: 11px; font-weight: 600;
      color: #ff9900; background: rgba(255, 153, 0, 0.12);
      border: 1px solid rgba(255, 153, 0, 0.3); padding: 2px 6px;
      border-radius: var(--radius-sm); letter-spacing: 0.5px;
    }

    .daemon-indicator {
      display: flex; align-items: center; gap: 6px;
      font-family: var(--font-mono); font-size: 11.5px; color: var(--text-muted);
    }

    .pulse-dot {
      width: 7px; height: 7px; border-radius: 50%; background: var(--status-running);
      box-shadow: 0 0 6px rgba(63, 185, 80, 0.6);
    }

    .btn-signout {
      font-family: var(--font-sans); font-size: 12px; color: var(--text-muted);
      background: transparent; border: 1px solid var(--border-default);
      padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer;
      transition: all 0.15s ease;
    }

    .btn-signout:hover {
      color: var(--text-main); border-color: var(--text-muted);
      background: var(--bg-surface-hover);
    }

    /* MAIN CONTAINER */
    .main-content {
      flex: 1; max-width: 1440px; width: 100%; margin: 0 auto;
      padding: 24px 32px 48px;
    }

    /* PAGE HEADER TITLE BAR */
    .page-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px;
    }

    .title-area { display: flex; align-items: baseline; gap: 12px; }

    .page-title {
      font-size: 20px; font-weight: 600; color: #fff; letter-spacing: -0.3px;
      display: flex; align-items: center; gap: 10px;
    }

    .instance-counter {
      font-family: var(--font-mono); font-size: 13px; font-weight: 500;
      color: var(--text-muted); background: var(--bg-surface);
      border: 1px solid var(--border-default); padding: 2px 8px;
      border-radius: var(--radius-sm);
    }

    .page-subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
    .action-group { display: flex; align-items: center; gap: 10px; }

    .btn {
      display: inline-flex; align-items: center; justify-content: center;
      gap: 6px; font-family: var(--font-sans); font-size: 12.5px; font-weight: 500;
      padding: 7px 14px; border-radius: var(--radius-sm); cursor: pointer;
      transition: all 0.15s ease; border: 1px solid transparent; text-decoration: none;
    }

    .btn-primary {
      background-color: var(--accent-orange); color: #0e1117; font-weight: 600;
      border-color: var(--accent-orange);
    }

    .btn-primary:hover {
      background-color: var(--accent-orange-hover);
      border-color: var(--accent-orange-hover);
    }

    .btn-ghost {
      background: transparent; color: var(--text-main);
      border: 1px solid var(--border-default);
    }

    .btn-ghost:hover {
      background: var(--bg-surface-hover); border-color: var(--text-muted);
    }

    /* SUMMARY STRIP */
    .summary-strip {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
      margin-bottom: 24px;
    }

    .metric-card {
      background-color: var(--bg-card); border: 1px solid var(--border-default);
      border-radius: var(--radius-md); padding: 14px 18px;
      transition: border-color 0.15s ease;
    }

    .metric-card:hover { border-color: #3b4657; }

    .metric-label {
      font-size: 11.5px; font-weight: 500; text-transform: uppercase;
      letter-spacing: 0.6px; color: var(--text-muted); margin-bottom: 6px;
      display: flex; align-items: center; justify-content: space-between;
    }

    .metric-value {
      font-family: var(--font-mono); font-size: 22px; font-weight: 600;
      color: var(--text-main); line-height: 1.2;
    }

    .metric-value.running { color: var(--status-running); }
    .metric-value.stopped { color: var(--text-dim); }
    .metric-value.region { font-size: 15px; color: var(--text-main); padding-top: 5px; }

    /* TABLE TOOLBAR */
    .table-toolbar {
      background-color: var(--bg-surface); border: 1px solid var(--border-default);
      border-bottom: none; border-radius: var(--radius-md) var(--radius-md) 0 0;
      padding: 12px 16px; display: flex; align-items: center;
      justify-content: space-between; gap: 16px;
    }

    .search-wrapper { position: relative; width: 320px; }

    .search-icon {
      position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
      color: var(--text-muted); pointer-events: none;
    }

    .search-input {
      width: 100%; height: 32px; background-color: #0e1117;
      border: 1px solid var(--border-default); border-radius: var(--radius-sm);
      color: var(--text-main); font-family: var(--font-sans); font-size: 12.5px;
      padding: 0 12px 0 32px; outline: none; transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .search-input:focus {
      border-color: var(--border-focus); box-shadow: 0 0 0 1px var(--border-focus);
    }

    .search-input::placeholder { color: var(--text-dim); }

    .table-tools { display: flex; align-items: center; gap: 10px; }

    .btn-icon {
      height: 32px; padding: 0 10px; background: transparent;
      border: 1px solid var(--border-default); border-radius: var(--radius-sm);
      color: var(--text-muted); font-size: 12px; display: inline-flex;
      align-items: center; gap: 6px; cursor: pointer;
    }

    .btn-icon:hover {
      background: var(--bg-surface-hover); color: var(--text-main);
      border-color: #3b4657;
    }

    /* DATA TABLE */
    .data-table-wrap {
      background-color: var(--bg-surface); border: 1px solid var(--border-default);
      border-radius: 0 0 var(--radius-md) var(--radius-md); overflow-x: auto;
    }

    .data-table {
      width: 100%; border-collapse: collapse; text-align: left; font-size: 12.5px;
    }

    .data-table th {
      background-color: #12161d; color: var(--text-muted); font-weight: 600;
      font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px;
      padding: 10px 14px; border-bottom: 1px solid var(--border-default);
      white-space: nowrap; user-select: none;
    }

    .data-table td {
      padding: 11px 14px; border-bottom: 1px solid var(--border-subtle);
      color: var(--text-main); vertical-align: middle; white-space: nowrap;
    }

    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:hover td { background-color: var(--bg-surface-hover); }

    .cell-checkbox { width: 36px; padding-right: 4px !important; text-align: center; }

    input[type="checkbox"] {
      appearance: none; -webkit-appearance: none; width: 14px; height: 14px;
      background: #0e1117; border: 1px solid var(--border-default);
      border-radius: var(--radius-sm); outline: none; cursor: pointer;
      display: inline-grid; place-content: center; margin: 0; vertical-align: middle;
    }

    input[type="checkbox"]:checked {
      background: var(--accent-orange); border-color: var(--accent-orange);
    }

    input[type="checkbox"]:checked::before {
      content: ""; width: 7px; height: 4px; border-left: 1.5px solid #0e1117;
      border-bottom: 1.5px solid #0e1117; transform: rotate(-45deg) translate(0.5px, -0.5px);
    }

    .instance-id-link {
      font-family: var(--font-mono); font-size: 12.5px; font-weight: 500;
      color: var(--accent-orange); transition: color 0.15s ease, text-decoration 0.15s ease;
    }

    .instance-id-link:hover { text-decoration: underline; color: #ffaa22; }

    .status-pill {
      display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px;
      border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 11px;
      font-weight: 500; line-height: 1; text-transform: uppercase; letter-spacing: 0.4px;
    }

    .status-pill .dot { width: 6px; height: 6px; border-radius: 50%; }

    .status-pill.running {
      color: var(--status-running); background: var(--status-running-bg);
      border: 1px solid rgba(63, 185, 80, 0.25);
    }
    .status-pill.running .dot { background: var(--status-running); box-shadow: 0 0 4px var(--status-running); }

    .status-pill.stopped {
      color: var(--status-muted); background: var(--status-muted-bg);
      border: 1px solid rgba(139, 148, 163, 0.2);
    }
    .status-pill.stopped .dot { background: var(--text-dim); }

    .status-pill.pending {
      color: var(--status-checking); background: var(--status-checking-bg);
      border: 1px solid rgba(210, 153, 34, 0.25);
    }
    .status-pill.pending .dot { background: var(--status-checking); box-shadow: 0 0 4px var(--status-checking); }

    .mono-cell { font-family: var(--font-mono); font-size: 12px; color: #c0c8d4; }

    .ami-badge { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 12px; color: var(--text-main); }

    .ami-tag {
      font-size: 10px; text-transform: uppercase; padding: 1px 4px;
      border-radius: var(--radius-sm); background: #202632;
      border: 1px solid var(--border-subtle); color: var(--text-muted);
    }

    .console-link-active {
      display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
      font-weight: 500; color: #58a6ff; transition: color 0.15s ease;
    }

    .console-link-active:hover { color: #79b8ff; text-decoration: underline; }

    .console-unavailable { font-size: 12px; color: var(--text-dim); font-style: italic; }

    .actions-cell { display: flex; align-items: center; gap: 12px; }

    .action-link { font-size: 12px; font-weight: 500; transition: color 0.15s ease; cursor: pointer; }
    .action-link-start { color: var(--status-running); }
    .action-link-start:hover { text-decoration: underline; color: #56d364; }
    .action-link-stop { color: #f0883e; }
    .action-link-stop:hover { text-decoration: underline; color: #ffa657; }
    .action-link-term { color: var(--status-stopped); }
    .action-link-term:hover { text-decoration: underline; color: #ff7b72; }

    .action-sep { color: var(--border-default); font-size: 11px; }

    .empty-state {
      padding: 56px 24px; text-align: center; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
    }

    .empty-icon {
      width: 44px; height: 44px; border-radius: var(--radius-md); background: #11151c;
      border: 1px dashed var(--border-default); display: flex; align-items: center;
      justify-content: center; color: var(--text-dim); margin-bottom: 14px;
    }

    .empty-title { font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 4px; }
    .empty-subtitle { font-size: 12.5px; color: var(--text-muted); max-width: 360px; margin-bottom: 18px; }

    /* MODAL OVERLAY / BACKDROP */
    .modal-overlay, .modal-backdrop {
      position: fixed; inset: 0; background-color: rgba(6, 9, 13, 0.78);
      backdrop-filter: blur(2px); display: none; align-items: center; justify-content: center; z-index: 100;
    }

    .modal-overlay.open, .modal-overlay.active,
    .modal-backdrop.open, .modal-backdrop.active { display: flex; }

    .modal-dialog, .modal {
      background-color: var(--bg-surface); border: 1px solid var(--border-default);
      border-radius: var(--radius-lg); width: 100%; max-width: 480px;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6); overflow: hidden;
      animation: modalFadeIn 0.15s ease-out;
    }

    @keyframes modalFadeIn {
      from { opacity: 0; transform: translateY(-8px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .modal-header {
      padding: 16px 20px; border-bottom: 1px solid var(--border-default);
      display: flex; align-items: center; justify-content: space-between;
      background-color: #13171f;
    }

    .modal-header h2, .modal-header h3 {
      font-size: 15px; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 8px;
    }

    .modal-close-btn, .modal-close {
      background: transparent; border: none; color: var(--text-muted);
      font-size: 18px; line-height: 1; cursor: pointer; padding: 4px;
    }

    .modal-close-btn:hover, .modal-close:hover { color: var(--text-main); }

    .modal-body { padding: 20px; }

    .form-group, .form-field { margin-bottom: 18px; }
    .form-group:last-child, .form-field:last-child { margin-bottom: 0; }

    .form-label, .form-field label {
      display: block; font-size: 12px; font-weight: 500; color: var(--text-main); margin-bottom: 6px;
    }

    .form-label span.req { color: var(--accent-orange); }

    .form-select, .form-input, .form-field input, .form-field select {
      width: 100%; height: 36px; background-color: #0e1117;
      border: 1px solid var(--border-default); border-radius: var(--radius-sm);
      color: var(--text-main); font-family: var(--font-sans); font-size: 13px;
      padding: 0 10px; outline: none; transition: border-color 0.15s ease;
    }

    .form-select:focus, .form-input:focus, .form-field input:focus, .form-field select:focus {
      border-color: var(--border-focus); box-shadow: 0 0 0 1px var(--border-focus);
    }

    .form-input[disabled], .form-select[disabled], .form-field input:disabled {
      background-color: #13171f; color: var(--text-muted); cursor: not-allowed;
      border-style: dashed; font-family: var(--font-mono); font-size: 12px;
    }

    .form-help, .form-hint {
      display: block; font-size: 11.5px; color: var(--text-muted); margin-top: 5px; line-height: 1.4;
    }

    .modal-footer {
      padding: 14px 20px; background-color: #12161e;
      border-top: 1px solid var(--border-default); display: flex;
      align-items: center; justify-content: flex-end; gap: 10px;
    }

    /* TELEMETRY FOOTER */
    .telemetry-bar {
      margin-top: auto; border-top: 1px solid var(--border-default);
      background-color: var(--bg-surface); padding: 8px 24px;
      display: flex; align-items: center; justify-content: space-between;
      font-family: var(--font-mono); font-size: 11.5px; color: var(--text-muted);
    }

    .telemetry-group { display: flex; align-items: center; gap: 18px; }
    .telemetry-item span.label { color: var(--text-dim); margin-right: 4px; }
    .telemetry-item span.val { color: var(--text-main); }

    .badge-subtle {
      background: #1e2633; border: 1px solid var(--border-subtle);
      padding: 1px 6px; border-radius: var(--radius-sm); color: #9ab;
    }
  </style>
</head>
<body>

  <!-- 1. TOP IDENTITY BAR -->
  <header class="top-header">
    <div class="brand-group">
      <a href="http://localhost:4566/services" style="display:flex; align-items:center; gap:10px; text-decoration:none; color:inherit;">
        <img src="/static/images/Local_AWS_logo.png" alt="LocalAWS Logo" style="height:26px; width:auto; display:block; object-fit:contain;">
        <div class="brand-wordmark">
          LocalAWS Console
          <span class="brand-badge">ec2.local:4567</span>
        </div>
      </a>
      <nav class="nav-breadcrumb">
        <a href="http://localhost:4566/services">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          Services Dashboard
        </a>
        <span class="separator">/</span>
        <span class="current">EC2</span>
      </nav>
    </div>

    <div class="header-right">
      <div class="service-chip-ec2">EC2 COMPUTE</div>
      <div class="daemon-indicator">
        <div class="pulse-dot"></div>
        <span>daemon: healthy</span>
      </div>
      <button class="btn-signout" onclick="window.location.href='http://localhost:4566/services'">Sign out</button>
    </div>
  </header>

  <!-- 2. MAIN WORKSPACE CONTENT -->
  <main class="main-content">
    
    <!-- PAGE TITLE & HEADER BAR -->
    <div class="page-header">
      <div class="title-block">
        <div class="title-area">
          <h1 class="page-title">EC2 Compute</h1>
          <span class="instance-counter" id="instanceCountBadge">{{ instances|length }} instances</span>
        </div>
        <p class="page-subtitle">Manage containerized virtual machine instances running under local Docker hypervisor emulation.</p>
      </div>

      <div class="action-group">
        <button type="button" class="btn btn-ghost" onclick="location.reload()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
          </svg>
          Refresh
        </button>
        <button type="button" class="btn btn-primary" onclick="openLaunchModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Launch instance
        </button>
      </div>
    </div>

    <!-- 3. 4-CARD SUMMARY STRIP -->
    <section class="summary-strip">
      <div class="metric-card">
        <div class="metric-label">
          <span>Total instances</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--text-dim)">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
            <line x1="6" y1="6" x2="6.01" y2="6"></line>
            <line x1="6" y1="18" x2="6.01" y2="18"></line>
          </svg>
        </div>
        <div class="metric-value">{{ instances|length }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">
          <span>Running</span>
          <span class="status-pill running" style="padding: 1px 5px; font-size: 10px;"><span class="dot"></span>LIVE</span>
        </div>
        <div class="metric-value running">{{ instances|selectattr('state','equalto','running')|list|length }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">
          <span>Stopped</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--text-dim)">
            <circle cx="12" cy="12" r="10"></circle>
            <rect x="9" y="9" width="6" height="6"></rect>
          </svg>
        </div>
        <div class="metric-value stopped">{{ instances|selectattr('state','equalto','exited')|list|length }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">
          <span>Region</span>
          <span class="badge-subtle">hypervisor</span>
        </div>
        <div class="metric-value region">local-docker-1</div>
      </div>
    </section>

    <!-- 4. TABLE TOOLBAR WITH SEARCH BOX -->
    <div class="table-toolbar">
      <div class="search-wrapper">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input 
          type="text" 
          id="searchBox" 
          class="search-input" 
          placeholder="Filter instances..." 
          oninput="filterTable()"
        >
      </div>

      <div class="table-tools">
        <button type="button" class="btn-icon" onclick="location.reload()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
          </svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- 5. DENSE INSTANCES TABLE -->
    <div class="data-table-wrap">
      <table id="instanceTable" class="data-table">
        <thead>
          <tr>
            <th class="cell-checkbox">
              <input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)" title="Select all instances">
            </th>
            <th>Instance ID</th>
            <th>Instance state</th>
            <th>Image (AMI)</th>
            <th>Instance type</th>
            <th>Console</th>
            <th style="text-align: right; padding-right: 20px;">Actions</th>
          </tr>
        </thead>
        <tbody id="instancesTbody">
          {% if instances %}
            {% for i in instances %}
            <tr>
              <td class="cell-checkbox">
                <input type="checkbox" class="instance-row-select">
              </td>
              <td>
                <a href="#" class="instance-id-link">i-{{ i.id }}</a>
              </td>
              <td>
                {% if i.state == 'running' %}
                  <span class="status-pill running">
                    <span class="dot"></span> Running
                  </span>
                {% elif i.state == 'exited' %}
                  <span class="status-pill stopped">
                    <span class="dot"></span> Stopped
                  </span>
                {% else %}
                  <span class="status-pill pending">
                    <span class="dot"></span> {{ i.state }}
                  </span>
                {% endif %}
              </td>
              <td>
                <div class="ami-badge">
                  <span class="ami-tag">AMI</span>
                  <span>{{ i.image }}</span>
                </div>
              </td>
              <td>
                <span class="mono-cell">docker.nano</span>
              </td>
              <td>
                {% if i.state == 'running' %}
                  <a href="http://localhost:{{ i.port }}" target="_blank" rel="noopener noreferrer" class="console-link-active" title="Open terminal via ttyd in new tab">
                    Open console &rarr;
                  </a>
                {% else %}
                  <span class="console-unavailable">&mdash; unavailable</span>
                {% endif %}
              </td>
              <td style="text-align: right; padding-right: 20px;">
                <div class="actions-cell" style="justify-content: flex-end;">
                  {% if i.state == 'running' %}
                    <a href="/stop/{{ i.id }}" class="action-link action-link-stop">Stop</a>
                  {% else %}
                    <a href="/start/{{ i.id }}" class="action-link action-link-start">Start</a>
                  {% endif %}
                  <span class="action-sep">|</span>
                  <a href="/terminate/{{ i.id }}" class="action-link action-link-term" onclick="return confirm('Terminate instance i-{{ i.id }}?')">Terminate</a>
                </div>
              </td>
            </tr>
            {% endfor %}
          {% else %}
            <tr>
              <td colspan="7">
                <div class="empty-state">
                  <div class="empty-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                      <line x1="6" y1="6" x2="6.01" y2="6"></line>
                      <line x1="6" y1="18" x2="6.01" y2="18"></line>
                    </svg>
                  </div>
                  <div class="empty-title">No instances found</div>
                  <div class="empty-subtitle">Launch an instance to get started running local workloads inside docker containers.</div>
                  <button type="button" class="btn btn-primary" onclick="openLaunchModal()">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19"></line>
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                    Launch instance
                  </button>
                </div>
              </td>
            </tr>
          {% endif %}
        </tbody>
      </table>
    </div>

  </main>

  <!-- LAUNCH INSTANCE MODAL -->
  <div id="launchModal" class="modal-overlay">
    <div class="modal-dialog">
      <div class="modal-header">
        <h3>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-orange)">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
            <line x1="6" y1="6" x2="6.01" y2="6"></line>
            <line x1="6" y1="18" x2="6.01" y2="18"></line>
          </svg>
          Launch new instance
        </h3>
        <button type="button" class="modal-close-btn" onclick="closeLaunchModal()">&times;</button>
      </div>

      <form action="/launch" method="post" id="launchForm">
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label" for="amiSelect">
              Base Image (AMI) <span class="req">*</span>
            </label>
            <select name="image" id="amiSelect" class="form-select" required>
              <option value="alpine" selected>Alpine Linux (alpine)</option>
              <option value="ubuntu">Ubuntu (ubuntu)</option>
              <option value="debian">Debian (debian)</option>
              <option value="python:3.11-slim">Python 3.11 Slim</option>
              <option value="node:20-alpine">Node.js 20 Alpine</option>
            </select>
            <span class="form-help">Pulls or reuses cached Docker container images from the local daemon registry.</span>
          </div>

          <div class="form-group">
            <label class="form-label" for="instanceType">
              Instance Type
            </label>
            <input 
              type="text" 
              id="instanceType" 
              value="docker.nano" 
              disabled 
              class="form-input"
              title="Locked to docker.nano under local emulation"
            >
            <span class="form-help">Fixed to <code>docker.nano</code> (1 vCPU, 512 MB memory limit, ttyd terminal enabled).</span>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-ghost" onclick="closeLaunchModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">
            Launch instance
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- TELEMETRY FOOTER -->
  <footer class="telemetry-bar">
    <div class="telemetry-group">
      <div class="telemetry-item">
        <span class="label">HYPERVISOR:</span>
        <span class="val">docker-engine</span>
      </div>
      <div class="telemetry-item">
        <span class="label">METADATA ENDPOINT:</span>
        <span class="val" style="color: var(--accent-orange);">metadata.local:4567</span>
      </div>
    </div>
    <div class="telemetry-group">
      <div class="telemetry-item">
        <span class="label">ARCHITECTURE:</span>
        <span class="val">x86_64</span>
      </div>
    </div>
  </footer>

  <script>
    function filterTable() {
      const q = document.getElementById('searchBox').value.toLowerCase();
      document.querySelectorAll('#instanceTable tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }

    function openLaunchModal() {
      const modal = document.getElementById('launchModal');
      if (modal) {
        modal.classList.add('open');
        modal.classList.add('active');
      }
    }

    function closeLaunchModal() {
      const modal = document.getElementById('launchModal');
      if (modal) {
        modal.classList.remove('open');
        modal.classList.remove('active');
      }
    }

    function toggleSelectAll(master) {
      const checkboxes = document.querySelectorAll('.instance-row-select');
      checkboxes.forEach(cb => cb.checked = master.checked);
    }
  </script>
</body>
</html>
"""

from flask import send_from_directory

@app.route("/docs/images/<path:filename>")
def serve_docs_images(filename):
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return send_from_directory(os.path.join(parent_dir, "docs", "images"), filename)

@app.route("/static/images/<path:filename>")
def serve_static_images(filename):
    static_dir = os.path.join(os.path.dirname(__file__), "static", "images")
    if os.path.exists(os.path.join(static_dir, filename)):
        return send_from_directory(static_dir, filename)
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return send_from_directory(os.path.join(parent_dir, "docs", "images"), filename)

@app.route("/")
def dashboard():
    rows = []
    for iid, info in INSTANCES.items():
        c = client.containers.get(info["cid"])
        rows.append({"id": iid, "state": c.status, "port": info["port"],  "image": info.get("image","unknown")})
    return render_template_string(PAGE, instances=rows)

@app.route("/launch", methods=["POST"])
@require_permission("ec2:RunInstance", lambda r: arn_ec2("*"), allow_session=False)
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
@require_permission("ec2:StopInstance", lambda r: arn_ec2(r.view_args['iid']), allow_session=False)
def stop(iid):
    client.containers.get(INSTANCES[iid]["cid"]).stop()
    return dashboard()

@app.route("/start/<iid>")
@require_permission("ec2:StartInstance", lambda r: arn_ec2(r.view_args['iid']), allow_session=False)
def start(iid):
    client.containers.get(INSTANCES[iid]["cid"]).start()
    return dashboard()

@app.route("/terminate/<iid>")
@require_permission("ec2:TerminateInstance", lambda r: arn_ec2(r.view_args['iid']), allow_session=False)
def terminate(iid):
    info = INSTANCES.pop(iid)
    client.containers.get(info["cid"]).remove(force=True)
    client.containers.get(info["tid"]).remove(force=True)
    return dashboard()


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "ec2", "version": "1.0.0"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4567)