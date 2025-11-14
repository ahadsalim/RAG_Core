#!/bin/bash

# Core System - Backup Script
# اسکریپت پشتیبان‌گیری از سیستم Core

set -e

# Configuration
BACKUP_DIR="/var/lib/core/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="core_backup_${TIMESTAMP}"
RETENTION_DAYS=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Core System - Backup"
echo "Timestamp: ${TIMESTAMP}"
echo "========================================="

# Check if running from correct directory
if [ ! -f "deployment/backup.sh" ]; then
    echo -e "${RED}Error: Please run this script from the core project root directory${NC}"
    exit 1
fi

# Create backup directory if not exists
mkdir -p "${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# Function to check if service is running
check_service() {
    docker-compose -f deployment/docker/docker-compose.yml ps | grep -q "$1.*Up"
}

echo -e "${YELLOW}Starting backup process...${NC}"

# 1. Backup PostgreSQL Database
echo -e "${YELLOW}Backing up PostgreSQL database...${NC}"
if check_service "postgres-core"; then
    docker-compose -f deployment/docker/docker-compose.yml exec -T postgres-core \
        pg_dump -U core_user -d core_db > "${BACKUP_DIR}/${BACKUP_NAME}/postgres_dump.sql"
    
    # Compress the dump
    gzip "${BACKUP_DIR}/${BACKUP_NAME}/postgres_dump.sql"
    echo -e "${GREEN}✓ PostgreSQL backup completed${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running. Skipping database backup.${NC}"
fi

# 2. Backup Redis Data
echo -e "${YELLOW}Backing up Redis data...${NC}"
if check_service "redis-core"; then
    docker-compose -f deployment/docker/docker-compose.yml exec -T redis-core \
        redis-cli --rdb /data/dump.rdb BGSAVE
    
    # Wait for background save to complete
    sleep 5
    
    # Copy Redis dump file
    docker cp redis-core:/data/dump.rdb "${BACKUP_DIR}/${BACKUP_NAME}/redis_dump.rdb"
    echo -e "${GREEN}✓ Redis backup completed${NC}"
else
    echo -e "${RED}✗ Redis is not running. Skipping Redis backup.${NC}"
fi

# 3. Backup Qdrant Data
echo -e "${YELLOW}Backing up Qdrant vector database...${NC}"
if check_service "qdrant"; then
    # Create Qdrant snapshot via API
    COLLECTION_NAME=$(grep QDRANT_COLLECTION .env | cut -d '=' -f2 | tr -d '"')
    
    # Trigger snapshot creation
    curl -X POST "http://localhost:7333/collections/${COLLECTION_NAME}/snapshots" \
        -H "Content-Type: application/json" \
        -d '{}' > /dev/null 2>&1
    
    # Wait for snapshot to be created
    sleep 10
    
    # Get snapshot list
    SNAPSHOT_NAME=$(curl -s "http://localhost:7333/collections/${COLLECTION_NAME}/snapshots" | \
        python3 -c "import sys, json; snapshots = json.load(sys.stdin)['result']; print(snapshots[-1]['name'] if snapshots else '')")
    
    if [ ! -z "$SNAPSHOT_NAME" ]; then
        # Download snapshot
        curl -o "${BACKUP_DIR}/${BACKUP_NAME}/qdrant_snapshot.tar" \
            "http://localhost:7333/collections/${COLLECTION_NAME}/snapshots/${SNAPSHOT_NAME}"
        echo -e "${GREEN}✓ Qdrant backup completed${NC}"
    else
        echo -e "${YELLOW}⚠ Could not create Qdrant snapshot${NC}"
    fi
else
    echo -e "${RED}✗ Qdrant is not running. Skipping Qdrant backup.${NC}"
fi

# 4. Backup configuration files
echo -e "${YELLOW}Backing up configuration files...${NC}"
cp .env "${BACKUP_DIR}/${BACKUP_NAME}/env_backup" 2>/dev/null || true
cp .env.production "${BACKUP_DIR}/${BACKUP_NAME}/env_production_backup" 2>/dev/null || true

# Backup Nginx config if exists
if [ -f "/etc/nginx/sites-available/core-api" ]; then
    cp /etc/nginx/sites-available/core-api "${BACKUP_DIR}/${BACKUP_NAME}/nginx_config"
fi

echo -e "${GREEN}✓ Configuration backup completed${NC}"

# 5. Backup uploaded files and logs (if any)
echo -e "${YELLOW}Backing up logs...${NC}"
if [ -d "logs" ]; then
    tar -czf "${BACKUP_DIR}/${BACKUP_NAME}/logs.tar.gz" logs/
    echo -e "${GREEN}✓ Logs backup completed${NC}"
fi

# 6. Create metadata file
echo -e "${YELLOW}Creating backup metadata...${NC}"
cat > "${BACKUP_DIR}/${BACKUP_NAME}/metadata.json" <<EOF
{
    "timestamp": "${TIMESTAMP}",
    "date": "$(date)",
    "hostname": "$(hostname)",
    "docker_version": "$(docker --version)",
    "services": {
        "postgres": $(check_service "postgres-core" && echo "true" || echo "false"),
        "redis": $(check_service "redis-core" && echo "true" || echo "false"),
        "qdrant": $(check_service "qdrant" && echo "true" || echo "false"),
        "core_api": $(check_service "core-api" && echo "true" || echo "false")
    }
}
EOF

# 7. Create final archive
echo -e "${YELLOW}Creating final backup archive...${NC}"
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}/"
rm -rf "${BACKUP_NAME}"
cd - > /dev/null

BACKUP_SIZE=$(du -sh "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)
echo -e "${GREEN}✓ Backup archive created: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})${NC}"

# 8. Upload to remote storage (optional)
if [ ! -z "$BACKUP_S3_BUCKET" ]; then
    echo -e "${YELLOW}Uploading to S3...${NC}"
    aws s3 cp "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" \
        "s3://${BACKUP_S3_BUCKET}/core-backups/${BACKUP_NAME}.tar.gz"
    echo -e "${GREEN}✓ Backup uploaded to S3${NC}"
fi

# 9. Clean old backups
echo -e "${YELLOW}Cleaning old backups (older than ${RETENTION_DAYS} days)...${NC}"
find "${BACKUP_DIR}" -name "core_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete
echo -e "${GREEN}✓ Old backups cleaned${NC}"

# 10. Send notification (optional)
if [ ! -z "$BACKUP_NOTIFICATION_WEBHOOK" ]; then
    curl -X POST "$BACKUP_NOTIFICATION_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"Core backup completed successfully: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})\"}" \
        > /dev/null 2>&1
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Backup completed successfully!${NC}"
echo -e "${GREEN}Location: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz${NC}"
echo -e "${GREEN}=========================================${NC}"
