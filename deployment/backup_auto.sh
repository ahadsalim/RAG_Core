#!/bin/bash

# ==============================================================================
# Core RAG System - Automatic Backup Script
# Version: 2.0.0
# Description: Automatic backup every 6 hours - PostgreSQL + Redis + NPM + Config
# Transfers to remote backup server via rsync
# ==============================================================================

set -e

# Detect directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yml"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${YELLOW}ℹ${NC} $1"; }

# Load environment variables
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found at $ENV_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# Configuration
BACKUP_DIR="/var/lib/core/backups/auto"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="core_backup_${DATE}"
SSH_KEY="${BACKUP_SSH_KEY:-/root/.ssh/backup_key}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
LOCAL_RETENTION_DAYS=3
LOG_FILE="/var/log/core_backup.log"

# Logging
log() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$LOG_FILE"
}

# ==============================================================================
# VALIDATION
# ==============================================================================

validate_config() {
    local errors=0
    
    if [ -z "$BACKUP_SERVER_HOST" ]; then
        print_error "BACKUP_SERVER_HOST not set in .env"
        errors=$((errors + 1))
    fi
    
    if [ -z "$BACKUP_SERVER_USER" ]; then
        print_error "BACKUP_SERVER_USER not set in .env"
        errors=$((errors + 1))
    fi
    
    if [ -z "$BACKUP_SERVER_PATH" ]; then
        print_error "BACKUP_SERVER_PATH not set in .env"
        errors=$((errors + 1))
    fi
    
    if [ ! -f "$SSH_KEY" ]; then
        print_error "SSH key not found: $SSH_KEY"
        errors=$((errors + 1))
    fi
    
    return $errors
}

# ==============================================================================
# BACKUP FUNCTIONS
# ==============================================================================

