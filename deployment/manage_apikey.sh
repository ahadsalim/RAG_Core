#!/bin/bash

# Manage INGEST_API_KEY for Core system
# - Show current key
# - Regenerate key (rotate) and save to .env
# - Creates a timestamped backup of .env

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

get_env(){ grep -E "^$1=" "$ENV_FILE" | sed -E 's/^'"$1"'="?(.*)"?$/\1/' | tail -n1; }
set_env(){ local k="$1"; local v="$2"; if grep -q "^$k=" "$ENV_FILE"; then sed -i "s#^$k=.*#$k=\"$v\"#g" "$ENV_FILE"; else echo "$k=\"$v\"" >> "$ENV_FILE"; fi }

echo ""
info "Core ↔ Ingest API Key Manager"
echo "1) نمایش API Key فعلی"
echo "2) تولید مجدد (Rotate) و جایگزینی"
echo "3) خروج"
read -p "انتخاب شما (1-3): " choice

case "$choice" in
  1)
    CURRENT=$(get_env INGEST_API_KEY || true)
    if [ -n "$CURRENT" ]; then
      success "INGEST_API_KEY فعلی: $CURRENT"
      echo "این مقدار را در سرویس ingest تنظیم کنید."
    else
      warn "INGEST_API_KEY در .env تنظیم نشده است. گزینه 2 را برای تولید انتخاب کنید."
    fi
    ;;
  2)
    read -p "آیا از تولید و جایگزینی کلید جدید مطمئن هستید؟ (y/N): " ans
    if [[ $ans =~ ^[Yy]$ ]]; then
      cp "$ENV_FILE" "$ENV_FILE.backup-$TIMESTAMP"
      info "Backup created: .env.backup-$TIMESTAMP"
      NEW_KEY=$(openssl rand -base64 48 | tr -d '\n')
      set_env INGEST_API_KEY "$NEW_KEY"
      success "کلید جدید تولید و ذخیره شد (INGEST_API_KEY)."
      echo ""
      echo "========== نمایش یک‌باره =========="
      echo "INGEST_API_KEY: $NEW_KEY"
      echo "آن را در سرویس ingest تنظیم کنید."
    else
      echo "لغو شد."
    fi
    ;;
  3)
    echo "خروج."
    ;;
  *)
    error "انتخاب نامعتبر"
    exit 1
    ;;
 esac
