#!/bin/bash

# Rotate application secrets and selected service credentials safely
# - Creates a timestamped backup of .env
# - Rotates SECRET_KEY, JWT_SECRET_KEY
# - Rotates REDIS_PASSWORD and injects it into REDIS_URL (client-side)
# - Optionally rotates Postgres core_user password (interactive)
# - Optionally rotates QDRANT_API_KEY if present
#
# NOTE:
# - Redis container in docker-compose uses no requirepass by default; this only updates app client password.
# - Changing Postgres password for an existing DB requires ALTER ROLE inside the DB.
# - docker-compose must be available if you choose to apply DB password in the container.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

color() { local c="$1"; shift; printf "\033[%sm%s\033[0m\n" "$c" "$*"; }
info(){ color 34 "ℹ️  $*"; }
success(){ color 32 "✅ $*"; }
warn(){ color 33 "⚠️  $*"; }
error(){ color 31 "❌ $*"; }

require_cmd(){ command -v "$1" >/dev/null 2>&1 || { error "Missing command: $1"; exit 1; }; }

require_cmd openssl

if [ ! -f "$ENV_FILE" ]; then
  error "Missing .env at $ENV_FILE"
  exit 1
fi

cp "$ENV_FILE" "$ENV_FILE.backup-$TIMESTAMP"
success "Backed up .env to $ENV_FILE.backup-$TIMESTAMP"

# Load helpers to read current values
get_env(){ grep -E "^$1=" "$ENV_FILE" | sed -E 's/^'"$1"'="?(.*)"?$/\1/' | tail -n1; }
set_env(){ local k="$1"; local v="$2"; if grep -q "^$k=" "$ENV_FILE"; then sed -i "s#^$k=.*#$k=\"$v\"#g" "$ENV_FILE"; else echo "$k=\"$v\"" >> "$ENV_FILE"; fi }

# Generate new values
NEW_SECRET=$(openssl rand -base64 48 | tr -d '\n')
NEW_JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
NEW_REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')

set_env SECRET_KEY "$NEW_SECRET"
set_env JWT_SECRET_KEY "$NEW_JWT_SECRET"
set_env REDIS_PASSWORD "$NEW_REDIS_PASSWORD"

# Update REDIS_URL to include password
OLD_REDIS_URL=$(get_env REDIS_URL || true)
if [ -n "$OLD_REDIS_URL" ] && echo "$OLD_REDIS_URL" | grep -q '^redis://'; then
  URL_NO_SCHEME=${OLD_REDIS_URL#redis://}
  if echo "$URL_NO_SCHEME" | grep -q '@'; then
    HOSTPART=${URL_NO_SCHEME#*@}
    NEW_REDIS_URL="redis://:$NEW_REDIS_PASSWORD@$HOSTPART"
  else
    NEW_REDIS_URL="redis://:$NEW_REDIS_PASSWORD@$URL_NO_SCHEME"
  fi
  set_env REDIS_URL "$NEW_REDIS_URL"
  info "Updated REDIS_URL to include password."
else
  warn "REDIS_URL not set or not in expected format; skipped embedding password."
fi

# Optionally rotate QDRANT_API_KEY if exists
if grep -q '^QDRANT_API_KEY=' "$ENV_FILE"; then
  read -p "Rotate QDRANT_API_KEY as well? (y/N): " ans
  if [[ $ans =~ ^[Yy]$ ]]; then
    NEW_QDRANT=$(openssl rand -base64 48 | tr -d '\n')
    set_env QDRANT_API_KEY "$NEW_QDRANT"
    info "QDRANT_API_KEY rotated."
  fi
fi

# Optionally rotate Postgres password
echo ""
warn "Database password rotation requires updating the DB user inside Postgres."
read -p "Attempt to rotate Postgres core_user password now? (y/N): " rotate_db
if [[ $rotate_db =~ ^[Yy]$ ]]; then
  require_cmd docker-compose
  # Determine new password
  NEW_DB_PASS=$(openssl rand -base64 24 | tr -d '\n')
  # Update DATABASE_URL in .env if it contains core_user:
  OLD_DB_URL=$(get_env DATABASE_URL || true)
  if [ -n "$OLD_DB_URL" ] && echo "$OLD_DB_URL" | grep -q 'core_user:'; then
    NEW_DB_URL=$(echo "$OLD_DB_URL" | sed -E "s#(core_user:)[^@]*@#\1$NEW_DB_PASS@#")
    set_env DATABASE_URL "$NEW_DB_URL"
    info "Updated DATABASE_URL in .env"
  else
    warn "DATABASE_URL not in expected format; skipped updating URL."
  fi
  # Apply inside container (assumes service name postgres-core and DB core_db)
  if docker ps --format '{{.Names}}' | grep -q '^postgres-core$'; then
    DB_HOST=postgres-core
    DB_NAME=core_db
    DB_USER=core_user
    # Extract current password from old URL (best-effort)
    CURRENT_DB_PASS=$(echo "$OLD_DB_URL" | sed -n 's#.*core_user:\([^@]*\)@.*#\1#p')
    if [ -z "$CURRENT_DB_PASS" ]; then
      warn "Could not parse current DB password from DATABASE_URL. You may be prompted."
    fi
    info "Altering Postgres user password inside container..."
    docker exec -i postgres-core psql -U "$DB_USER" -d "$DB_NAME" -c "ALTER USER $DB_USER WITH PASSWORD '$NEW_DB_PASS';" || {
      error "Failed to alter Postgres password. Revert using backup if needed."
    }
    success "Postgres password rotated."
  else
    warn "postgres-core container not running; only .env updated. Apply DB change manually."
  fi
fi

cat <<EOF

================ ONE-TIME DISPLAY ================
Store these securely. They are also saved in .env (except DB change may require manual steps):
- SECRET_KEY: $NEW_SECRET
- JWT_SECRET_KEY: $NEW_JWT_SECRET
- REDIS_PASSWORD: $NEW_REDIS_PASSWORD
EOF

success "Rotation complete. Restart services to apply changes."