run_backup() {
    print_info "Starting automatic backup: $BACKUP_NAME"
    log "Starting backup: $BACKUP_NAME"
    
    # Validate configuration
    if ! validate_config; then
        print_error "Configuration validation failed"
        exit 1
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    cd "$SCRIPT_DIR"
    
    local backup_success=true
    
    # ============================================
    # 1. PostgreSQL Backup
    # ============================================
    print_info "Backing up PostgreSQL database..."
    
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
        pg_dump -U "${POSTGRES_USER:-core_user}" \
                -d "${POSTGRES_DB:-core_db}" \
                --format=custom \
                --blobs \
                --compress=9 \
        > "${BACKUP_DIR}/${BACKUP_NAME}_postgres.dump" 2>/dev/null; then
        print_success "PostgreSQL backup completed"
    else
        print_error "PostgreSQL backup failed"
        backup_success=false
    fi
    
    # ============================================
    # 2. Redis Backup
    # ============================================
    print_info "Backing up Redis data..."
    
    # Trigger Redis BGSAVE
    if [ -n "$REDIS_PASSWORD" ]; then
        docker-compose -f "$COMPOSE_FILE" exec -T redis-core \
            redis-cli -a "$REDIS_PASSWORD" BGSAVE > /dev/null 2>&1 || true
    else
        docker-compose -f "$COMPOSE_FILE" exec -T redis-core \
            redis-cli BGSAVE > /dev/null 2>&1 || true
    fi
    
    # Wait for BGSAVE to complete
    sleep 5
    
    # Copy dump.rdb
    if docker cp core-redis:/data/dump.rdb "${BACKUP_DIR}/${BACKUP_NAME}_redis.rdb" 2>/dev/null; then
        print_success "Redis backup completed"
    else
        print_info "Redis backup skipped (no data or container not found)"
    fi
    
    # ============================================
    # 3. Nginx Proxy Manager Data Backup
    # ============================================
    print_info "Backing up Nginx Proxy Manager data..."
    
    # Try to find NPM data volume or directory
    NPM_DATA_PATH="/srv/data/nginx-proxy-manager"
    
    if [ -d "$NPM_DATA_PATH" ] && [ "$(ls -A $NPM_DATA_PATH 2>/dev/null)" ]; then
        # Backup from local directory
        if tar czf "${BACKUP_DIR}/${BACKUP_NAME}_npm_data.tar.gz" -C "$NPM_DATA_PATH" . 2>/dev/null; then
            print_success "NPM data backup completed (from directory)"
        else
            print_info "NPM data backup failed"
        fi
    else
        # Try Docker volume
        if docker run --rm \
            -v npm_data:/data \
            -v "${BACKUP_DIR}:/backup" \
            alpine \
            tar czf "/backup/${BACKUP_NAME}_npm_data.tar.gz" -C /data . 2>/dev/null; then
            print_success "NPM data backup completed (from volume)"
        else
            print_info "NPM data backup skipped (volume/directory not found)"
        fi
    fi
    
    # ============================================
    # 4. Qdrant Vector Database Backup
    # ============================================
    print_info "Backing up Qdrant vector data..."
    
    if docker-compose -f "$COMPOSE_FILE" exec -T qdrant \
        tar czf - /qdrant/storage > "${BACKUP_DIR}/${BACKUP_NAME}_qdrant.tar.gz" 2>/dev/null; then
        # Check if file is not empty (more than 100 bytes)
        if [ -s "${BACKUP_DIR}/${BACKUP_NAME}_qdrant.tar.gz" ] && \
           [ $(stat -c%s "${BACKUP_DIR}/${BACKUP_NAME}_qdrant.tar.gz" 2>/dev/null || echo 0) -gt 100 ]; then
            print_success "Qdrant backup completed"
        else
            rm -f "${BACKUP_DIR}/${BACKUP_NAME}_qdrant.tar.gz"
            print_info "Qdrant backup skipped (empty)"
        fi
    else
        print_info "Qdrant backup skipped (container not running)"
    fi
    
    # ============================================
    # 5. Backup .env file
    # ============================================
    print_info "Backing up .env configuration..."
    
    if cp "$ENV_FILE" "${BACKUP_DIR}/${BACKUP_NAME}_env" 2>/dev/null; then
        print_success ".env backup completed"
    else
        print_error ".env backup failed"
    fi
    
    # ============================================
    # 6. Create compressed archive
    # ============================================
    print_info "Creating compressed archive..."
    
    cd "$BACKUP_DIR"
    
    # Collect all backup files
    BACKUP_FILES=""
    [ -f "${BACKUP_NAME}_postgres.dump" ] && BACKUP_FILES="$BACKUP_FILES ${BACKUP_NAME}_postgres.dump"
    [ -f "${BACKUP_NAME}_redis.rdb" ] && BACKUP_FILES="$BACKUP_FILES ${BACKUP_NAME}_redis.rdb"
    [ -f "${BACKUP_NAME}_npm_data.tar.gz" ] && BACKUP_FILES="$BACKUP_FILES ${BACKUP_NAME}_npm_data.tar.gz"
    [ -f "${BACKUP_NAME}_qdrant.tar.gz" ] && BACKUP_FILES="$BACKUP_FILES ${BACKUP_NAME}_qdrant.tar.gz"
    [ -f "${BACKUP_NAME}_env" ] && BACKUP_FILES="$BACKUP_FILES ${BACKUP_NAME}_env"
    
    if [ -n "$BACKUP_FILES" ]; then
        if tar -czf "${BACKUP_NAME}.tar.gz" $BACKUP_FILES 2>/dev/null; then
            # Remove individual files
            rm -f $BACKUP_FILES
            
            BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
            print_success "Archive created: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})"
            
            # Generate SHA256 checksum
            print_info "Generating SHA256 checksum..."
            sha256sum "${BACKUP_NAME}.tar.gz" > "${BACKUP_NAME}.tar.gz.sha256"
            print_success "Checksum created: ${BACKUP_NAME}.tar.gz.sha256"
        else
            print_error "Archive creation failed"
            backup_success=false
        fi
    else
        print_error "No backup files to archive"
        backup_success=false
    fi
    
    # ============================================
    # 7. Transfer to remote backup server
    # ============================================
    print_info "Transferring backup and checksum to remote server..."
    
    if rsync -avz --progress \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30" \
        "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" \
        "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz.sha256" \
        "${BACKUP_SERVER_USER}@${BACKUP_SERVER_HOST}:${BACKUP_SERVER_PATH}/" 2>&1; then
        
        print_success "Backup and checksum transferred to remote server"
        
        # Remove local backup after successful transfer (if configured)
        if [ "${BACKUP_KEEP_LOCAL:-false}" != "true" ]; then
            rm -f "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
            rm -f "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz.sha256"
            print_info "Local backup and checksum removed (transferred to remote)"
        fi
    else
        print_error "Backup transfer failed - keeping local copy"
        backup_success=false
    fi
    
    # ============================================
    # 8. Cleanup old backups on remote server
    # ============================================
    print_info "Cleaning old backups on remote server (keeping last ${RETENTION_DAYS} days)..."
    
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no \
        "${BACKUP_SERVER_USER}@${BACKUP_SERVER_HOST}" \
        "find ${BACKUP_SERVER_PATH} -name 'core_backup_*.tar.gz' -mtime +${RETENTION_DAYS} -delete && \
         find ${BACKUP_SERVER_PATH} -name 'core_backup_*.tar.gz.sha256' -mtime +${RETENTION_DAYS} -delete" 2>/dev/null; then
        print_success "Old remote backups and checksums cleaned"
    fi
    
    # ============================================
    # 9. Cleanup old local backups
    # ============================================
    print_info "Cleaning old local backups (keeping last ${LOCAL_RETENTION_DAYS} days)..."
    find "$BACKUP_DIR" -name "core_backup_*.tar.gz" -mtime +${LOCAL_RETENTION_DAYS} -delete 2>/dev/null
    find "$BACKUP_DIR" -name "core_backup_*.tar.gz.sha256" -mtime +${LOCAL_RETENTION_DAYS} -delete 2>/dev/null
    print_success "Local cleanup completed"
    
    # ============================================
    # 10. Log completion
    # ============================================
    if [ "$backup_success" = true ]; then
        log "Backup completed successfully: ${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})"
        print_success "Automatic backup completed successfully!"
        print_info "Backup: ${BACKUP_NAME}.tar.gz"
        print_info "Remote: ${BACKUP_SERVER_USER}@${BACKUP_SERVER_HOST}:${BACKUP_SERVER_PATH}/"
    else
        log "Backup completed with errors: ${BACKUP_NAME}"
        print_error "Backup completed with some errors"
    fi
}

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

