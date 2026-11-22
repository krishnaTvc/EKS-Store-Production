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


def required_env(name):
    value = os.environ.get(name)
    if value is None or value == "":
        raise ValueError(f"Required bootstrap variable is missing: {name}")
    return value


def get_connection_params():
    return (required_env("RDS_HOST"), required_env("RDS_PORT"),
            required_env("RDS_MASTER_USER"), required_env("RDS_MASTER_PASSWORD"))


def get_app_credentials():
    return required_env("CATALOG_DB_PASSWORD"), required_env("ORDER_DB_PASSWORD")


def bootstrap():
    host, port, master_user, master_pass = get_connection_params()
    catalog_pass, order_pass = get_app_credentials()

    logger.info(f"Connecting to PostgreSQL host {host}:{port} as user '{master_user}'...")

    sslmode = os.getenv("PGSSLMODE", "verify-full")
    sslrootcert = os.getenv("PGSSLROOTCERT")

    conn_kwargs = {
        "host": host,
        "port": port,
        "user": master_user,
        "password": master_pass,
        "dbname": "postgres",
        "autocommit": True,
        "connect_timeout": 15,
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
                        cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(username), sql.Literal(password)))
                    else:
                        logger.info(f"Role '{username}' already exists. Updating password...")
                        cur.execute(sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(sql.Identifier(username), sql.Literal(password)))

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
