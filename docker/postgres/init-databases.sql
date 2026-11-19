-- PostgreSQL Initialization Script
-- Executed automatically on container first boot by /docker-entrypoint-initdb.d/

-- 1. Create Application Users
CREATE USER catalog_user WITH PASSWORD 'catalog_pass';
CREATE USER order_user WITH PASSWORD 'order_pass';

-- 2. Create Logical Databases with dedicated owners
CREATE DATABASE catalog OWNER catalog_user;
CREATE DATABASE orders OWNER order_user;

-- 3. Grant schema permissions for PostgreSQL 15+
\connect catalog
GRANT ALL ON SCHEMA public TO catalog_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO catalog_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO catalog_user;

\connect orders
GRANT ALL ON SCHEMA public TO order_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO order_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO order_user;

