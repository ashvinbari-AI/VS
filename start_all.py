#!/usr/bin/env python3
"""
Political Person Social Media Intelligence -- one-command local launcher.

Starts the FastAPI backend (backend/.venv) and the React/Vite frontend
(frontend/node_modules) as two subprocesses, waits for each to actually
come up, and prints the URLs. Never touches your existing Instagram/Facebook
scrapers -- this only launches the platform built around them.

Usage:
    python start_all.py
    python start_all.py --backend-port 8010 --frontend-port 5180
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def find_free_port(preferred: int) -> int:
    port = preferred
    while not is_port_free(port):
        print(f"  ! port {port} is in use -- trying {port + 1}")
        port += 1
    return port


def venv_python() -> Path:
    venv = BACKEND_DIR / ".venv"
    candidate = venv / "Scripts" / "python.exe"  # Windows
    if candidate.exists():
        return candidate
    candidate = venv / "bin" / "python"  # just in case (WSL/mac)
    if candidate.exists():
        return candidate
    print("  ! backend/.venv not found -- creating it and installing requirements.")
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    pip_python = venv / "Scripts" / "python.exe" if (venv / "Scripts").exists() else venv / "bin" / "python"
    subprocess.run([str(pip_python), "-m", "pip", "install", "--quiet", "-r",
                     str(BACKEND_DIR / "requirements.txt")], check=True)
    return pip_python


def ensure_frontend_deps() -> None:
    if not (FRONTEND_DIR / "node_modules").exists():
        print("  Installing frontend dependencies (npm install)...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True, shell=(sys.platform == "win32"))


def wait_for(url: str, timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend-port", type=int, default=8000)
    ap.add_argument("--frontend-port", type=int, default=5173)
    args = ap.parse_args()

    backend_port = find_free_port(args.backend_port)
    frontend_port = find_free_port(args.frontend_port)

    print("Verifying Python environment...")
    python = venv_python()

    print("Verifying frontend dependencies...")
    ensure_frontend_deps()

    print(f"\nStarting FastAPI backend on port {backend_port}...")
    backend_proc = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--port", str(backend_port)],
        cwd=str(BACKEND_DIR),
    )

    if not wait_for(f"http://127.0.0.1:{backend_port}/api/health"):
        print("  ! backend did not come up in time -- check backend/logs/backend.log")

    print(f"Starting React/Vite frontend on port {frontend_port}...")
    # Vite's dev proxy (frontend/vite.config.ts) targets 127.0.0.1:8000 --
    # if you changed --backend-port, edit that file's proxy target too.
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(frontend_port)],
        cwd=str(FRONTEND_DIR), shell=(sys.platform == "win32"),
    )

    print(f"""
================================================
  Political Person Intelligence
================================================

  Backend:    http://127.0.0.1:{backend_port}
  API docs:   http://127.0.0.1:{backend_port}/docs
  Frontend:   http://127.0.0.1:{frontend_port}

  LOCAL MODE -- nothing leaves this machine unless
  Gemini NLP is explicitly enabled in Settings.

  Press Ctrl+C to stop both processes.
================================================
""")

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    main()
