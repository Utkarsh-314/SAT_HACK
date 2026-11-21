
"""
SATHACK - Windows server launcher

Frontend:       127.0.0.1:5500
FastAPI:        127.0.0.1:8000
Reverse Proxy:  127.0.0.1:9000
ngrok:          HTTPS -> localhost:9000

Run:
    cd D:\projects\SATHACK
    python start_sathack.py
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time

from pathlib import Path


ROOT = Path(__file__).resolve().parent

FRONTEND_DIR = ROOT / "FrontEnd"
BACKEND_DIR = ROOT / "BackEnd"
PROXY_FILE = ROOT / "proxy.py"

HOST = "127.0.0.1"

FRONTEND_PORT = 5500
BACKEND_PORT = 8000
PROXY_PORT = 9000

VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"

BACKEND_PYTHON = (
    str(VENV_PYTHON)
    if VENV_PYTHON.is_file()
    else sys.executable
)

CREATE_NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE

processes = []


# ==========================================
# CHECK FILES
# ==========================================

def check_files():

    required = [
        ("Frontend folder", FRONTEND_DIR),
        ("Backend folder", BACKEND_DIR),
        ("Proxy file", PROXY_FILE),
    ]

    missing = [
        f"{name}: {path}"
        for name, path in required
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "\n".join(missing)
        )


# ==========================================
# CHECK PORT
# ==========================================

def check_port_free(port):

    try:

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        ) as sock:

            sock.bind((HOST, port))

        return True

    except OSError:

        return False


def wait_for_port(port, timeout=20):

    print(f"[WAITING] {HOST}:{port}")

    start = time.monotonic()

    while time.monotonic() - start < timeout:

        try:

            with socket.create_connection(
                (HOST, port),
                timeout=1
            ):

                print(f"[READY] {HOST}:{port}")
                return True

        except OSError:

            time.sleep(0.5)

    return False


# ==========================================
# START WINDOWS WITH VISIBLE ERRORS
# ==========================================

def launch(name, command, cwd):

    print(f"\n[STARTING] {name}")

    command_line = subprocess.list2cmdline(command)

    proc = subprocess.Popen(

        [
            "cmd.exe",
            "/k",
            command_line
        ],

        cwd=str(cwd),

        creationflags=CREATE_NEW_CONSOLE

    )

    processes.append((name, proc))

    print(
        f"[OPENED] {name} | PID: {proc.pid}"
    )

    return proc


# ==========================================
# STOP SERVICES
# ==========================================

def stop_all():

    print("\nStopping SATHACK services...")

    for name, proc in reversed(processes):

        if proc.poll() is None:

            print(f"[STOPPING] {name}")

            subprocess.run(

                [
                    "taskkill",
                    "/PID",
                    str(proc.pid),
                    "/T",
                    "/F"
                ],

                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False

            )

    print("All launcher processes stopped.")


# ==========================================
# WAIT FOR SERVICE
# ==========================================

def start_and_check(name, command, cwd, port):

    launch(name, command, cwd)

    if not wait_for_port(port):

        raise RuntimeError(
            f"{name} did not start on port {port}. "
            "Check its terminal window for the actual error."
        )


# ==========================================
# MAIN
# ==========================================

def main():

    if sys.platform != "win32":

        print("This launcher requires Windows.")

        return 1

    try:

        check_files()

    except FileNotFoundError as error:

        print(error)

        input("Press Enter to exit...")

        return 1


    # Check ngrok

    ngrok = shutil.which("ngrok")

    if not ngrok:

        print(
            "ngrok was not found in PATH. "
            "Install ngrok or add it to PATH."
        )

        input("Press Enter to exit...")

        return 1


    # Check required ports

    for port in [
        FRONTEND_PORT,
        BACKEND_PORT,
        PROXY_PORT
    ]:

        if not check_port_free(port):

            print(
                f"\nPort {port} is already occupied."
            )

            print(
                "Close the existing service or identify "
                "the process using this port before restarting."
            )

            input("\nPress Enter to exit...")

            return 1


    print("=" * 60)
    print(" SATHACK SERVER LAUNCHER")
    print("=" * 60)

    print("Project:", ROOT)

    print("Backend Python:", BACKEND_PYTHON)

    print("\nStarting services...\n")


    try:

        # ----------------------------------
        # 1. FRONTEND
        # ----------------------------------

        start_and_check(

            "SATHACK Frontend",

            [
                sys.executable,
                "-m",
                "http.server",
                str(FRONTEND_PORT),
                "--bind",
                HOST
            ],

            FRONTEND_DIR,

            FRONTEND_PORT

        )


        # ----------------------------------
        # 2. FASTAPI BACKEND
        # ----------------------------------

        start_and_check(

            "SATHACK FastAPI",

            [
                BACKEND_PYTHON,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                HOST,
                "--port",
                str(BACKEND_PORT)
            ],

            BACKEND_DIR,

            BACKEND_PORT

        )


        # ----------------------------------
        # 3. REVERSE PROXY
        # ----------------------------------

        start_and_check(

            "SATHACK Reverse Proxy",

            [
                BACKEND_PYTHON,
                str(PROXY_FILE)
            ],

            ROOT,

            PROXY_PORT

        )


        # ----------------------------------
        # 4. NGROK
        # ----------------------------------

        launch(

            "SATHACK ngrok",

            [
                ngrok,
                "http",
                str(PROXY_PORT)
            ],

            ROOT

        )


        print("\n" + "=" * 60)

        print(" ALL SERVICES LAUNCHED")

        print("=" * 60)

        print(
            f"Frontend:  http://{HOST}:{FRONTEND_PORT}"
        )

        print(
            f"Backend:   http://{HOST}:{BACKEND_PORT}"
        )

        print(
            f"Proxy:     http://{HOST}:{PROXY_PORT}"
        )

        print(
            f"API Docs:  http://{HOST}:{PROXY_PORT}/api/docs"
        )

        print(
            "ngrok:     http://127.0.0.1:4040"
        )

        print("\nOpen the Proxy URL for normal testing.")

        print(
            "\nFind the public HTTPS forwarding address "
            "in the ngrok terminal."
        )

        input(
            "\nPress Enter to stop all services..."
        )

    except KeyboardInterrupt:

        print("\nLauncher interrupted.")

    except Exception as error:

        print("\nSERVICE STARTUP ERROR:")
        print(error)

        print(
            "\nCheck the opened terminal windows. "
            "Their error messages have been kept visible."
        )

        input("\nPress Enter to stop launched services...")

    finally:

        stop_all()

    return 0


if __name__ == "__main__":

    raise SystemExit(main())
