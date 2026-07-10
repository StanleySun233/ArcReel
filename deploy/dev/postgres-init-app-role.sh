#!/bin/sh
set -eu

: "${POSTGRES_DB:=arcreel}"
: "${ARCREEL_DEV_POSTGRES_APP_USER:=arcreel_app}"
: "${ARCREEL_DEV_POSTGRES_APP_PASSWORD:=arcreel_app_dev_password}"

sql_literal() {
  printf "%s" "$1" | sed "s/'/''/g"
}

app_user=$(sql_literal "$ARCREEL_DEV_POSTGRES_APP_USER")
app_password=$(sql_literal "$ARCREEL_DEV_POSTGRES_APP_PASSWORD")
database_name=$(sql_literal "$POSTGRES_DB")

psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$app_user') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$app_user', '$app_password');
  END IF;

  EXECUTE format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
    '$app_user',
    '$app_password'
  );
  EXECUTE format('GRANT CONNECT, CREATE ON DATABASE %I TO %I', '$database_name', '$app_user');
  EXECUTE format('GRANT USAGE, CREATE ON SCHEMA public TO %I', '$app_user');
  EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I', '$app_user');
  EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO %I', '$app_user');
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
    '$app_user'
  );
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
    '$app_user'
  );
END
\$\$;
SQL
