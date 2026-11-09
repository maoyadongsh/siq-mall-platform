"""Run an opt-in 100k-product read smoke on a disposable local MariaDB instance."""

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymysql

from smoke import free_port, wait_for_port

PROJECT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT / "backend"


def request(url, access):
    started = time.monotonic()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"}),
            timeout=30,
        ) as response:
            payload = json.load(response)
        assert response.status == 200 and payload["data"]["count"] == 100000
        assert len(payload["data"]["results"]) == 100
        return time.monotonic() - started, None
    except urllib.error.HTTPError as exc:
        return time.monotonic() - started, f"HTTP{exc.code}"
    except Exception as exc:
        return time.monotonic() - started, type(exc).__name__


def run(work):
    bin_dir = Path(os.environ.get("SIQ_MARIADB_BIN", r"C:\Program Files\MariaDB 11.8\bin"))
    db_port, api_port = free_port(), free_port()
    password = secrets.token_hex(24)
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parent),
        "PYTHONUTF8": "1",
        "DJANGO_SETTINGS_MODULE": "siq_accept_settings",
        "MALL_ALLOW_SCALE_SEED": "1",
        "SIQ_TEST_PASSWORD": password,
        "SIQ_TEST_MEDIA_ROOT": str(work / "media"),
        "SIQ_TEST_PORT": str(db_port),
        "SIQ_BROWSER_URL": "http://127.0.0.1",
    }
    data = work / "data"
    init = subprocess.run(
        [bin_dir / "mariadb-install-db.exe", f"--datadir={data}", f"--password={password}", f"--port={db_port}", "--silent"],
        stdout=subprocess.DEVNULL,
    )
    if init.returncode:
        raise RuntimeError("Could not initialize the temporary MariaDB data directory")
    db = subprocess.Popen(
        [bin_dir / "mariadbd.exe", f"--defaults-file={data}/my.ini", f"--port={db_port}", "--bind-address=127.0.0.1"],
        cwd=work,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    api = None
    try:
        wait_for_port(db_port, db)
        with pymysql.connect(host="127.0.0.1", port=db_port, user="root", password=password, autocommit=True) as conn:
            with conn.cursor() as cursor:
                cursor.execute("CREATE DATABASE siq_accept CHARACTER SET utf8mb4")
        def django(args):
            return subprocess.run([sys.executable, *args], cwd=BACKEND, env=env, check=True)
        django(["manage.py", "migrate", "--noinput", "--verbosity=0"])
        django(["manage.py", "seed_catalog_scale", "--products", "100000", "--skus", "3", "--prefix", "scale100k"])
        api = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"127.0.0.1:{api_port}", "--noreload"],
            cwd=BACKEND,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        wait_for_port(api_port, api)
        with pymysql.connect(host="127.0.0.1", port=db_port, user="root", password=password, database="siq_accept") as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM catalog_category WHERE name='scale100k-category-0'")
                category_id = cursor.fetchone()[0]
                cursor.execute(f"EXPLAIN SELECT id,title FROM catalog_product WHERE status='on_sale' AND category_id={category_id} ORDER BY id DESC LIMIT 100")
                print(f"EXPLAIN 100k: {cursor.fetchall()}")
                cursor.execute("SELECT id FROM catalog_category WHERE name='scale100k-root'")
                root_id = cursor.fetchone()[0]
        url = f"http://127.0.0.1:{api_port}/api/v1/products/?category={root_id}&sort=price_asc&page_size=100"
        django([
            "manage.py",
            "shell",
            "-c",
            "import os; from django.contrib.auth.models import User; User.objects.create_user('scale_buyer', password=os.environ['SIQ_TEST_PASSWORD'])",
        ])
        login = urllib.request.Request(
            f"http://127.0.0.1:{api_port}/api/v1/auth/mini/login/",
            data=json.dumps({"identifier": "scale_buyer", "password": password}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(login, timeout=30) as response:
            access = json.load(response)["data"]["access"]
        for _ in range(5):
            duration, error = request(url, access)
            assert error is None, error
        durations = []
        started = time.monotonic()
        for _ in range(50):
            duration, error = request(url, access)
            assert error is None, error
            durations.append(duration)
        durations.sort()
        print(f"100k serial x50: p95={durations[47]:.4f}s, max={durations[-1]:.4f}s")
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _: request(url, access), range(100)))
        durations = sorted(result[0] for result in results)
        errors = [result[1] for result in results if result[1]]
        assert not errors, errors
        print(f"100k concurrent20 x100: p95={durations[94]:.4f}s, max={durations[-1]:.4f}s, elapsed={time.monotonic()-started:.2f}s")
    finally:
        if api:
            api.terminate()
            api.wait(timeout=10)
        db.terminate()
        db.wait(timeout=10)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="siq-scale-100k-") as temp:
        run(Path(temp))
