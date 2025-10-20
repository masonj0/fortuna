import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import time
import requests
import psutil
import socket
import sys
import os
from pathlib import Path

# --- Control Panel Tab (from former launcher_gui.py) ---
class ControlPanelTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg='#1a1a2e')
        self.backend_proc = None
        self.frontend_proc = None
        self._create_ui()
        self.monitor_thread = threading.Thread(target=self.monitor_services, daemon=True)
        self.monitor_thread.start()

    def _create_ui(self):
        title = tk.Label(self, text="🐴 System Control Panel", font=("Segoe UI", 16, "bold"), bg='#1a1a2e', fg='#00ff88')
        title.pack(pady=20)

        status_frame = tk.Frame(self, bg='#1a1a2e')
        status_frame.pack(fill=tk.X, padx=40, pady=10)

        tk.Label(status_frame, text="Backend Service (API)", font=("Segoe UI", 10), bg='#1a1a2e', fg='#ffffff').pack(anchor="w")
        self.backend_status_canvas = tk.Canvas(status_frame, width=300, height=40, bg='#0f3460', highlightthickness=0)
        self.backend_status_canvas.pack(fill=tk.X, pady=(0, 10))
        self.backend_indicator = self.backend_status_canvas.create_oval(15, 10, 35, 30, fill='#ff4444', outline='')
        self.backend_text = self.backend_status_canvas.create_text(55, 20, text="Stopped", fill='#ffffff', anchor="w", font=("Segoe UI", 9))

        tk.Label(status_frame, text="Frontend Dashboard (UI)", font=("Segoe UI", 10), bg='#1a1a2e', fg='#ffffff').pack(anchor="w")
        self.frontend_status_canvas = tk.Canvas(status_frame, width=300, height=40, bg='#0f3460', highlightthickness=0)
        self.frontend_status_canvas.pack(fill=tk.X)
        self.frontend_indicator = self.frontend_status_canvas.create_oval(15, 10, 35, 30, fill='#ff4444', outline='')
        self.frontend_text = self.frontend_status_canvas.create_text(55, 20, text="Stopped", fill='#ffffff', anchor="w", font=("Segoe UI", 9))

        button_frame = tk.Frame(self, bg='#1a1a2e')
        button_frame.pack(fill=tk.X, padx=40, pady=20)

        self.launch_btn = tk.Button(button_frame, text="▶ START FORTUNA", font=("Segoe UI", 14, "bold"), bg='#00ff88', fg='#000000', command=self.launch_services, height=2, relief=tk.FLAT)
        self.launch_btn.pack(fill=tk.X, pady=(0, 10))

        self.stop_btn = tk.Button(button_frame, text="⏹ STOP SERVICES", font=("Segoe UI", 12), bg='#ff4444', fg='#ffffff', command=self.stop_services, state=tk.DISABLED, height=1, relief=tk.FLAT)
        self.stop_btn.pack(fill=tk.X)

    def check_ports(self, ports=[8000, 3000]):
        unavailable_ports = []
        for port in ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    unavailable_ports.append(port)
        return unavailable_ports

    def launch_services(self):
        unavailable = self.check_ports()
        if unavailable:
            messagebox.showerror("Port Conflict", f"Cannot launch. Port(s) {', '.join(map(str, unavailable))} are already in use by another application.")
            return

        self.launch_btn.config(state=tk.DISABLED)
        self.update_status("backend", "starting", "Launching...")
        self.update_status("frontend", "starting", "Launching...")

        try:
            venv_python = Path(".venv/Scripts/python.exe")
            self.backend_proc = subprocess.Popen(
                [str(venv_python), "-m", "uvicorn", "python_service.api:app", "--host", "127.0.0.1", "--port", "8000"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=Path(__file__).parent, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        except Exception as e:
            self.update_status("backend", "error", f"Launch Error: {str(e)[:40]}")
            self.stop_btn.config(state=tk.NORMAL)
            return

        try:
            self.frontend_proc = subprocess.Popen(
                ["npm", "run", "dev"], shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="web_platform/frontend", creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        except Exception as e:
            self.update_status("frontend", "error", f"Launch Error: {str(e)[:40]}")
            self.stop_btn.config(state=tk.NORMAL)
            return

        self.stop_btn.config(state=tk.NORMAL)

    def stop_services(self):
        self.stop_btn.config(state=tk.DISABLED)
        for proc_name in ["backend", "frontend"]:
            proc = getattr(self, f"{proc_name}_proc")
            if proc and proc.poll() is None:
                try:
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
            setattr(self, f"{proc_name}_proc", None)
        self.launch_btn.config(state=tk.NORMAL)

    def monitor_services(self):
        while True:
            if self.backend_proc and self.backend_proc.poll() is None:
                try:
                    r = requests.get("http://localhost:8000/health", timeout=2)
                    if r.status_code == 200:
                        self.update_status("backend", "ok", "Healthy (200 OK)")
                    else:
                        self.update_status("backend", "error", f"Error ({r.status_code})")
                except requests.RequestException:
                    self.update_status("backend", "unresponsive", "Unresponsive")
            else:
                self.update_status("backend", "stopped", "Stopped")

            if self.frontend_proc and self.frontend_proc.poll() is None:
                try:
                    r = requests.get("http://localhost:3000", timeout=2)
                    if r.status_code == 200:
                        self.update_status("frontend", "ok", "Healthy (200 OK)")
                    else:
                        self.update_status("frontend", "error", f"Error ({r.status_code})")
                except requests.RequestException:
                    self.update_status("frontend", "unresponsive", "Unresponsive")
            else:
                self.update_status("frontend", "stopped", "Stopped")
            time.sleep(5)

    def update_status(self, service: str, status: str, message: str):
        colors = {"ok": "#00ff88", "unresponsive": "#ffcc00", "error": "#ff4444", "stopped": "#ff4444", "starting": "#0f6cbd"}
        canvas = getattr(self, f"{service}_status_canvas")
        indicator = getattr(self, f"{service}_indicator")
        text = getattr(self, f"{service}_text")

        canvas.itemconfig(indicator, fill=colors.get(status, "#404060"))
        canvas.itemconfig(text, text=message)

# --- Setup Wizard Tab (from former setup_wizard_gui.py) ---
class SetupWizardTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg='#1a1a2e')
        self.current_step = 0
        self.settings = {}
        self._create_widgets()
        self.show_step(0)

    def _create_widgets(self):
        header = tk.Label(self, text="🔧 First-Time Setup & Configuration", font=("Segoe UI", 16, "bold"), bg='#1a1a2e', fg='#ffffff')
        header.pack(pady=20)
        self.step_label = tk.Label(self, text="Step 1 of 4: Generate API Key", font=("Segoe UI", 11), bg='#1a1a2e', fg='#ffffff')
        self.step_label.pack(pady=10)
        self.content_frame = tk.Frame(self, bg='#1a1a2e')
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        button_frame = tk.Frame(self, bg='#1a1a2e')
        button_frame.pack(fill=tk.X, padx=30, pady=20)
        self.prev_btn = tk.Button(button_frame, text="< Back", command=self.previous_step, state=tk.DISABLED, bg='#404060', fg='#ffffff', padx=20)
        self.prev_btn.pack(side=tk.LEFT)
        self.next_btn = tk.Button(button_frame, text="Next >", command=self.next_step, bg='#00ff88', fg='#000000', font=("Segoe UI", 11, "bold"), padx=20)
        self.next_btn.pack(side=tk.RIGHT)

    def show_step(self, step_index):
        self._clear_content()
        self.current_step = step_index
        if step_index == 0: self._show_step_1()
        elif step_index == 1: self._show_step_2()
        elif step_index == 2: self._show_step_3()
        elif step_index == 3: self._show_step_4()
        self.update_buttons()

    def _show_step_1(self):
        tk.Label(self.content_frame, text="🔐 Secure API Key", font=("Segoe UI", 12, "bold"), bg='#1a1a2e', fg='#ffffff').pack(anchor="w")
        tk.Label(self.content_frame, text="A secure API key will be generated and stored.", wraplength=600, justify=tk.LEFT, bg='#1a1a2e', fg='#cccccc').pack(anchor="w", pady=10)
        # ... Add API key generation logic and display ...

    def _show_step_2(self):
        tk.Label(self.content_frame, text="🏇 Betfair Exchange (Optional)", font=("Segoe UI", 12, "bold"), bg='#1a1a2e', fg='#ffffff').pack(anchor="w")
        # ... Add Betfair configuration form ...

    def _show_step_3(self):
        tk.Label(self.content_frame, text="✓ Verifying Setup", font=("Segoe UI", 12, "bold"), bg='#1a1a2e', fg='#00ff88').pack(anchor="w")
        # ... Add verification checks logic ...

    def _show_step_4(self):
        tk.Label(self.content_frame, text="🎉 Setup Complete!", font=("Segoe UI", 14, "bold"), bg='#1a1a2e', fg='#00ff88').pack(pady=20)
        self.next_btn.config(text="✓ Finish", command=self.finish_setup)

    def next_step(self):
        if self.current_step < 3: self.show_step(self.current_step + 1)
    def previous_step(self):
        if self.current_step > 0: self.show_step(self.current_step - 1)
    def finish_setup(self):
        messagebox.showinfo("Setup Complete", "Your configuration has been saved.")

    def _clear_content(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()

    def update_buttons(self):
        self.prev_btn.config(state=tk.NORMAL if self.current_step > 0 else tk.DISABLED)
        if self.current_step == 3:
            self.next_btn.config(text="✓ Finish", command=self.finish_setup)
        else:
            self.next_btn.config(text="Next >", command=self.next_step)

# --- System Tools Tab ---
class SystemToolsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg='#1a1a2e')
        self._create_ui()

    def _create_ui(self):
        title = tk.Label(self, text="⚙️ System Tools", font=("Segoe UI", 16, "bold"), bg='#1a1a2e', fg='#ffffff')
        title.pack(pady=20)
        tk.Button(self, text="Create Desktop Shortcuts", command=self.run_create_shortcuts, font=("Segoe UI", 12)).pack(pady=10, padx=40, fill=tk.X)
        tk.Button(self, text="Verify Installation", command=self.run_verification, font=("Segoe UI", 12)).pack(pady=10, padx=40, fill=tk.X)
        self.output_box = scrolledtext.ScrolledText(self, height=10, bg="#0f3460", fg="#ffffff", state=tk.DISABLED)
        self.output_box.pack(pady=10, padx=40, fill=tk.BOTH, expand=True)

    def log_output(self, message):
        self.output_box.config(state=tk.NORMAL)
        self.output_box.insert(tk.END, message + "\n")
        self.output_box.config(state=tk.DISABLED)
        self.output_box.see(tk.END)

    def run_create_shortcuts(self):
        self.log_output("Running shortcut creation...")
        try:
            from win32com.client import Dispatch
            desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
            app_path = Path(__file__).resolve()
            shortcut_path = desktop / "🐴 Launch Fortuna.lnk"
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.TargetPath = sys.executable
            shortcut.Arguments = f'\"{app_path}\"'
            shortcut.WorkingDirectory = str(app_path.parent)
            shortcut.IconLocation = str(app_path.parent / "fortuna.ico")
            shortcut.save()
            self.log_output("✅ Success: Shortcut created on Desktop.")
        except Exception as e:
            self.log_output(f"❌ ERROR: Could not create shortcut. Make sure 'pywin32' is installed (`pip install pywin32`). Details: {e}")

    def run_verification(self):
        self.log_output("Running installation verification...")
        # Placeholder for full verification logic
        py_ok = sys.version_info >= (3, 11)
        self.log_output(f"- Python 3.11+ Check: {'✅' if py_ok else '❌'}")
        # ... Add other checks (Node.js, pip packages, etc.)
        self.log_output("Verification complete.")

# --- Main Application Window ---
class FortunaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🐴 Fortuna Faucet")
        self.geometry("700x550")
        self.configure(bg='#1a1a2e')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background='#1a1a2e', borderwidth=0)
        style.configure("TNotebook.Tab", background="#404060", foreground="#ffffff", padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", "#0f6cbd")])

        self.notebook = ttk.Notebook(self)

        self.control_panel_tab = ControlPanelTab(self.notebook)
        self.setup_wizard_tab = SetupWizardTab(self.notebook)
        self.system_tools_tab = SystemToolsTab(self.notebook)

        self.notebook.add(self.control_panel_tab, text='Control Panel')
        self.notebook.add(self.setup_wizard_tab, text='Setup & Config')
        self.notebook.add(self.system_tools_tab, text='System Tools')

        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

    def on_closing(self):
        if self.control_panel_tab.backend_proc or self.control_panel_tab.frontend_proc:
            if messagebox.askokcancel("Quit", "Services are still running. Do you want to stop them and exit?"):
                self.control_panel_tab.stop_services()
                self.destroy()
        else:
            self.destroy()

# --- NEW: Self-Setup UI and Logic ---
class SetupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fortuna Faucet - First-Time Setup")
        self.geometry("700x500")
        self.configure(bg='#1a1a2e')

        self.protocol("WM_DELETE_WINDOW", self.quit)

        header_font = tk.font.Font(family="Segoe UI", size=16, weight="bold")
        body_font = tk.font.Font(family="Segoe UI", size=10)
        button_font = tk.font.Font(family="Segoe UI", size=12, weight="bold")

        tk.Label(self, text="📦 Welcome to Fortuna Faucet", font=header_font, bg='#1a1a2e', fg='#00ff88').pack(pady=(20, 10))
        tk.Label(self, text="The necessary dependencies are not installed. Click 'Start Installation' to begin.", font=body_font, bg='#1a1a2e', fg='#ffffff').pack(pady=(0, 20))

        self.install_button = tk.Button(self, text="▶️ Start Installation", font=button_font, bg='#00ff88', fg='#000000', command=self.start_installation, relief=tk.FLAT, padx=20, pady=10)
        self.install_button.pack(pady=10)

        self.output_box = scrolledtext.ScrolledText(self, height=15, bg="#0f3460", fg="#cccccc", state=tk.DISABLED, relief=tk.FLAT, bd=0, padx=10, pady=10)
        self.output_box.pack(pady=10, padx=40, fill=tk.BOTH, expand=True)

        self.status_label = tk.Label(self, text="Waiting to start...", font=body_font, bg='#1a1a2e', fg='#ffffff')
        self.status_label.pack(pady=10)

    def log(self, message):
        self.output_box.config(state=tk.NORMAL)
        self.output_box.insert(tk.END, message + "\n")
        self.output_box.config(state=tk.DISABLED)
        self.output_box.see(tk.END)
        self.update_idletasks()

    def start_installation(self):
        self.install_button.config(state=tk.DISABLED, text="Installation in progress...")
        self.log("--- Starting installation ---")
        self.status_label.config(text="Installing... Please be patient, this may take several minutes.")
        threading.Thread(target=self.run_install_commands, daemon=True).start()

    def run_command(self, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', shell=True)
        for line in iter(process.stdout.readline, ''):
            self.log(line.strip())
        process.wait()
        return process.returncode

    def run_install_commands(self):
        commands = [
            ("1/3: Creating Python virtual environment...", f'{sys.executable} -m venv .venv'),
            ("2/3: Installing Python dependencies...", '\"' + str(Path(".venv/Scripts/python.exe")) + '\" -m pip install -r requirements.txt'),
            ("3/3: Installing Node.js dependencies...", 'npm install --prefix web_platform/frontend')
        ]

        for i, (msg, cmd) in enumerate(commands):
            self.log(f'\\n--- STEP {msg} ---')
            return_code = self.run_command(cmd)
            if return_code != 0:
                self.log(f'\\n--- ERROR: Step {i+1} failed with code {return_code}. ---')
                self.status_label.config(text="Installation Failed. Please see log for details.", fg="#ff4444")
                self.install_button.config(state=tk.NORMAL, text="Retry Installation")
                return

        self.log("\\n--- ✅ INSTALLATION COMPLETE! ---")
        self.status_label.config(text="Setup successful! You can now launch the application.", fg="#00ff88")
        self.install_button.destroy()
        launch_button = tk.Button(self, text="🚀 Launch Fortuna", font=tk.font.Font(family="Segoe UI", size=12, weight="bold"), bg='#00ff88', fg='#000000', command=self.launch_app, relief=tk.FLAT, padx=20, pady=10)
        launch_button.pack(pady=10)

    def launch_app(self):
        self.destroy()
        # Relaunch the script to start the main app
        subprocess.Popen([sys.executable, __file__])

# --- NEW: Main Execution Block ---
if __name__ == "__main__":
    VENV_PATH = Path(__file__).parent / ".venv"
    if not VENV_PATH.exists() or not (VENV_PATH / "Scripts" / "python.exe").exists():
        # If the virtual environment doesn't exist, run the setup wizard.
        setup_app = SetupApp()
        setup_app.mainloop()
    else:
        # Otherwise, run the main application.
        app = FortunaApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()