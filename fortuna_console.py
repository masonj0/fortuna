# fortuna_console.py
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import asyncio
from python_service import updater

class FortunaConsole(tk.Tk):
    SERVICE_NAME = "FortunaFaucetBackend"

    def __init__(self):
        super().__init__()
        self.title("Fortuna Faucet - System Console")
        self.geometry("600x550") # Increased height for updater

        notebook = ttk.Notebook(self, padding="10")
        notebook.pack(fill=tk.BOTH, expand=True)

        main_tab = ttk.Frame(notebook)
        updater_tab = ttk.Frame(notebook)

        notebook.add(main_tab, text='System Tools')
        notebook.add(updater_tab, text='Updater')

        self._create_service_controls(main_tab)
        self._create_diagnostics_controls(main_tab)
        self._create_config_controls(main_tab)
        self._create_updater_controls(updater_tab)

        self.get_service_status()

    def _create_updater_controls(self, parent):
        updater_frame = ttk.LabelFrame(parent, text="Application Updater", padding="10")
        updater_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        ttk.Button(updater_frame, text="Check for Updates", command=self.run_update_check).pack(pady=10)

        self.update_status_text = tk.Text(updater_frame, height=15, wrap=tk.WORD, state=tk.DISABLED, bg="#f0f0f0")
        self.update_status_text.pack(fill=tk.BOTH, expand=True)

    def run_update_check(self):
        self.update_status_text.config(state=tk.NORMAL)
        self.update_status_text.delete("1.0", tk.END)
        self.update_status_text.insert(tk.END, "Checking for updates...\n")
        self.update_status_text.config(state=tk.DISABLED)

        # Since Tkinter is not async-native, we run the async check in a separate thread
        import threading
        threading.Thread(target=lambda: asyncio.run(self.check_updates_async())).start()

    async def check_updates_async(self):
        update_info = await updater.check_for_updates()
        status = update_info.get("status")

        self.update_status_text.config(state=tk.NORMAL)
        self.update_status_text.delete("1.0", tk.END)

        if status == "update_available":
            self.update_status_text.insert(tk.END, f"Update Available!\n\n")
            self.update_status_text.insert(tk.END, f"  Current Version: {update_info['current_version']}\n")
            self.update_status_text.insert(tk.END, f"  Latest Version: {update_info['latest_version']}\n\n")
            self.update_status_text.insert(tk.END, "Release Notes:\n")
            self.update_status_text.insert(tk.END, f"{update_info['release_notes']}\n\n")

            if messagebox.askyesno("Update Found", "A new version is available. Do you want to download and install it now?"):
                self.download_and_run_installer(update_info['download_url'])

        elif status == "up_to_date":
            self.update_status_text.insert(tk.END, f"You are up to date.\n\nVersion: {update_info['current_version']}")
        else:
            self.update_status_text.insert(tk.END, f"Could not check for updates.\n\nReason: {update_info.get('message', 'Unknown error')}")

        self.update_status_text.config(state=tk.DISABLED)

    def download_and_run_installer(self, url):
        import requests
        import tempfile
        import os

        self.update_status_text.config(state=tk.NORMAL)
        self.update_status_text.insert(tk.END, "\nDownloading installer...")
        self.update_status_text.config(state=tk.DISABLED)
        self.update() # Force UI update

        try:
            r = requests.get(url, allow_redirects=True)
            r.raise_for_status()

            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, "Fortuna-Faucet-Setup.msi")

            with open(installer_path, 'wb') as f:
                f.write(r.content)

            self.update_status_text.config(state=tk.NORMAL)
            self.update_status_text.insert(tk.END, f"\nDownload complete. Starting installer...\n\nThis application will now close.")
            self.update_status_text.config(state=tk.DISABLED)
            self.update() # Force UI update

            os.startfile(installer_path)
            self.destroy() # Close the console

        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to download or run the installer: {e}")
            self.update_status_text.config(state=tk.NORMAL)
            self.update_status_text.insert(tk.END, f"\nUpdate failed: {e}")
            self.update_status_text.config(state=tk.DISABLED)

    def _create_service_controls(self, parent):
        service_frame = ttk.LabelFrame(parent, text="Service Controls", padding="10")
        service_frame.pack(fill=tk.X, pady=5)

        status_frame = ttk.Frame(service_frame)
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, text="Service Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="Checking...", font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(service_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Start Service", command=self.start_service).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stop Service", command=self.stop_service).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh Status", command=self.get_service_status).pack(side=tk.LEFT, padx=5)

    def _create_diagnostics_controls(self, parent):
        logs_frame = ttk.LabelFrame(parent, text="Diagnostics", padding="10")
        logs_frame.pack(fill=tk.X, pady=5)
        ttk.Button(logs_frame, text="Open Log File", command=self.open_log_file).pack(side=tk.LEFT, padx=5)

    def open_log_file(self):
        # Assuming the log file is in the same directory as the executable.
        # A more robust solution would read this from a config file.
        import os
        log_file_path = os.path.join(os.path.dirname(sys.argv[0]), "fortuna_service.log")
        try:
            os.startfile(log_file_path, 'open')
        except FileNotFoundError:
            messagebox.showinfo("Info", "Log file not found. The service may need to run first to generate it.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log file: {e}")

    def _create_config_controls(self, parent):
        config_frame = ttk.LabelFrame(parent, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        key_frame = ttk.Frame(config_frame)
        key_frame.pack(fill=tk.X, pady=5)

        ttk.Label(key_frame, text="TVG API Key:").pack(side=tk.LEFT, padx=(0, 5))
        self.api_key_var = tk.StringVar()
        ttk.Entry(key_frame, textvariable=self.api_key_var, width=50).pack(side=tk.LEFT, expand=True, fill=tk.X)

        button_frame = ttk.Frame(config_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.LEFT)

        self.load_config()

    def _get_env_path(self):
        # Assuming .env file is in the parent directory of the script's location
        # This might need to be adjusted based on the final installed structure
        import os
        import sys
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, ".env")

    def load_config(self):
        env_path = self._get_env_path()
        try:
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("TVG_API_KEY"):
                        key, value = line.strip().split("=", 1)
                        self.api_key_var.set(value.strip('\'"'))
                        return
        except FileNotFoundError:
            pass # File might not exist yet, that's fine.

    def save_config(self):
        env_path = self._get_env_path()
        lines = []
        key_found = False
        new_line = f'TVG_API_KEY="{self.api_key_var.get()}"'

        try:
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("TVG_API_KEY"):
                        lines.append(new_line + "\n")
                        key_found = True
                    else:
                        lines.append(line)
            if not key_found:
                lines.append(new_line + "\n")

            with open(env_path, "w") as f:
                f.writelines(lines)
            messagebox.showinfo("Success", "Configuration saved. Please restart the service for changes to take effect.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def _run_sc_command(self, command):
        try:
            result = subprocess.run(
                ["sc", command, self.SERVICE_NAME],
                capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            messagebox.showerror("Error", f"Failed to execute command: {e}")
            return None

    def get_service_status(self):
        self.status_label.config(text="Checking...")
        result = self._run_sc_command("query")
        if result:
            if "RUNNING" in result.stdout:
                self.status_label.config(text="RUNNING", foreground="green")
            elif "STOPPED" in result.stdout:
                self.status_label.config(text="STOPPED", foreground="red")
            else:
                self.status_label.config(text="UNKNOWN", foreground="gray")

    def start_service(self):
        self._run_sc_command("start")
        self.get_service_status()

    def stop_service(self):
        self._run_sc_command("stop")
        self.get_service_status()

if __name__ == "__main__":
    app = FortunaConsole()
    app.mainloop()