show_usage() {
    echo ""
    echo -e "${BLUE}Core RAG System - Automatic Backup${NC}"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  run         Run backup once (default)"
    echo "  setup       Setup cron job for automatic backups every 6 hours"
    echo "  remove      Remove cron job"
    echo "  status      Show backup status and configuration"
    echo "  test        Test SSH connection to backup server"
    echo ""
    echo "Environment variables (in .env):"
    echo "  BACKUP_SERVER_HOST      Remote backup server hostname/IP"
    echo "  BACKUP_SERVER_USER      SSH username"
    echo "  BACKUP_SERVER_PATH      Remote directory path"
    echo "  BACKUP_SSH_KEY          Path to SSH private key"
    echo "  BACKUP_RETENTION_DAYS   Days to keep backups on remote (default: 30)"
    echo "  BACKUP_KEEP_LOCAL       Keep local copy after transfer (default: false)"
    echo ""
}

setup_cron() {
    print_info "Setting up automatic backup every 6 hours..."
    
    # Remove existing cron job if any
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    
    # Add new cron job (every 6 hours: 0:00, 6:00, 12:00, 18:00)
    local cron_cmd="0 */6 * * * $SCRIPT_DIR/backup_auto.sh run >> $LOG_FILE 2>&1"
    (crontab -l 2>/dev/null; echo "$cron_cmd") | crontab -
    
    print_success "Cron job installed: every 6 hours"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep backup_auto || echo "  (none found)"
    echo ""
}

remove_cron() {
    print_info "Removing automatic backup cron job..."
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    print_success "Cron job removed"
}

show_status() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Backup Configuration Status${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    echo "Remote Server Configuration:"
    if [ -n "$BACKUP_SERVER_HOST" ]; then
        print_success "  Host: $BACKUP_SERVER_HOST"
    else
        print_error "  Host: Not configured"
    fi
    if [ -n "$BACKUP_SERVER_USER" ]; then
        print_success "  User: $BACKUP_SERVER_USER"
    else
        print_error "  User: Not configured"
    fi
    echo "  Path: ${BACKUP_SERVER_PATH:-/backups/core}"
    if [ -f "$SSH_KEY" ]; then
        print_success "  SSH Key: $SSH_KEY"
    else
        print_error "  SSH Key: $SSH_KEY (NOT FOUND)"
    fi
    echo "  Retention: ${RETENTION_DAYS} days"
    echo "  Keep Local: ${BACKUP_KEEP_LOCAL:-false}"
    
    echo ""
    echo "Cron Status:"
    if crontab -l 2>/dev/null | grep -q "backup_auto.sh"; then
        print_success "  Automatic backup is ENABLED"
        crontab -l | grep backup_auto | sed 's/^/    /'
    else
        print_info "  Automatic backup is DISABLED"
    fi
    
    echo ""
    echo "Local Backups ($BACKUP_DIR):"
    if [ -d "$BACKUP_DIR" ]; then
        local count=$(find "$BACKUP_DIR" -name "core_backup_*.tar.gz" -type f 2>/dev/null | wc -l)
        echo "  Total: $count backup(s)"
        if [ "$count" -gt 0 ]; then
            echo "  Latest:"
            ls -lht "$BACKUP_DIR"/core_backup_*.tar.gz 2>/dev/null | head -3 | while read line; do
                echo "    $line"
            done
        fi
    else
        print_info "  Directory not found (will be created on first backup)"
    fi
    
    echo ""
    echo "Recent Log Entries:"
    if [ -f "$LOG_FILE" ]; then
        tail -5 "$LOG_FILE" | sed 's/^/  /'
    else
        print_info "  No log file yet"
    fi
    echo ""
}

test_ssh() {
    print_info "Testing SSH connection to backup server..."
    
    if ! validate_config; then
        return 1
    fi
    
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "${BACKUP_SERVER_USER}@${BACKUP_SERVER_HOST}" \
        "echo 'Connection successful' && mkdir -p ${BACKUP_SERVER_PATH}" 2>/dev/null; then
        print_success "SSH connection test passed!"
        print_success "Remote directory verified: ${BACKUP_SERVER_PATH}"
        return 0
    else
        print_error "SSH connection failed"
        return 1
    fi
}

# ==============================================================================
# MAIN
# ==============================================================================

case "${1:-run}" in
    run)
        run_backup
        ;;
    setup)
        setup_cron
        ;;
    remove)
        remove_cron
        ;;
    status)
        show_status
        ;;
    test)
        test_ssh
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
