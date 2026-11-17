"""
SATHACK - One-click local server launcher (Windows)

Save this file as:
    D:\projects\SATHACK\start_sathack.py

Run from PowerShell:
    cd D:\projects\SATHACK
    python start_sathack.py

This opens separate terminal windows for:
  1. Frontend: 127.0.0.1:5500
  2. FastAPI:  127.0.0.1:8000
  3. Proxy:    127.0.0.1:9000
  4. ngrok:    public HTTPS tunnel -> localhost:9000

It does not delete or modify any project files.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "FrontEnd"
BACKEND_DIR = ROOT / "BackEnd"
PROXY_FILE = ROOT / "proxy.py"

FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = "5500"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = "8000"
PROXY_PORT = "9000"

# Use the project's virtual environment for FastAPI, if it exists.
VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
BACKEND_PYTHON = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable

CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
processes: list[tuple[str, subprocess.Popen]] = []


def check_files() -> None:
    required = [
        ("Frontend folder", FRONTEND_DIR),
        ("Backend folder", BACKEND_DIR),
        ("Proxy file", PROXY_FILE),
    ]
    missing = [f"{label}: {path}" for label, path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "The following required project paths were not found:\n"
            + "\n".join(missing)
            + "\n\nKeep start_sathack.py in D:\\projects\\SATHACK."
        )


def launch(name: str, command: list[str], cwd: Path) -> None:
    print(f"[STARTING] {name}")
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        creationflags=CREATE_NEW_CONSOLE,
    )
    processes.append((name, proc))
    print(f"[OPENED]   {name} (PID {proc.pid})")


def stop_all() -> None:
    print("\nStopping the services started by this launcher...")
    for name, proc in reversed(processes):
        if proc.poll() is None:
            print(f"[STOPPING] {name} (PID {proc.pid})")
            # Stop the process and any child processes it created.
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    print("Stop command sent. You can close this launcher window.")


def main() -> int:
    if sys.platform != "win32":
        print("This launcher is intended for Windows.")
        return 1

    try:
        check_files()
    except FileNotFoundError as exc:
        print(exc)
        input("\nPress Enter to exit...")
        return 1

    ngrok = shutil.which("ngrok")
    if not ngrok:
        print(
            "ngrok was not found in PATH.\n"
            "Install ngrok or add its executable to PATH, then run this file again."
        )
        input("\nPress Enter to exit...")
        return 1

    print("=" * 62)
    print(" SATHACK SERVER LAUNCHER")
    print("=" * 62)
    print(f"Project:  {ROOT}")
    print(f"Backend Python: {BACKEND_PYTHON}")
    print("\nStarting services in separate terminal windows...\n")

    try:
        # 1. Static frontend server
        launch(
            "SATHACK Frontend (port 5500)",
            [
                sys.executable, "-m", "http.server",
                FRONTEND_PORT, "--bind", FRONTEND_HOST,
            ],
            FRONTEND_DIR,
        )

        time.sleep(1)

        # 2. FastAPI backend
        launch(
            "SATHACK FastAPI Backend (port 8000)",
            [
                BACKEND_PYTHON, "-m", "uvicorn", "main:app",
                "--host", BACKEND_HOST, "--port", BACKEND_PORT,
            ],
            BACKEND_DIR,
        )

        time.sleep(1)

        # 3. Reverse proxy
        launch(
            "SATHACK Reverse Proxy (port 9000)",
            [sys.executable, str(PROXY_FILE)],
            ROOT,
        )

        time.sleep(2)

        # 4. Public ngrok tunnel
        launch(
            "SATHACK ngrok Tunnel",
            [ngrok, "http", PROXY_PORT],
            ROOT,
        )

    except Exception as exc:
        print(f"\nCould not start all services: {exc}")
        stop_all()
        input("\nPress Enter to exit...")
        return 1

    print("\n" + "=" * 62)
    print(" LAUNCH COMMANDS SENT")
    print("=" * 62)
    print("Local website:  http://127.0.0.1:9000")
    print("Frontend:       http://127.0.0.1:5500")
    print("Backend docs:   http://127.0.0.1:9000/api/docs")
    print("ngrok status:   http://127.0.0.1:4040")
    print("\nFind the HTTPS Forwarding URL in the ngrok terminal window.")
    print("Share that HTTPS URL with other users.")
    print("\nKeep all four service windows and this launcher running.")
    print("Press Ctrl+C here, or Enter, to stop the processes started by this file.")

    try:
        input("\nPress Enter when you want to stop all services...")
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
