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
from PIL import Image, ImageTk

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
        "static",
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
        self.root.title("LocalAWS Console Launcher")
        self.root.geometry("560x410")
        self.root.resizable(False, False)
        self.root.configure(bg="#0e1117")

        self.runtime_dir = get_runtime_dir()
        self.is_running = False
        self.src_dir = get_resource_dir()

        self.set_window_icon()
        self.setup_ui()
        
        # Start initialization thread
        threading.Thread(target=self.initial_startup, daemon=True).start()

    def set_window_icon(self):
        # Set taskbar / window icon
        ico_path = os.path.join(self.src_dir, "launcher", "logo.ico")
        png_path = os.path.join(self.src_dir, "static", "images", "Local_AWS_logo.png")
        
        try:
            if sys.platform == "win32" and os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                img = Image.open(png_path)
                self.window_icon_img = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self.window_icon_img)
        except Exception:
            pass

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
            padx=16,
            pady=8
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
        # Global Header Bar
        header_frame = tk.Frame(self.root, bg="#161b22", padx=24, pady=14, highlightbackground="#2e3745", highlightthickness=1)
        header_frame.pack(fill="x", side="top")

        header_content = tk.Frame(header_frame, bg="#161b22")
        header_content.pack(fill="x")

        # Logo Image
        logo_png_path = os.path.join(self.src_dir, "static", "images", "Local_AWS_logo.png")
        logo_loaded = False
        if os.path.exists(logo_png_path):
            try:
                img = Image.open(logo_png_path)
                w, h = img.size
                target_h = 34
                target_w = int(w * (target_h / h))
                img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                self.header_logo_img = ImageTk.PhotoImage(img_resized)
                logo_lbl = tk.Label(header_content, image=self.header_logo_img, bg="#161b22")
                logo_lbl.pack(side="left", padx=(0, 12))
                logo_loaded = True
            except Exception:
                pass

        if not logo_loaded:
            # Fallback orange box logo
            logo_lbl = tk.Label(
                header_content,
                text="L",
                font=("IBM Plex Mono", 12, "bold"),
                fg="#0e1117",
                bg="#ff9900",
                width=2,
                height=1
            )
            logo_lbl.pack(side="left", padx=(0, 12))

        header_text = tk.Frame(header_content, bg="#161b22")
        header_text.pack(side="left", fill="x")

        # Title Row (LocalAWS Console + v1.0 Badge)
        title_row = tk.Frame(header_text, bg="#161b22")
        title_row.pack(anchor="w")

        title_lbl = tk.Label(
            title_row,
            text="LocalAWS Console Launcher",
            font=("Segoe UI", 12, "bold"),
            fg="#ffffff",
            bg="#161b22"
        )
        title_lbl.pack(side="left", padx=(0, 8))

        badge_lbl = tk.Label(
            title_row,
            text="v1.10",
            font=("Consolas", 8, "bold"),
            fg="#ff9900",
            bg="#161b22",
            highlightbackground="#ff9900",
            highlightthickness=1,
            padx=4,
            pady=1
        )
        badge_lbl.pack(side="left")

        sub_lbl = tk.Label(
            header_text,
            text="Local Cloud Infrastructure & Services Suite",
            font=("Segoe UI", 9),
            fg="#8b94a3",
            bg="#161b22"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Main Body Container
        main_container = tk.Frame(self.root, bg="#0e1117", padx=24, pady=18)
        main_container.pack(fill="both", expand=True)

        # Status Card (Bordered Box matching web surface)
        self.card_frame = tk.Frame(
            main_container,
            bg="#1f242d",
            highlightbackground="#2e3745",
            highlightthickness=1,
            padx=18,
            pady=16
        )
        self.card_frame.pack(fill="x", pady=(0, 16))

        # Status Row (Dot + Text Status)
        status_row = tk.Frame(self.card_frame, bg="#1f242d")
        status_row.pack(anchor="w", fill="x", pady=(0, 12))

        self.status_dot = tk.Label(
            status_row,
            text="●",
            font=("Segoe UI", 14),
            fg="#d29922",
            bg="#1f242d"
        )
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_lbl = tk.Label(
            status_row,
            text="Checking Docker Desktop...",
            font=("Segoe UI", 11, "bold"),
            fg="#d29922",
            bg="#1f242d"
        )
        self.status_lbl.pack(side="left")

        # Daemon Badge Indicator
        daemon_lbl = tk.Label(
            status_row,
            text="Gateway: http://localhost:4566",
            font=("Consolas", 8),
            fg="#ff9900",
            bg="#161b22",
            highlightbackground="#2e3745",
            highlightthickness=1,
            padx=6,
            pady=2
        )
        daemon_lbl.pack(side="right")

        # Runtime Info Sub-section
        path_header = tk.Label(
            self.card_frame,
            text="RUNTIME DIRECTORY",
            font=("Segoe UI", 8, "bold"),
            fg="#8b94a3",
            bg="#1f242d"
        )
        path_header.pack(anchor="w", pady=(0, 4))

        info_box = tk.Frame(
            self.card_frame,
            bg="#0e1117",
            highlightbackground="#242b35",
            highlightthickness=1,
            padx=10,
            pady=6
        )
        info_box.pack(fill="x")

        self.info_lbl = tk.Label(
            info_box,
            text=self.runtime_dir,
            font=("Consolas", 8),
            fg="#d6dde5",
            bg="#0e1117",
            justify="left",
            wraplength=460
        )
        self.info_lbl.pack(anchor="w")

        # Action Buttons Row
        btn_frame = tk.Frame(main_container, bg="#0e1117")
        btn_frame.pack(fill="x", pady=(4, 16))

        # Primary Orange Button for Open Console
        self.btn_open = self.create_hover_button(
            btn_frame, "Open Console", "#ff9900", "#0e1117", "#ffaa22", self.open_browser, is_bold=True
        )
        self.btn_open.pack(side="left", padx=(0, 10))
        self.btn_open.config(state="disabled")

        self.btn_start = self.create_hover_button(
            btn_frame, "Start Stack", "#21262d", "#3fb950", "#2ea043", self.start_stack_thread
        )
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_start.config(state="disabled")

        self.btn_stop = self.create_hover_button(
            btn_frame, "Stop Stack", "#21262d", "#f85149", "#da3633", self.stop_stack_thread
        )
        self.btn_stop.pack(side="left", padx=(0, 10))
        self.btn_stop.config(state="disabled")

        self.btn_quit = self.create_hover_button(
            btn_frame, "Exit", "#21262d", "#8b94a3", "#30363d", self.on_quit
        )
        self.btn_quit.pack(side="right")

        # Footer Credit Line
        footer_lbl = tk.Label(
            main_container,
            text="made by k-is-sick and joshiyashsh",
            font=("Segoe UI", 9),
            fg="#8b94a3",
            bg="#0e1117"
        )
        footer_lbl.pack(side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

    def set_status(self, text, color, open_enabled=False, start_enabled=False, stop_enabled=False):
        display_text = text.replace("Status: ", "")
        self.status_lbl.config(text=display_text, fg=color)
        self.status_dot.config(fg=color)

        self.btn_open.config(state="normal" if open_enabled else "disabled")
        self.btn_start.config(state="normal" if start_enabled else "disabled")
        self.btn_stop.config(state="normal" if stop_enabled else "disabled")

        # Button styling according to enabled state
        if self.btn_open["state"] == "disabled":
            self.btn_open.config(bg="#161b22", fg="#484f58")
        else:
            self.btn_open.config(bg="#ff9900", fg="#0e1117")

        if self.btn_start["state"] == "disabled":
            self.btn_start.config(bg="#161b22", fg="#484f58")
        else:
            self.btn_start.config(bg="#21262d", fg="#3fb950")

        if self.btn_stop["state"] == "disabled":
            self.btn_stop.config(bg="#161b22", fg="#484f58")
        else:
            self.btn_stop.config(bg="#21262d", fg="#f85149")

    def initial_startup(self):
        if not check_docker():
            self.root.after(0, self.handle_no_docker)
            return

        self.set_status("Status: Syncing runtime resources...", "#d29922")
        sync_resources(self.src_dir, self.runtime_dir)
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
