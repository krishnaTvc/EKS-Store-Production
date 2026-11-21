"""
RDS Database Bootstrap Utility
Connects using RDS master credentials to provision logical databases, application users,
and schema grants for catalog-service and order-service.
Idempotent and safe to run as a pre-deploy Kubernetes Job.
"""

import os
import sys
import logging
from pathlib import Path
from urllib.parse import quote_plus
import psycopg
from psycopg import sql

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bootstrap_databases")


def get_connection_params():
    """Resolves master connection parameters securely."""
    # Check if secrets directory is mounted
    secret_dir_env = os.getenv("DB_SECRET_DIR") or os.getenv("DATABASE_SECRET_DIR")
    if secret_dir_env and os.path.isdir(secret_dir_env):
        s_path = Path(secret_dir_env)
        host = (s_path / "host").read_text().strip() if (s_path / "host").is_file() else None
        port = (s_path / "port").read_text().strip() if (s_path / "port").is_file() else "5432"
        user = (s_path / "master_username").read_text().strip() if (s_path / "master_username").is_file() else None
        password = (s_path / "master_password").read_text().strip() if (s_path / "master_password").is_file() else None
        if host and user and password:
            return host, port, user, password

    host = (os.getenv("RDS_HOST") or os.getenv("DB_HOST", "localhost")).strip()
    port = (os.getenv("RDS_PORT") or os.getenv("DB_PORT", "5432")).strip()
    user = (os.getenv("RDS_MASTER_USER") or os.getenv("DB_MASTER_USER", "postgres")).strip()
    password = (os.getenv("RDS_MASTER_PASSWORD") or os.getenv("DB_MASTER_PASSWORD", "postgrespassword")).strip()
    return host, port, user, password


def get_app_credentials():
    secret_dir_env = os.getenv("DB_SECRET_DIR") or os.getenv("DATABASE_SECRET_DIR")
    if secret_dir_env and os.path.isdir(secret_dir_env):
        s_path = Path(secret_dir_env)
        cat_p = (s_path / "catalog_password").read_text().strip() if (s_path / "catalog_password").is_file() else None
        ord_p = (s_path / "order_password").read_text().strip() if (s_path / "order_password").is_file() else None
        if cat_p and ord_p:
            return cat_p, ord_p
    catalog_pass = (os.getenv("CATALOG_DB_PASSWORD") or "catalog_pass").strip()
    order_pass = (os.getenv("ORDER_DB_PASSWORD") or "order_pass").strip()
    return catalog_pass, order_pass


def bootstrap():
    host, port, master_user, master_pass = get_connection_params()
    catalog_pass, order_pass = get_app_credentials()

    logger.info(f"Connecting to PostgreSQL host {host}:{port} as user '{master_user}'...")

    sslmode = os.getenv("PGSSLMODE", "prefer")
    sslrootcert = os.getenv("PGSSLROOTCERT")

    conn_kwargs = {
        "host": host,
        "port": port,
        "user": master_user,
        "password": master_pass,
        "dbname": "postgres",
        "autocommit": True,
        "sslmode": sslmode,
    }
    if sslrootcert and os.path.isfile(sslrootcert):
        conn_kwargs["sslrootcert"] = sslrootcert

    try:
        with psycopg.connect(**conn_kwargs) as conn:
            with conn.cursor() as cur:
                # 1. Create Application Users if they do not exist
                logger.info("Ensuring application roles exist...")

                for username, password in [("catalog_user", catalog_pass), ("order_user", order_pass)]:
                    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
                    if not cur.fetchone():
                        logger.info(f"Creating role '{username}'...")
                        cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(username)), (password,))
                    else:
                        logger.info(f"Role '{username}' already exists. Updating password...")
                        cur.execute(sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(sql.Identifier(username)), (password,))

                # 2. Create Logical Databases if they do not exist
                logger.info("Ensuring logical databases exist...")
                for dbname, owner in [("catalog", "catalog_user"), ("orders", "order_user")]:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
                    if not cur.fetchone():
                        logger.info(f"Creating database '{dbname}' with owner '{owner}'...")
                        cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(dbname),
                            sql.Identifier(owner)
                        ))
                    else:
                        logger.info(f"Database '{dbname}' already exists.")

        # 3. Configure database-level permissions on each database
        for dbname, owner in [("catalog", "catalog_user"), ("orders", "order_user")]:
            logger.info(f"Granting schema permissions on '{dbname}' to '{owner}'...")
            db_conn_kwargs = dict(conn_kwargs)
            db_conn_kwargs["dbname"] = dbname
            with psycopg.connect(**db_conn_kwargs) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("GRANT ALL ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(owner)))
                    try:
                        cur.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(owner)))
                    except Exception as schema_err:
                        logger.warning(f"Could not alter public schema owner on {dbname}: {schema_err}")
                    cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(owner)))
                    cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}").format(sql.Identifier(owner)))
                    cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}").format(sql.Identifier(owner)))

        # 4. Self-test connection as catalog_user and order_user
        for dbname, user, pwd in [("catalog", "catalog_user", catalog_pass), ("orders", "order_user", order_pass)]:
            logger.info(f"Verifying live connection as '{user}' to database '{dbname}'...")
            test_kwargs = dict(conn_kwargs)
            test_kwargs["dbname"] = dbname
            test_kwargs["user"] = user
            test_kwargs["password"] = pwd
            with psycopg.connect(**test_kwargs) as test_conn:
                with test_conn.cursor() as test_cur:
                    test_cur.execute("SELECT current_user, current_database()")
                    row = test_cur.fetchone()
                    logger.info(f"Verified connection: user='{row[0]}', database='{row[1]}'!")

        logger.info("Database bootstrap completed successfully.")
        return 0

    except Exception as e:
        logger.error(f"Database bootstrap failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(bootstrap())
