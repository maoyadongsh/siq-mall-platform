"""Run the address/catalog smoke suite with a disposable local MariaDB instance."""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pymysql

PROJECT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT / "backend"
FRONTEND = PROJECT / "frontend"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError(f"Test service exited before opening port {port}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Test service on port {port} did not start")


def run_suite(work):
    bin_dir = Path(
        os.environ.get("SIQ_MARIADB_BIN", r"C:\Program Files\MariaDB 11.8\bin")
    )
    ports = set()
    while len(ports) < 3:
        ports.add(free_port())
    db_port, api_port, web_port = ports
    password = secrets.token_hex(24)
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parent),
        "PYTHONUTF8": "1",
        "DJANGO_SETTINGS_MODULE": "siq_accept_settings",
        "SIQ_TEST_PASSWORD": password,
        "SIQ_TEST_MEDIA_ROOT": str(work / "media"),
        "SIQ_TEST_PORT": str(db_port),
        "SIQ_BROWSER_URL": f"http://127.0.0.1:{web_port}",
        "VITE_PROXY_TARGET": f"http://127.0.0.1:{api_port}",
    }
    processes = []

    def start(args, cwd, port):
        process = subprocess.Popen(
            args, cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW
        )
        processes.append(process)
        wait_for_port(port, process)

    def django(args):
        subprocess.run([sys.executable, *args], cwd=BACKEND, env=env, check=True)

    data = work / "data"
    init = subprocess.run(
        [
            bin_dir / "mariadb-install-db.exe",
            f"--datadir={data}",
            f"--password={password}",
            f"--port={db_port}",
            "--silent",
        ],
        stdout=subprocess.DEVNULL,
    )
    if init.returncode:
        raise RuntimeError("Could not initialize the temporary MariaDB data directory")
    try:
        start(
            [
                bin_dir / "mariadbd.exe",
                f"--defaults-file={data}/my.ini",
                f"--port={db_port}",
                "--bind-address=127.0.0.1",
            ],
            work,
            db_port,
        )
        with pymysql.connect(
            host="127.0.0.1",
            port=db_port,
            user="root",
            password=password,
            autocommit=True,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("CREATE DATABASE siq_accept CHARACTER SET utf8mb4")
        django(
            [
                "-m",
                "pytest",
                "--ds=siq_accept_settings",
                "users/tests/test_address_races.py",
                "catalog/tests/test_stock_races.py",
                "--no-cov",
            ]
        )
        django(["manage.py", "migrate", "--noinput", "--verbosity=0"])
        django(
            [
                "manage.py",
                "shell",
                "-c",
                "import os; from django.contrib.auth.models import User,Group; user=User.objects.create_user('accept_operator',password=os.environ['SIQ_TEST_PASSWORD']); user.groups.add(Group.objects.get(name='catalog_operator'))",
            ]
        )
        start(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{api_port}",
                "--noreload",
            ],
            BACKEND,
            api_port,
        )
        start(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                str(web_port),
                "--strictPort",
            ],
            FRONTEND,
            web_port,
        )
        subprocess.run(
            ["node", "e2e/acceptance.cjs"],
            cwd=FRONTEND,
            env=env,
            check=True,
            timeout=150,
        )
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="siq-acceptance-") as temp:
        run_suite(Path(temp))
