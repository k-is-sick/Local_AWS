import os
import sys
import shutil
import time
import threading
import subprocess
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox

RUN_DIR_NAME = "LocalAWS_Runtime"
DOCKER_DOWNLOAD_URL = "https://www.docker.com/products/docker-desktop/"


def get_resource_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_runtime_dir():
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local_app_data, RUN_DIR_NAME)


def sync_resources(src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    items_to_copy = [
        "docker-compose.yaml",
        "Dockerfile",
        "app.py",
        "requirements.txt",
        "s3",
        "dynamodb",
        "ec2",
        "iam",
        "lambda",
        "templates",
        "shared"
    ]
    for item in items_to_copy:
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        if os.path.exists(s):
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)


def check_docker():
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            creationflags=creation_flags
        )
        return res.returncode == 0
    except Exception:
        return False


def run_cmd(cmd_list, cwd):
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        return subprocess.run(
            cmd_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            creationflags=creation_flags
        )
    except Exception as e:
        return None


def run_docker_up(cwd):
    res = run_cmd(["docker", "compose", "up", "-d", "--build"], cwd)
    if not res or res.returncode != 0:
        res = run_cmd(["docker-compose", "up", "-d", "--build"], cwd)
    return res


def run_docker_down(cwd):
    res = run_cmd(["docker", "compose", "down"], cwd)
    if not res or res.returncode != 0:
        res = run_cmd(["docker-compose", "down"], cwd)
    return res


class LocalAWSLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LocalAWS Control Launcher")
        self.root.geometry("520x360")
        self.root.resizable(False, False)
        self.root.configure(bg="#0d1117")

        self.runtime_dir = get_runtime_dir()
        self.is_running = False

        self.setup_ui()
        
        # Start initialization thread
        threading.Thread(target=self.initial_startup, daemon=True).start()

    def create_hover_button(self, parent, text, bg, fg, hover_bg, command, is_bold=False):
        font_style = ("Segoe UI", 9, "bold") if is_bold else ("Segoe UI", 9)
        btn = tk.Button(
            parent,
            text=text,
            font=font_style,
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=command,
            padx=14,
            pady=7
        )
        
        def on_enter(e):
            if btn["state"] == "normal":
                btn.config(bg=hover_bg)

        def on_leave(e):
            if btn["state"] == "normal":
                btn.config(bg=bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.default_bg = bg
        btn.hover_bg = hover_bg
        return btn

    def setup_ui(self):
        # Header Box
        header_frame = tk.Frame(self.root, bg="#161b22", padx=24, pady=16)
        header_frame.pack(fill="x", side="top")

        header_content = tk.Frame(header_frame, bg="#161b22")
        header_content.pack(fill="x")

        # Logo Badge
        logo_lbl = tk.Label(
            header_content,
            text="L",
            font=("Segoe UI", 12, "bold"),
            fg="#161616",
            bg="#ff9900",
            width=2,
            height=1
        )
        logo_lbl.pack(side="left", padx=(0, 12))

        header_text = tk.Frame(header_content, bg="#161b22")
        header_text.pack(side="left", fill="x")

        title_lbl = tk.Label(
            header_text,
            text="LocalAWS Control Launcher",
            font=("Segoe UI", 13, "bold"),
            fg="#e6edf3",
            bg="#161b22"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            header_text,
            text="Local AWS Micro-Cloud Emulation Suite",
            font=("Segoe UI", 9),
            fg="#8b949e",
            bg="#161b22"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Main Body Container
        main_container = tk.Frame(self.root, bg="#0d1117", padx=24, pady=20)
        main_container.pack(fill="both", expand=True)

        # Status Card (Bordered Box)
        self.card_frame = tk.Frame(
            main_container,
            bg="#161b22",
            highlightbackground="#30363d",
            highlightthickness=1,
            padx=18,
            pady=16
        )
        self.card_frame.pack(fill="x", pady=(0, 20))

        # Status Row (Badge Dot + Text)
        status_row = tk.Frame(self.card_frame, bg="#161b22")
        status_row.pack(anchor="w", fill="x", pady=(0, 10))

        self.status_dot = tk.Label(
            status_row,
            text="●",
            font=("Segoe UI", 14),
            fg="#d29922",
            bg="#161b22"
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_lbl = tk.Label(
            status_row,
            text="Checking Docker Desktop...",
            font=("Segoe UI", 11, "bold"),
            fg="#d29922",
            bg="#161b22"
        )
        self.status_lbl.pack(side="left")

        # Runtime Info Sub-section
        path_header = tk.Label(
            self.card_frame,
            text="RUNTIME DIRECTORY",
            font=("Segoe UI", 8, "bold"),
            fg="#8b949e",
            bg="#161b22"
        )
        path_header.pack(anchor="w", pady=(0, 2))

        self.info_lbl = tk.Label(
            self.card_frame,
            text=self.runtime_dir,
            font=("Consolas", 8),
            fg="#8b949e",
            bg="#161b22",
            justify="left",
            wraplength=430
        )
        self.info_lbl.pack(anchor="w")

        # Action Buttons Row
        btn_frame = tk.Frame(main_container, bg="#0d1117")
        btn_frame.pack(fill="x")

        self.btn_open = self.create_hover_button(
            btn_frame, "Open Console", "#238636", "#ffffff", "#2ea043", self.open_browser, is_bold=True
        )
        self.btn_open.pack(side="left", padx=(0, 10))
        self.btn_open.config(state="disabled")

        self.btn_start = self.create_hover_button(
            btn_frame, "Start Stack", "#21262d", "#c9d1d9", "#30363d", self.start_stack_thread
        )
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_start.config(state="disabled")

        self.btn_stop = self.create_hover_button(
            btn_frame, "Stop Stack", "#da3633", "#ffffff", "#f85149", self.stop_stack_thread
        )
        self.btn_stop.pack(side="left", padx=(0, 10))
        self.btn_stop.config(state="disabled")

        self.btn_quit = self.create_hover_button(
            btn_frame, "Exit", "#21262d", "#c9d1d9", "#30363d", self.on_quit
        )
        self.btn_quit.pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

    def set_status(self, text, color, open_enabled=False, start_enabled=False, stop_enabled=False):
        # Format display text (strip 'Status: ' prefix if present)
        display_text = text.replace("Status: ", "")
        self.status_lbl.config(text=display_text, fg=color)
        self.status_dot.config(fg=color)

        self.btn_open.config(state="normal" if open_enabled else "disabled")
        self.btn_start.config(state="normal" if start_enabled else "disabled")
        self.btn_stop.config(state="normal" if stop_enabled else "disabled")

        # Adjust background colors when disabled/enabled
        for btn in (self.btn_open, self.btn_start, self.btn_stop):
            if btn["state"] == "disabled":
                btn.config(bg="#161b22", fg="#484f58")
            else:
                btn.config(bg=btn.default_bg, fg="#ffffff" if btn.default_bg in ("#238636", "#da3633") else "#c9d1d9")

    def initial_startup(self):
        # 1. Check Docker
        if not check_docker():
            self.root.after(0, self.handle_no_docker)
            return

        # 2. Extract/sync runtime files
        self.set_status("Status: Syncing runtime resources...", "#d29922")
        src_dir = get_resource_dir()
        sync_resources(src_dir, self.runtime_dir)

        # 3. Start docker compose stack
        self.start_stack_internal()

    def handle_no_docker(self):
        self.set_status("Status: Docker Desktop not found/running", "#f85149")
        show_err = messagebox.showerror(
            "Docker Desktop Required",
            "Docker Desktop is not installed or not currently running.\n\n"
            "LocalAWS requires Docker Desktop to orchestrate cloud service containers.\n\n"
            "Click OK to open the Docker Desktop download page."
        )
        webbrowser.open(DOCKER_DOWNLOAD_URL)
        self.root.destroy()
        sys.exit(1)

    def start_stack_thread(self):
        threading.Thread(target=self.start_stack_internal, daemon=True).start()

    def start_stack_internal(self):
        self.set_status("Status: Starting Docker containers...", "#d29922")
        run_docker_up(self.runtime_dir)

        # Poll gateway health
        self.set_status("Status: Waiting for LocalAWS Gateway (:4566)...", "#d29922")
        healthy = False
        for _ in range(45):
            try:
                req = urllib.request.urlopen("http://localhost:4566/api/health", timeout=2)
                if req.getcode() == 200:
                    healthy = True
                    break
            except Exception:
                time.sleep(1)

        if healthy:
            self.is_running = True
            self.set_status("Status: LocalAWS Running (http://localhost:4566)", "#3fb950", open_enabled=True, stop_enabled=True)
            self.open_browser()
        else:
            self.set_status("Status: Failed to reach gateway", "#f85149", start_enabled=True, stop_enabled=True)

    def stop_stack_thread(self):
        threading.Thread(target=self.stop_stack_internal, daemon=True).start()

    def stop_stack_internal(self):
        self.set_status("Status: Stopping containers...", "#d29922")
        run_docker_down(self.runtime_dir)
        self.is_running = False
        self.set_status("Status: LocalAWS Stopped", "#f85149", start_enabled=True)

    def open_browser(self):
        webbrowser.open("http://localhost:4566")

    def on_quit(self):
        if self.is_running:
            if messagebox.askyesno("Exit LocalAWS", "Do you want to stop all LocalAWS containers before exiting?"):
                self.set_status("Status: Stopping containers on exit...", "#d29922")
                run_docker_down(self.runtime_dir)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = LocalAWSLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
