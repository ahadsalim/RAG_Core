#!/bin/bash

# Validate .env file for Docker deployment
# This script checks if .env file has correct configuration for Docker

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Validating .env for Docker Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env file not found at: $ENV_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓ .env file found${NC}"
echo ""

# Check for required variables
REQUIRED_VARS=(
    "SECRET_KEY"
    "JWT_SECRET_KEY"
    "DATABASE_URL"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "REDIS_URL"
    "REDIS_PASSWORD"
    "QDRANT_HOST"
    "CELERY_BROKER_URL"
    "CELERY_RESULT_BACKEND"
)

echo -e "${YELLOW}Checking required variables...${NC}"
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" "$ENV_FILE"; then
        MISSING_VARS+=("$var")
        echo -e "${RED}  ❌ Missing: $var${NC}"
    else
        echo -e "${GREEN}  ✓ Found: $var${NC}"
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Missing ${#MISSING_VARS[@]} required variable(s)${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Checking Docker service names...${NC}"

# Check if using Docker service names (not localhost)
ISSUES=()

# Check DATABASE_URL
DB_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if echo "$DB_URL" | grep -q "localhost:7433"; then
    echo -e "${RED}  ❌ DATABASE_URL uses localhost:7433 (should be postgres-core:5432)${NC}"
    ISSUES+=("DATABASE_URL")
elif echo "$DB_URL" | grep -q "postgres-core:5432"; then
    echo -e "${GREEN}  ✓ DATABASE_URL uses correct Docker service name${NC}"
else
    echo -e "${YELLOW}  ⚠️  DATABASE_URL: $DB_URL${NC}"
fi

# Check REDIS_URL
REDIS_URL=$(grep "^REDIS_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if echo "$REDIS_URL" | grep -q "localhost:7379"; then
    echo -e "${RED}  ❌ REDIS_URL uses localhost:7379 (should be redis-core:6379)${NC}"
    ISSUES+=("REDIS_URL")
elif echo "$REDIS_URL" | grep -q "redis-core:6379"; then
    echo -e "${GREEN}  ✓ REDIS_URL uses correct Docker service name${NC}"
else
    echo -e "${YELLOW}  ⚠️  REDIS_URL: $REDIS_URL${NC}"
fi

# Check QDRANT_HOST
QDRANT_HOST=$(grep "^QDRANT_HOST=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if [ "$QDRANT_HOST" = "localhost" ]; then
    echo -e "${RED}  ❌ QDRANT_HOST uses localhost (should be qdrant)${NC}"
    ISSUES+=("QDRANT_HOST")
elif [ "$QDRANT_HOST" = "qdrant" ]; then
    echo -e "${GREEN}  ✓ QDRANT_HOST uses correct Docker service name${NC}"
else
    echo -e "${YELLOW}  ⚠️  QDRANT_HOST: $QDRANT_HOST${NC}"
fi

# Check QDRANT_PORT
QDRANT_PORT=$(grep "^QDRANT_PORT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if [ "$QDRANT_PORT" = "7333" ]; then
    echo -e "${RED}  ❌ QDRANT_PORT uses 7333 (should be 6333 for Docker)${NC}"
    ISSUES+=("QDRANT_PORT")
elif [ "$QDRANT_PORT" = "6333" ]; then
    echo -e "${GREEN}  ✓ QDRANT_PORT uses correct Docker port${NC}"
else
    echo -e "${YELLOW}  ⚠️  QDRANT_PORT: $QDRANT_PORT${NC}"
fi

# Check CELERY URLs
CELERY_BROKER=$(grep "^CELERY_BROKER_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if echo "$CELERY_BROKER" | grep -q "localhost:7379"; then
    echo -e "${RED}  ❌ CELERY_BROKER_URL uses localhost:7379 (should be redis-core:6379)${NC}"
    ISSUES+=("CELERY_BROKER_URL")
elif echo "$CELERY_BROKER" | grep -q "redis-core:6379"; then
    echo -e "${GREEN}  ✓ CELERY_BROKER_URL uses correct Docker service name${NC}"
else
    echo -e "${YELLOW}  ⚠️  CELERY_BROKER_URL: $CELERY_BROKER${NC}"
fi

echo ""
echo -e "${YELLOW}Checking for duplicate DOMAIN_NAME...${NC}"
DOMAIN_COUNT=$(grep -c "^DOMAIN_NAME=" "$ENV_FILE" || true)
if [ "$DOMAIN_COUNT" -gt 1 ]; then
    echo -e "${RED}  ❌ Found $DOMAIN_COUNT DOMAIN_NAME entries (should be 1)${NC}"
    ISSUES+=("DOMAIN_NAME_DUPLICATE")
elif [ "$DOMAIN_COUNT" -eq 1 ]; then
    DOMAIN_NAME=$(grep "^DOMAIN_NAME=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
    if [ -z "$DOMAIN_NAME" ]; then
        echo -e "${YELLOW}  ⚠️  DOMAIN_NAME is empty (OK for development)${NC}"
    else
        echo -e "${GREEN}  ✓ DOMAIN_NAME: $DOMAIN_NAME${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠️  No DOMAIN_NAME found (OK for development)${NC}"
fi

echo ""
echo -e "${YELLOW}Checking password security...${NC}"

# Check if passwords are still default values
SECRET_KEY=$(grep "^SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if [ "$SECRET_KEY" = "your-secret-key-change-in-production" ]; then
    echo -e "${RED}  ❌ SECRET_KEY is still default value!${NC}"
    ISSUES+=("SECRET_KEY_DEFAULT")
else
    echo -e "${GREEN}  ✓ SECRET_KEY is customized${NC}"
fi

POSTGRES_PASS=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
if [ "$POSTGRES_PASS" = "core_pass" ]; then
    echo -e "${RED}  ❌ POSTGRES_PASSWORD is still default value!${NC}"
    ISSUES+=("POSTGRES_PASSWORD_DEFAULT")
else
    echo -e "${GREEN}  ✓ POSTGRES_PASSWORD is customized${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
if [ ${#ISSUES[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo -e "${GREEN}Your .env file is ready for Docker deployment${NC}"
    exit 0
else
    echo -e "${RED}❌ Found ${#ISSUES[@]} issue(s):${NC}"
    for issue in "${ISSUES[@]}"; do
        echo -e "${RED}  - $issue${NC}"
    done
    echo ""
    echo -e "${YELLOW}To fix these issues, run:${NC}"
    echo -e "  nano $ENV_FILE"
    echo ""
    echo -e "${YELLOW}Or use the deployment scripts:${NC}"
    echo -e "  cd $SCRIPT_DIR"
    echo -e "  sudo ./start.sh"
    exit 1
fi
