-- Initialize Core database

-- Create database if not exists
SELECT 'CREATE DATABASE core_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'core_db')\gexec

-- Create user if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_user
      WHERE  usename = 'core_user') THEN
      CREATE USER core_user WITH PASSWORD 'core_pass';
   END IF;
END
$do$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE core_db TO core_user;
ALTER DATABASE core_db OWNER TO core_user;

-- Connect to core_db
\c core_db;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO core_user;

-- Create read-only user for monitoring
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_user
      WHERE  usename = 'core_reader') THEN
      CREATE USER core_reader WITH PASSWORD 'reader_pass';
   END IF;
END
$do$;

-- Grant read-only access
GRANT CONNECT ON DATABASE core_db TO core_reader;
GRANT USAGE ON SCHEMA public TO core_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO core_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO core_reader;
