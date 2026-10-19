-- Runs once, on first start of an empty data volume, against POSTGRES_DB.
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy/full-text product search
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- hashing helpers

-- Separate databases for optional services (same PostgreSQL server).
-- \gexec makes CREATE DATABASE idempotent.
SELECT 'CREATE DATABASE litellm'  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
SELECT 'CREATE DATABASE keycloak' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

-- Application schemas, roles (including an INSERT-only audit role) and
-- row-level-security policies are created by Alembic migrations, not here.
