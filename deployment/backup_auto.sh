#!/bin/bash

# ==============================================================================
# Core RAG System - Automatic Backup Script
# Version: 1.0.0
# Description: Automatic database backup every 6 hours, sends to remote server
# ==============================================================================

set -e

# Detect directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yml"

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Configuration
LOCAL_BACKUP_DIR="/var/lib/core/backups/auto"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="core_db_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=7
LOG_FILE="/var/log/core_backup.log"

# Colors (for interactive use)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "$1"; }
log_success() { log "SUCCESS" "$1"; }
log_error() { log "ERROR" "$1"; }
log_warning() { log "WARNING" "$1"; }

print_info() { echo -e "${BLUE}[ℹ]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }

# Validate SSH configuration
validate_ssh_config() {
    if [ -z "$BACKUP_SSH_HOST" ]; then
        log_error "BACKUP_SSH_HOST not configured in .env"
        return 1
    fi
    if [ -z "$BACKUP_SSH_USER" ]; then
        log_error "BACKUP_SSH_USER not configured in .env"
        return 1
    fi
    if [ -n "$BACKUP_SSH_KEY_PATH" ] && [ ! -f "$BACKUP_SSH_KEY_PATH" ]; then
        log_error "SSH key file not found: $BACKUP_SSH_KEY_PATH"
        return 1
    fi
    return 0
}

# Create database backup
create_db_backup() {
    log_info "Starting database backup..."
    
    # Create local backup directory
    mkdir -p "$LOCAL_BACKUP_DIR"
    
    local backup_path="$LOCAL_BACKUP_DIR/$BACKUP_NAME"
    
    # Check if PostgreSQL is running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "postgres-core"; then
        log_error "PostgreSQL container is not running"
        return 1
    fi
    
    # Dump and compress database
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
        pg_dump -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" 2>/dev/null | gzip > "$backup_path"; then
        
        local size=$(du -h "$backup_path" | cut -f1)
        log_success "Database backup created: $backup_path ($size)"
        echo "$backup_path"
        return 0
    else
        log_error "Database backup failed"
        rm -f "$backup_path"
        return 1
    fi
}

# Send backup to remote server
send_to_remote() {
    local backup_file="$1"
    
    if ! validate_ssh_config; then
        return 1
    fi
    
    log_info "Sending backup to remote server: $BACKUP_SSH_HOST"
    
    # Build SSH options
    local ssh_opts="-o StrictHostKeyChecking=no -o ConnectTimeout=30"
    if [ -n "$BACKUP_SSH_KEY_PATH" ]; then
        ssh_opts="$ssh_opts -i $BACKUP_SSH_KEY_PATH"
    fi
    if [ -n "$BACKUP_SSH_PORT" ] && [ "$BACKUP_SSH_PORT" != "22" ]; then
        ssh_opts="$ssh_opts -p $BACKUP_SSH_PORT"
    fi
    
    local remote_path="${BACKUP_REMOTE_PATH:-/backups/core}"
    local remote_dest="$BACKUP_SSH_USER@$BACKUP_SSH_HOST:$remote_path/"
    
    # Create remote directory
    ssh $ssh_opts "$BACKUP_SSH_USER@$BACKUP_SSH_HOST" "mkdir -p $remote_path" 2>/dev/null || true
    
    # Build SCP options
    local scp_opts="-o StrictHostKeyChecking=no -o ConnectTimeout=30"
    if [ -n "$BACKUP_SSH_KEY_PATH" ]; then
        scp_opts="$scp_opts -i $BACKUP_SSH_KEY_PATH"
    fi
    if [ -n "$BACKUP_SSH_PORT" ] && [ "$BACKUP_SSH_PORT" != "22" ]; then
        scp_opts="$scp_opts -P $BACKUP_SSH_PORT"
    fi
    
    # Send file
    if scp $scp_opts "$backup_file" "$remote_dest"; then
        log_success "Backup sent to remote server: $remote_dest$(basename $backup_file)"
        return 0
    else
        log_error "Failed to send backup to remote server"
        return 1
    fi
}

# Clean old local backups
clean_old_backups() {
    log_info "Cleaning local backups older than $RETENTION_DAYS days..."
    
    local deleted=$(find "$LOCAL_BACKUP_DIR" -name "core_db_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete -print | wc -l)
    
    if [ "$deleted" -gt 0 ]; then
        log_info "Deleted $deleted old backup(s)"
    fi
}

# Show usage
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
    echo "  BACKUP_SSH_HOST       Remote backup server hostname/IP"
    echo "  BACKUP_SSH_PORT       SSH port (default: 22)"
    echo "  BACKUP_SSH_USER       SSH username"
    echo "  BACKUP_SSH_KEY_PATH   Path to SSH private key"
    echo "  BACKUP_REMOTE_PATH    Remote directory path"
    echo ""
}

# Setup cron job
setup_cron() {
    print_info "Setting up automatic backup every 6 hours..."
    
    # Remove existing cron job if any
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    
    # Add new cron job (every 6 hours: 0:00, 6:00, 12:00, 18:00)
    local cron_cmd="0 */6 * * * $SCRIPT_DIR/backup_auto.sh run >> /var/log/core_backup.log 2>&1"
    (crontab -l 2>/dev/null; echo "$cron_cmd") | crontab -
    
    print_success "Cron job installed: every 6 hours"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep backup_auto || echo "  (none found)"
    echo ""
}

# Remove cron job
remove_cron() {
    print_info "Removing automatic backup cron job..."
    crontab -l 2>/dev/null | grep -v "backup_auto.sh" | crontab - 2>/dev/null || true
    print_success "Cron job removed"
}

# Show status
show_status() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Backup Configuration Status${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    echo "SSH Configuration:"
    if [ -n "$BACKUP_SSH_HOST" ]; then
        print_success "  Host: $BACKUP_SSH_HOST"
    else
        print_error "  Host: Not configured"
    fi
    echo "  Port: ${BACKUP_SSH_PORT:-22}"
    if [ -n "$BACKUP_SSH_USER" ]; then
        print_success "  User: $BACKUP_SSH_USER"
    else
        print_error "  User: Not configured"
    fi
    if [ -n "$BACKUP_SSH_KEY_PATH" ]; then
        if [ -f "$BACKUP_SSH_KEY_PATH" ]; then
            print_success "  Key: $BACKUP_SSH_KEY_PATH"
        else
            print_error "  Key: $BACKUP_SSH_KEY_PATH (FILE NOT FOUND)"
        fi
    else
        print_warning "  Key: Not configured (will use password)"
    fi
    echo "  Remote Path: ${BACKUP_REMOTE_PATH:-/backups/core}"
    
    echo ""
    echo "Cron Status:"
    if crontab -l 2>/dev/null | grep -q "backup_auto.sh"; then
        print_success "  Automatic backup is ENABLED"
        crontab -l | grep backup_auto | sed 's/^/    /'
    else
        print_warning "  Automatic backup is DISABLED"
    fi
    
    echo ""
    echo "Local Backups ($LOCAL_BACKUP_DIR):"
    if [ -d "$LOCAL_BACKUP_DIR" ]; then
        local count=$(find "$LOCAL_BACKUP_DIR" -name "core_db_*.sql.gz" -type f 2>/dev/null | wc -l)
        echo "  Total: $count backup(s)"
        if [ "$count" -gt 0 ]; then
            echo "  Latest:"
            ls -lht "$LOCAL_BACKUP_DIR"/core_db_*.sql.gz 2>/dev/null | head -3 | while read line; do
                echo "    $line"
            done
        fi
    else
        print_warning "  Directory not found"
    fi
    echo ""
}

# Test SSH connection
test_ssh() {
    print_info "Testing SSH connection..."
    
    if ! validate_ssh_config; then
        return 1
    fi
    
    local ssh_opts="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
    if [ -n "$BACKUP_SSH_KEY_PATH" ]; then
        ssh_opts="$ssh_opts -i $BACKUP_SSH_KEY_PATH"
    fi
    if [ -n "$BACKUP_SSH_PORT" ] && [ "$BACKUP_SSH_PORT" != "22" ]; then
        ssh_opts="$ssh_opts -p $BACKUP_SSH_PORT"
    fi
    
    if ssh $ssh_opts "$BACKUP_SSH_USER@$BACKUP_SSH_HOST" "echo 'Connection successful'" 2>/dev/null; then
        print_success "SSH connection test passed!"
        return 0
    else
        print_error "SSH connection failed"
        return 1
    fi
}

# Main backup process
run_backup() {
    log_info "========== Starting Automatic Backup =========="
    
    # Create database backup
    local backup_file
    backup_file=$(create_db_backup)
    
    if [ $? -ne 0 ] || [ -z "$backup_file" ]; then
        log_error "Backup process failed"
        exit 1
    fi
    
    # Send to remote server
    if validate_ssh_config 2>/dev/null; then
        send_to_remote "$backup_file"
    else
        log_warning "Remote backup not configured, keeping local only"
    fi
    
    # Clean old backups
    clean_old_backups
    
    log_success "========== Backup Complete =========="
}

# Main
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
