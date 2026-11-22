"""CI integration against a disposable PostgreSQL service, never production."""
import os
from pathlib import Path
import subprocess
import sys
import psycopg
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.environ.get("ALLOW_DISPOSABLE_DB_TEST") != "yes":
        raise RuntimeError("Set ALLOW_DISPOSABLE_DB_TEST=yes only for a disposable PostgreSQL server")
    env = os.environ.copy()
    env.update(RDS_HOST="127.0.0.1", RDS_PORT=env.get("TEST_PG_PORT", "5432"),
               RDS_MASTER_USER="postgres", RDS_MASTER_PASSWORD="integration-master",
               CATALOG_DB_PASSWORD="cat:@/%+test", ORDER_DB_PASSWORD="order:@/%+test", PGSSLMODE="disable")
    def run(args, cwd=ROOT, extra=None):
        subprocess.run(args, cwd=cwd, env={**env, **(extra or {})}, check=True)
    run([sys.executable, "scripts/bootstrap_databases.py"])
    # Exercise ALTER ROLE and replacement of pre-existing passwords on rerun.
    env["CATALOG_DB_PASSWORD"] = "new-cat:@/%+test"
    env["ORDER_DB_PASSWORD"] = "new-order:@/%+test"
    run([sys.executable, "scripts/bootstrap_databases.py"])
    urls = {}
    for folder, user, db, key in [("catalog-service", "catalog_user", "catalog", "CATALOG_DB_PASSWORD"),
                                  ("order-service", "order_user", "orders", "ORDER_DB_PASSWORD")]:
        url = URL.create("postgresql+psycopg", username=user, password=env[key], host="127.0.0.1",
                         port=int(env["RDS_PORT"]), database=db, query={"sslmode": "disable"})
        urls[db] = url.render_as_string(hide_password=False)
        run([sys.executable, "-m", "alembic", "upgrade", "head"], ROOT / folder, {"DATABASE_URL": urls[db]})
        with psycopg.connect(host="127.0.0.1", port=int(env["RDS_PORT"]), user=user, password=env[key],
                             dbname=db, sslmode="disable") as conn:
            assert conn.execute("select version_num from alembic_version").fetchone()
    for _ in range(2):
        run([sys.executable, "scripts/import_catalog.py"], extra={"DATABASE_URL": urls["catalog"]})
    with psycopg.connect(host="127.0.0.1", port=int(env["RDS_PORT"]), user="catalog_user",
                         password=env["CATALOG_DB_PASSWORD"], dbname="catalog", sslmode="disable") as conn:
        count, distinct = conn.execute("select count(*), count(distinct product_code) from catalog_items").fetchone()
        assert count > 0 and count == distinct
    print("PostgreSQL bootstrap rerun, encoded passwords, migrations and idempotent seeding passed.")


if __name__ == "__main__":
    main()
