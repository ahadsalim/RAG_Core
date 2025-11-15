#!/bin/bash

# Core RAG System - Unified Backup & Restore Script
# اسکریپت یکپارچه Backup و Restore

set -e

# Configuration
BACKUP_DIR="/var/lib/core/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="core_backup_${TIMESTAMP}"
RETENTION_DAYS=30

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Detect directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  backup              Create full backup"
    echo "  restore [FILE]      Restore from backup file"
    echo "  list                List available backups"
    echo "  clean               Remove old backups (older than $RETENTION_DAYS days)"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 restore /var/lib/core/backups/core_backup_20251115_093000.tar.gz"
    echo "  $0 list"
}

create_backup() {
    print_info "Starting backup process..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_PATH="$BACKUP_DIR/${BACKUP_NAME}.tar.gz"
    TEMP_DIR="/tmp/core_backup_${TIMESTAMP}"
    
    mkdir -p "$TEMP_DIR"
    
    # Backup database
    print_info "Backing up PostgreSQL database..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T postgres-core \
        pg_dump -U core_user core_db > "$TEMP_DIR/database.sql"
    
    # Backup .env file
    print_info "Backing up configuration..."
    cp "$PROJECT_ROOT/.env" "$TEMP_DIR/.env"
    
    # Backup Qdrant data
    print_info "Backing up Qdrant data..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T qdrant \
        tar czf - /qdrant/storage > "$TEMP_DIR/qdrant_data.tar.gz" 2>/dev/null || \
        print_warning "Qdrant backup skipped"
    
    # Create backup metadata
    cat > "$TEMP_DIR/backup_info.txt" <<EOF
Backup Date: $(date)
Timestamp: $TIMESTAMP
Project Root: $PROJECT_ROOT
Database: core_db
User: core_user
EOF
    
    # Create compressed archive
    print_info "Creating compressed archive..."
    tar czf "$BACKUP_PATH" -C "$TEMP_DIR" .
    
    # Cleanup temp directory
    rm -rf "$TEMP_DIR"
    
    # Set permissions
    chmod 600 "$BACKUP_PATH"
    
    print_success "Backup completed: $BACKUP_PATH"
    print_info "Backup size: $(du -h "$BACKUP_PATH" | cut -f1)"
}

restore_backup() {
    BACKUP_FILE="$1"
    
    if [ -z "$BACKUP_FILE" ]; then
        print_error "Please specify backup file"
        echo "Available backups:"
        list_backups
        exit 1
    fi
    
    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    print_warning "⚠️  This will restore from backup and overwrite current data!"
    read -p "Are you sure? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        print_info "Restore cancelled"
        exit 0
    fi
    
    print_info "Starting restore process..."
    
    TEMP_DIR="/tmp/core_restore_$(date +%s)"
    mkdir -p "$TEMP_DIR"
    
    # Extract backup
    print_info "Extracting backup..."
    tar xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    # Stop services
    print_info "Stopping services..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" stop
    
    # Restore database
    if [ -f "$TEMP_DIR/database.sql" ]; then
        print_info "Restoring database..."
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" up -d postgres-core
        sleep 5
        
        # Drop and recreate database
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T postgres-core \
            psql -U core_user -d postgres -c "DROP DATABASE IF EXISTS core_db;"
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T postgres-core \
            psql -U core_user -d postgres -c "CREATE DATABASE core_db;"
        
        # Restore data
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T postgres-core \
            psql -U core_user -d core_db < "$TEMP_DIR/database.sql"
        
        print_success "Database restored"
    fi
    
    # Restore .env
    if [ -f "$TEMP_DIR/.env" ]; then
        print_info "Restoring configuration..."
        cp "$TEMP_DIR/.env" "$PROJECT_ROOT/.env"
        print_success "Configuration restored"
    fi
    
    # Restore Qdrant data
    if [ -f "$TEMP_DIR/qdrant_data.tar.gz" ]; then
        print_info "Restoring Qdrant data..."
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" up -d qdrant
        sleep 5
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T qdrant \
            tar xzf - -C / < "$TEMP_DIR/qdrant_data.tar.gz" 2>/dev/null || \
            print_warning "Qdrant restore skipped"
    fi
    
    # Cleanup temp directory
    rm -rf "$TEMP_DIR"
    
    # Restart all services
    print_info "Restarting all services..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" up -d
    
    print_success "Restore completed successfully!"
}

list_backups() {
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        print_warning "No backups found in $BACKUP_DIR"
        return
    fi
    
    echo ""
    echo "Available backups:"
    echo "=================="
    
    for backup in "$BACKUP_DIR"/*.tar.gz; do
        if [ -f "$backup" ]; then
            SIZE=$(du -h "$backup" | cut -f1)
            DATE=$(stat -c %y "$backup" | cut -d'.' -f1)
            echo "📦 $(basename "$backup")"
            echo "   Size: $SIZE"
            echo "   Date: $DATE"
            echo "   Path: $backup"
            echo ""
        fi
    done
}

clean_old_backups() {
    print_info "Cleaning old backups (older than $RETENTION_DAYS days)..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "Backup directory not found"
        return
    fi
    
    DELETED=0
    find "$BACKUP_DIR" -name "core_backup_*.tar.gz" -type f -mtime +$RETENTION_DAYS -print0 | while IFS= read -r -d '' backup; do
        print_info "Deleting: $(basename "$backup")"
        rm -f "$backup"
        DELETED=$((DELETED + 1))
    done
    
    if [ $DELETED -eq 0 ]; then
        print_info "No old backups to delete"
    else
        print_success "Deleted $DELETED old backup(s)"
    fi
}

# Main
case "${1:-}" in
    backup)
        create_backup
        ;;
    restore)
        restore_backup "$2"
        ;;
    list)
        list_backups
        ;;
    clean)
        clean_old_backups
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
