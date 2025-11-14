#!/bin/bash

# Core System - Restore Script
# اسکریپت بازیابی سیستم Core

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Core System - Restore"
echo "========================================="

# Check arguments
if [ "$#" -ne 1 ]; then
    echo -e "${RED}Usage: $0 <backup_file.tar.gz>${NC}"
    echo "Example: $0 /var/lib/core/backups/core_backup_20240101_120000.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Check if running from correct directory
if [ ! -f "deployment/restore.sh" ]; then
    echo -e "${RED}Error: Please run this script from the core project root directory${NC}"
    exit 1
fi

# Warning
echo -e "${RED}WARNING: This will restore the system from backup!${NC}"
echo -e "${RED}All current data will be overwritten!${NC}"
read -p "Are you sure you want to continue? (y/N): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 1
fi

# Create temporary directory
TEMP_DIR="/tmp/core_restore_$(date +%s)"
mkdir -p "$TEMP_DIR"

echo -e "${YELLOW}Extracting backup archive...${NC}"
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find extracted backup directory
BACKUP_DIR=$(ls -d ${TEMP_DIR}/core_backup_* | head -n 1)

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}Error: Invalid backup archive structure${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Read metadata
if [ -f "$BACKUP_DIR/metadata.json" ]; then
    echo -e "${GREEN}Backup metadata:${NC}"
    cat "$BACKUP_DIR/metadata.json"
    echo ""
fi

# Stop services
echo -e "${YELLOW}Stopping services...${NC}"
docker-compose -f deployment/docker/docker-compose.yml down

# 1. Restore PostgreSQL Database
if [ -f "$BACKUP_DIR/postgres_dump.sql.gz" ]; then
    echo -e "${YELLOW}Restoring PostgreSQL database...${NC}"
    
    # Start only PostgreSQL service
    docker-compose -f deployment/docker/docker-compose.yml up -d postgres-core
    
    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    sleep 10
    
    # Drop existing database and recreate
    docker-compose -f deployment/docker/docker-compose.yml exec -T postgres-core \
        psql -U core_user -c "DROP DATABASE IF EXISTS core_db;"
    
    docker-compose -f deployment/docker/docker-compose.yml exec -T postgres-core \
        psql -U core_user -c "CREATE DATABASE core_db;"
    
    # Restore database
    gunzip -c "$BACKUP_DIR/postgres_dump.sql.gz" | \
        docker-compose -f deployment/docker/docker-compose.yml exec -T postgres-core \
        psql -U core_user -d core_db
    
    echo -e "${GREEN}✓ PostgreSQL restored${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL backup not found in archive${NC}"
fi

# 2. Restore Redis Data
if [ -f "$BACKUP_DIR/redis_dump.rdb" ]; then
    echo -e "${YELLOW}Restoring Redis data...${NC}"
    
    # Start Redis service
    docker-compose -f deployment/docker/docker-compose.yml up -d redis-core
    sleep 5
    
    # Stop Redis to restore data
    docker-compose -f deployment/docker/docker-compose.yml stop redis-core
    
    # Copy backup file
    docker cp "$BACKUP_DIR/redis_dump.rdb" redis-core:/data/dump.rdb
    
    # Start Redis again
    docker-compose -f deployment/docker/docker-compose.yml start redis-core
    
    echo -e "${GREEN}✓ Redis restored${NC}"
else
    echo -e "${YELLOW}⚠ Redis backup not found in archive${NC}"
fi

# 3. Restore Qdrant Data
if [ -f "$BACKUP_DIR/qdrant_snapshot.tar" ]; then
    echo -e "${YELLOW}Restoring Qdrant vector database...${NC}"
    
    # Start Qdrant service
    docker-compose -f deployment/docker/docker-compose.yml up -d qdrant
    sleep 10
    
    # Get collection name from env
    COLLECTION_NAME=$(grep QDRANT_COLLECTION .env | cut -d '=' -f2 | tr -d '"')
    
    # Upload and restore snapshot
    # First, upload the snapshot file
    curl -X POST "http://localhost:7333/collections/${COLLECTION_NAME}/snapshots/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@${BACKUP_DIR}/qdrant_snapshot.tar"
    
    # Wait for restoration
    sleep 10
    
    echo -e "${GREEN}✓ Qdrant restored${NC}"
else
    echo -e "${YELLOW}⚠ Qdrant backup not found in archive${NC}"
fi

# 4. Restore configuration files (optional)
read -p "Do you want to restore configuration files (.env)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$BACKUP_DIR/env_backup" ]; then
        cp "$BACKUP_DIR/env_backup" .env.restored
        echo -e "${GREEN}✓ Configuration restored to .env.restored${NC}"
        echo -e "${YELLOW}Please review and rename to .env if needed${NC}"
    fi
    
    if [ -f "$BACKUP_DIR/env_production_backup" ]; then
        cp "$BACKUP_DIR/env_production_backup" .env.production.restored
        echo -e "${GREEN}✓ Production config restored to .env.production.restored${NC}"
    fi
    
    if [ -f "$BACKUP_DIR/nginx_config" ]; then
        sudo cp "$BACKUP_DIR/nginx_config" /etc/nginx/sites-available/core-api.restored
        echo -e "${GREEN}✓ Nginx config restored to /etc/nginx/sites-available/core-api.restored${NC}"
    fi
fi

# 5. Restore logs (optional)
if [ -f "$BACKUP_DIR/logs.tar.gz" ]; then
    read -p "Do you want to restore logs? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p logs_restored
        tar -xzf "$BACKUP_DIR/logs.tar.gz" -C logs_restored/
        echo -e "${GREEN}✓ Logs restored to logs_restored/${NC}"
    fi
fi

# Clean up temporary files
rm -rf "$TEMP_DIR"

# Start all services
echo -e "${YELLOW}Starting all services...${NC}"
docker-compose -f deployment/docker/docker-compose.yml up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 15

# Check services status
echo -e "${YELLOW}Checking services status...${NC}"
docker-compose -f deployment/docker/docker-compose.yml ps

# Run health check
echo -e "${YELLOW}Running health check...${NC}"
if curl -f http://localhost:7001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is responding${NC}"
else
    echo -e "${RED}✗ API is not responding. Check logs: docker-compose logs core-api${NC}"
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Restore completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "1. Review restored configuration files (.env.restored)"
echo "2. Check service logs: docker-compose -f deployment/docker/docker-compose.yml logs"
echo "3. Verify data integrity in the application"
echo "4. Run migrations if needed: alembic upgrade head"
