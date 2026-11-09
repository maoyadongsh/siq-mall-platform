"""Run the address/catalog smoke suite with a disposable local MariaDB instance."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
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
        "MALL_ALLOW_SCALE_SEED": "1",
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
                "cart/tests/test_race.py",
                "orders/tests/test_races.py",
                "promotions/tests/test_races.py",
                "reviews/tests/test_races.py",
                "notifications/tests/test_races.py",
                "content/tests/test_races.py",
                "support/tests/test_races.py",
                "../qa/acceptance/test_delivery_boundaries.py",
                "--no-cov",
            ]
        )
        django(["manage.py", "migrate", "--noinput", "--verbosity=0"])
        django(
            [
                "manage.py",
                "shell",
                "-c",
                "import os; from django.contrib.auth.models import User,Group; user=User.objects.create_user('accept_operator',password=os.environ['SIQ_TEST_PASSWORD']); user.groups.add(Group.objects.get(name='catalog_operator'),Group.objects.get(name='order_operator'),Group.objects.get(name='promotion_operator'),Group.objects.get(name='content_operator')); moderator=User.objects.create_user('accept_moderator',password=os.environ['SIQ_TEST_PASSWORD']); moderator.groups.add(Group.objects.get(name='review_moderator')); agent=User.objects.create_user('accept_agent',password=os.environ['SIQ_TEST_PASSWORD']); agent.groups.add(Group.objects.get(name='support_supervisor')); access=User.objects.create_user('accept_access',password=os.environ['SIQ_TEST_PASSWORD']); access.groups.add(Group.objects.get(name='access_admin'),Group.objects.get(name='audit_viewer')); User.objects.create_user('accept_role_target',password=os.environ['SIQ_TEST_PASSWORD'])",
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
        worker = subprocess.Popen(
            [sys.executable, "manage.py", "process_order_events", "--watch"],
            cwd=BACKEND,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(worker)
        subprocess.run(
            ["node", "e2e/acceptance.cjs"],
            cwd=FRONTEND,
            env=env,
            check=True,
            timeout=240,
        )
        # Advance only the pending fixture's deadline inside this newly provisioned database.
        with pymysql.connect(
            host="127.0.0.1",
            port=db_port,
            user="root",
            password=password,
            database="siq_accept",
            autocommit=True,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(TIMESTAMPDIFF(MICROSECOND,e.occurred_at,n.created_at)/1000000) FROM orders_event e JOIN notifications_notification n ON n.event_id=e.event_id WHERE e.kind='order.paid'"
                )
                notification_lag = cursor.fetchone()[0]
                assert notification_lag is not None and 0 <= notification_lag <= 10
                cursor.execute(
                    "SELECT COUNT(*),COUNT(DISTINCT user_id,event_id,type) FROM notifications_notification"
                )
                notice_counts = cursor.fetchone()
                assert notice_counts[0] == notice_counts[1]
                print(
                    f"PASS notification max paid-event lag {notification_lag} seconds; no duplicate notices"
                )
                cursor.execute(
                    "UPDATE orders_order SET expires_at=UTC_TIMESTAMP(6)+INTERVAL 3 SECOND WHERE status='pending'"
                )
                assert cursor.rowcount == 1
                deadline = time.monotonic() + 93
                while time.monotonic() < deadline:
                    cursor.execute(
                        "SELECT TIMESTAMPDIFF(MICROSECOND,o.expires_at,e.occurred_at)/1000000 FROM orders_order o JOIN orders_event e ON e.order_id=o.id WHERE o.status='canceled' AND e.reason='timeout' AND e.delivered_at IS NOT NULL"
                    )
                    result = cursor.fetchone()
                    if result:
                        assert 0 <= result[0] <= 90
                        cursor.execute(
                            "SELECT COUNT(*) FROM orders_stockmovement m JOIN orders_orderitem i ON i.id=m.item_id JOIN orders_event e ON e.order_id=i.order_id WHERE m.kind='release' AND e.reason='timeout'"
                        )
                        assert cursor.fetchone()[0] == 1
                        print(
                            f"PASS worker timeout, single release, outbox delivered; close lag {result[0]} seconds"
                        )
                        break
                    if worker.poll() is not None:
                        raise RuntimeError("order worker exited")
                    time.sleep(0.5)
                else:
                    raise TimeoutError(
                        "pending order not closed and delivered within deadline"
                    )
                worker.terminate()
                worker.wait(timeout=10)
                processes.remove(worker)
                django(
                    [
                        "manage.py",
                        "seed_catalog_scale",
                        "--products",
                        "1000",
                        "--skus",
                        "1",
                        "--prefix",
                        "scale1k",
                    ]
                )
                cursor.execute("SELECT id FROM catalog_category WHERE name='scale1k-root'")
                scale_root = cursor.fetchone()[0]
                durations = []
                for _ in range(20):
                    started = time.monotonic()
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{api_port}/api/v1/products/?category={scale_root}&sort=price_asc&page_size=100",
                        timeout=10,
                    ) as response:
                        payload = json.load(response)
                    assert response.status == 200 and payload["data"]["count"] == 1000
                    durations.append(time.monotonic() - started)
                durations.sort()
                print(
                    f"PASS 1000-product MariaDB reads x20; p95={durations[18]:.4f}s, max={durations[-1]:.4f}s (local serial)"
                )
                cursor.execute(
                    "SELECT id FROM catalog_category WHERE name='scale1k-category-0'"
                )
                scale_category = cursor.fetchone()[0]
                cursor.execute(
                    f"EXPLAIN SELECT id,title FROM catalog_product WHERE status='on_sale' AND category_id={scale_category} ORDER BY id DESC LIMIT 100"
                )
                print(f"MariaDB EXPLAIN scale query: {cursor.fetchall()}")
                backup = work / "acceptance-backup.sql"
                with backup.open("wb") as output:
                    subprocess.run(
                        [
                            bin_dir / "mariadb-dump.exe",
                            "--protocol=tcp",
                            "--host=127.0.0.1",
                            f"--port={db_port}",
                            "--user=root",
                            "--single-transaction",
                            "--skip-lock-tables",
                            "siq_accept",
                        ],
                        env={**env, "MYSQL_PWD": password},
                        stdout=output,
                        check=True,
                    )
                with pymysql.connect(
                    host="127.0.0.1",
                    port=db_port,
                    user="root",
                    password=password,
                    autocommit=True,
                ) as conn:
                    with conn.cursor() as restore_cursor:
                        restore_cursor.execute(
                            "CREATE DATABASE siq_accept_restore CHARACTER SET utf8mb4"
                        )
                with backup.open("rb") as source:
                    subprocess.run(
                        [
                            bin_dir / "mariadb.exe",
                            "--protocol=tcp",
                            "--host=127.0.0.1",
                            f"--port={db_port}",
                            "--user=root",
                            "siq_accept_restore",
                        ],
                        env={**env, "MYSQL_PWD": password},
                        stdin=source,
                        check=True,
                    )
                for table in (
                    "orders_order",
                    "notifications_notification",
                    "content_contentrevision",
                    "support_supportmessage",
                ):
                    cursor.execute(
                        f"SELECT (SELECT COUNT(*) FROM siq_accept.{table}),(SELECT COUNT(*) FROM siq_accept_restore.{table})"
                    )
                    counts = cursor.fetchone()
                    assert counts[0] == counts[1], table
                print("PASS MariaDB dump -> isolated restore -> table count parity")
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="siq-acceptance-") as temp:
        run_suite(Path(temp))
