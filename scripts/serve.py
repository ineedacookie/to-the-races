from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from collections.abc import Sequence


def port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def choose_port(requested: int | None) -> int:
    candidates = [requested] if requested is not None else [1515, 5151]
    for port in candidates:
        if port is not None and port_is_available(port):
            return port
    choices = ", ".join(str(port) for port in candidates)
    raise SystemExit(f"No preferred port is available ({choices}).")


def lan_address() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("8.8.8.8", 80))
            return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def run_checked(command: Sequence[str]) -> None:
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and run To The Races on the LAN.")
    parser.add_argument("--port", type=int, help="Override the preferred port.")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the Vite production build.",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip database migrations.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reload the ASGI process on code changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    if not args.skip_build:
        run_checked(["npm", "run", "build"])
    if not args.skip_migrate:
        run_checked([sys.executable, "manage.py", "migrate", "--noinput"])
    run_checked([sys.executable, "manage.py", "collectstatic", "--noinput"])
    run_checked([sys.executable, "manage.py", "seed_game"])

    port = choose_port(args.port)
    address = lan_address()
    print()
    print("To The Races is ready:")
    print(f"  Betting: http://{address}:{port}/bet/")
    print(f"  Display: http://{address}:{port}/display/")
    print(f"  Admin:   http://{address}:{port}/admin/")
    print()

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "config.asgi:application",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--workers",
        "1",
    ]
    if args.reload:
        command.append("--reload")
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
