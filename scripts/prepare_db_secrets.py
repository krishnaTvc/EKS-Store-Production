"""Use one validated AWS source to build all database credentials, never log them."""
import json
import os
import subprocess
from urllib.parse import quote, urlsplit, unquote
import boto3


def require(data, key):
    value = data.get(key)
    if value is None or not isinstance(value, (str, int)) or str(value) == "":
        raise ValueError(f"Missing/invalid Secrets Manager field: {key}")
    return str(value)


def connection_values(master, application, database, expected_user):
    host = require(master, "host")
    port = require(master, "port")
    user = require(application, "username")
    password = require(application, "password")
    if user != expected_user or require(application, "dbname") != database:
        raise ValueError(f"Unexpected application username/database for {database}")
    if require(application, "host") != host or require(application, "port") != port:
        raise ValueError(f"Application and master database endpoints differ for {database}")
    # Reject inconsistent existing URLs instead of silently using a stale password.
    existing = application.get("DATABASE_URL")
    if existing:
        parsed = urlsplit(existing)
        if (parsed.hostname != host or parsed.port != int(port) or
                unquote(parsed.username or "") != user or
                unquote(parsed.password or "") != password or parsed.path != "/" + database):
            raise ValueError(f"DATABASE_URL disagrees with secret fields for {database}; repair the source secret")
    sslmode = os.environ.get("PGSSLMODE", "verify-full")
    return f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}?sslmode={sslmode}"


def manifests(master, catalog, orders):
    catalog_url = connection_values(master, catalog, "catalog", "catalog_user")
    order_url = connection_values(master, orders, "orders", "order_user")
    values = {
        "eks-store-bootstrap-db-credentials": {
            "RDS_HOST": require(master, "host"), "RDS_PORT": require(master, "port"),
            "RDS_MASTER_USER": require(master, "master_username"),
            "RDS_MASTER_PASSWORD": require(master, "master_password"),
            "CATALOG_DB_PASSWORD": require(catalog, "password"),
            "ORDER_DB_PASSWORD": require(orders, "password"),
        },
        "eks-store-catalog-db": {"DATABASE_URL": catalog_url},
        "eks-store-orders-db": {"DATABASE_URL": order_url},
    }
    return [{"apiVersion": "v1", "kind": "Secret", "metadata": {"name": name, "namespace": "eks-store"},
             "type": "Opaque", "stringData": data} for name, data in values.items()]


def main():
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    prefix = f"eks-store/{os.environ['ENVIRONMENT']}"
    def read(suffix):
        return json.loads(client.get_secret_value(SecretId=prefix + "/" + suffix)["SecretString"])
    objects = manifests(read("rds/master"), read("catalog-db"), read("order-db"))
    for obj in objects:
        # Server-side apply avoids putting plaintext stringData in last-applied annotations.
        # Use data for stable server-side apply semantics (stringData is write-only).
        import base64
        obj["data"] = {key: base64.b64encode(value.encode()).decode() for key, value in obj.pop("stringData").items()}
        subprocess.run(["kubectl", "apply", "--server-side", "--field-manager=eks-store-release", "-f", "-"],
                       input=json.dumps(obj), text=True, check=True, capture_output=True)
    print("Validated database configuration and applied three dedicated Kubernetes Secrets.")


if __name__ == "__main__":
    main()
