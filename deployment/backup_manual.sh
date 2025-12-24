#!/bin/bash

# ==============================================================================
# Core RAG System - Manual Backup & Restore Script
# Version: 1.0.0
# Description: Manual backup/restore with full system or database-only modes
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
BACKUP_DIR="/var/lib/core/backups/manual"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[ℹ]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }

show_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       Core RAG System - Manual Backup & Restore          ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_usage() {
    show_banner
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo -e "${YELLOW}Backup Commands:${NC}"
    echo "  backup full              Create full system backup (DB + Qdrant + Config)"
    echo "  backup db                Create database-only backup"
    echo ""
    echo -e "${YELLOW}Restore Commands:${NC}"
    echo "  restore full <FILE>      Restore full system from backup file"
    echo "  restore db <FILE>        Restore database only from backup file"
    echo ""
    echo -e "${YELLOW}Other Commands:${NC}"
    echo "  list                     List available backups"
    echo "  verify <FILE>            Verify backup file integrity"
    echo "  menu                     Show interactive menu"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0 backup full"
    echo "  $0 backup db"
    echo "  $0 restore full /var/lib/core/backups/manual/core_full_20251224.tar.gz"
    echo "  $0 restore db /var/lib/core/backups/manual/core_db_20251224.sql.gz"
    echo ""
    echo -e "${YELLOW}Backup Location:${NC} $BACKUP_DIR"
    echo ""
}

# ==============================================================================
# BACKUP FUNCTIONS
# ==============================================================================

# Full system backup
backup_full() {
    show_banner
    print_info "Creating FULL system backup..."
    echo ""
    
    mkdir -p "$BACKUP_DIR"
    
    local backup_name="core_full_${TIMESTAMP}"
    local temp_dir="/tmp/${backup_name}"
    local backup_path="$BACKUP_DIR/${backup_name}.tar.gz"
    
    mkdir -p "$temp_dir"
    
    # Check if services are running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "postgres-core"; then
        print_error "PostgreSQL container is not running"
        print_info "Start services first: $SCRIPT_DIR/start.sh"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    # 1. Backup database
    print_info "[1/5] Backing up PostgreSQL database..."
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
        pg_dump -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" > "$temp_dir/database.sql" 2>/dev/null; then
        print_success "Database backed up ($(du -h "$temp_dir/database.sql" | cut -f1))"
    else
        print_error "Database backup failed"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    # 2. Backup .env file
    print_info "[2/5] Backing up configuration..."
    if [ -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env" "$temp_dir/.env"
        print_success "Configuration backed up"
    else
        print_warning ".env file not found, skipping"
    fi
    
    # 3. Backup Qdrant data
    print_info "[3/5] Backing up Qdrant vector data..."
    if docker-compose -f "$COMPOSE_FILE" exec -T qdrant \
        tar czf - /qdrant/storage > "$temp_dir/qdrant_data.tar.gz" 2>/dev/null; then
        local qdrant_size=$(du -h "$temp_dir/qdrant_data.tar.gz" | cut -f1)
        print_success "Qdrant data backed up ($qdrant_size)"
    else
        print_warning "Qdrant backup skipped (may be empty or unavailable)"
    fi
    
    # 4. Backup alembic version info
    print_info "[4/5] Backing up migration info..."
    if [ -d "$PROJECT_ROOT/alembic/versions" ]; then
        docker-compose -f "$COMPOSE_FILE" exec -T core-api alembic current > "$temp_dir/alembic_version.txt" 2>/dev/null || true
        print_success "Migration info backed up"
    fi
    
    # 5. Create metadata
    print_info "[5/5] Creating backup metadata..."
    cat > "$temp_dir/backup_info.json" <<EOF
{
    "type": "full",
    "backup_date": "$(date -Iseconds)",
    "timestamp": "$TIMESTAMP",
    "project_root": "$PROJECT_ROOT",
    "database": "${POSTGRES_DB:-core_db}",
    "db_user": "${POSTGRES_USER:-core_user}",
    "hostname": "$(hostname)",
    "version": "1.0.0",
    "components": ["database", "config", "qdrant", "alembic_info"]
}
EOF
    print_success "Metadata created"
    
    # Create compressed archive
    print_info "Creating compressed archive..."
    tar czf "$backup_path" -C "$temp_dir" .
    
    # Cleanup
    rm -rf "$temp_dir"
    chmod 600 "$backup_path"
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    print_success "Full backup completed successfully!"
    echo ""
    echo -e "  ${YELLOW}File:${NC} $backup_path"
    echo -e "  ${YELLOW}Size:${NC} $(du -h "$backup_path" | cut -f1)"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Database-only backup
backup_db() {
    show_banner
    print_info "Creating DATABASE backup..."
    echo ""
    
    mkdir -p "$BACKUP_DIR"
    
    local backup_name="core_db_${TIMESTAMP}.sql.gz"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    # Check if PostgreSQL is running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "postgres-core"; then
        print_error "PostgreSQL container is not running"
        print_info "Start services first: $SCRIPT_DIR/start.sh"
        exit 1
    fi
    
    print_info "Dumping and compressing database..."
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
        pg_dump -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" 2>/dev/null | gzip > "$backup_path"; then
        chmod 600 "$backup_path"
        echo ""
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        print_success "Database backup completed successfully!"
        echo ""
        echo -e "  ${YELLOW}File:${NC} $backup_path"
        echo -e "  ${YELLOW}Size:${NC} $(du -h "$backup_path" | cut -f1)"
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        echo ""
    else
        print_error "Database backup failed"
        rm -f "$backup_path"
        exit 1
    fi
}

# ==============================================================================
# RESTORE FUNCTIONS
# ==============================================================================

# Full system restore
restore_full() {
    local backup_file="$1"
    
    show_banner
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify backup file"
        echo ""
        list_backups
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    # Verify it's a full backup
    local temp_check="/tmp/backup_check_$$"
    mkdir -p "$temp_check"
    tar xzf "$backup_file" -C "$temp_check" backup_info.json 2>/dev/null || true
    
    if [ -f "$temp_check/backup_info.json" ]; then
        local backup_type=$(grep -o '"type": *"[^"]*"' "$temp_check/backup_info.json" | cut -d'"' -f4)
        if [ "$backup_type" != "full" ]; then
            print_error "This is not a full backup file (type: $backup_type)"
            print_info "Use 'restore db' for database-only backups"
            rm -rf "$temp_check"
            exit 1
        fi
    fi
    rm -rf "$temp_check"
    
    echo ""
    print_warning "╔══════════════════════════════════════════════════════════╗"
    print_warning "║  WARNING: This will restore from backup and overwrite    ║"
    print_warning "║  current data including database, config, and Qdrant!    ║"
    print_warning "╚══════════════════════════════════════════════════════════╝"
    echo ""
    read -p "Type 'yes' to confirm restore: " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Restore cancelled"
        exit 0
    fi
    
    print_info "Starting FULL restore..."
    echo ""
    
    local temp_dir="/tmp/core_restore_$$"
    mkdir -p "$temp_dir"
    
    # Extract backup
    print_info "[1/5] Extracting backup..."
    tar xzf "$backup_file" -C "$temp_dir"
    print_success "Backup extracted"
    
    # Stop services
    print_info "[2/5] Stopping services..."
    docker-compose -f "$COMPOSE_FILE" stop
    print_success "Services stopped"
    
    # Restore database
    if [ -f "$temp_dir/database.sql" ]; then
        print_info "[3/5] Restoring database..."
        docker-compose -f "$COMPOSE_FILE" up -d postgres-core
        sleep 5
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-core_db};" 2>/dev/null || true
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-core_db};"
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" < "$temp_dir/database.sql"
        
        print_success "Database restored"
    else
        print_warning "No database dump found in backup"
    fi
    
    # Restore .env
    if [ -f "$temp_dir/.env" ]; then
        print_info "[4/5] Restoring configuration..."
        cp "$PROJECT_ROOT/.env" "$PROJECT_ROOT/.env.backup-before-restore-$TIMESTAMP" 2>/dev/null || true
        cp "$temp_dir/.env" "$PROJECT_ROOT/.env"
        print_success "Configuration restored (old config backed up)"
    else
        print_warning "No configuration found in backup"
    fi
    
    # Restore Qdrant data
    if [ -f "$temp_dir/qdrant_data.tar.gz" ]; then
        print_info "[5/5] Restoring Qdrant data..."
        docker-compose -f "$COMPOSE_FILE" up -d qdrant
        sleep 5
        docker-compose -f "$COMPOSE_FILE" exec -T qdrant \
            tar xzf - -C / < "$temp_dir/qdrant_data.tar.gz" 2>/dev/null || \
            print_warning "Qdrant restore skipped"
        print_success "Qdrant data restored"
    else
        print_warning "No Qdrant data found in backup"
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    # Restart all services
    print_info "Restarting all services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    print_success "Full restore completed successfully!"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Database-only restore
restore_db() {
    local backup_file="$1"
    
    show_banner
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify backup file"
        echo ""
        list_backups
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    echo ""
    print_warning "╔══════════════════════════════════════════════════════════╗"
    print_warning "║  WARNING: This will restore database and overwrite       ║"
    print_warning "║  all current database data!                              ║"
    print_warning "╚══════════════════════════════════════════════════════════╝"
    echo ""
    read -p "Type 'yes' to confirm restore: " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Restore cancelled"
        exit 0
    fi
    
    print_info "Starting DATABASE restore..."
    echo ""
    
    # Check if PostgreSQL is running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "postgres-core"; then
        print_info "Starting PostgreSQL..."
        docker-compose -f "$COMPOSE_FILE" up -d postgres-core
        sleep 5
    fi
    
    # Determine file type and restore
    if [[ "$backup_file" == *.sql.gz ]]; then
        # Compressed SQL file
        print_info "Restoring from compressed SQL dump..."
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-core_db};" 2>/dev/null || true
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-core_db};"
        
        gunzip -c "$backup_file" | docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}"
            
    elif [[ "$backup_file" == *.sql ]]; then
        # Plain SQL file
        print_info "Restoring from SQL dump..."
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-core_db};" 2>/dev/null || true
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-core_db};"
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" < "$backup_file"
            
    elif [[ "$backup_file" == *.tar.gz ]]; then
        # Full backup archive - extract database only
        print_info "Extracting database from full backup..."
        
        local temp_dir="/tmp/db_restore_$$"
        mkdir -p "$temp_dir"
        tar xzf "$backup_file" -C "$temp_dir" database.sql 2>/dev/null || {
            print_error "No database.sql found in archive"
            rm -rf "$temp_dir"
            exit 1
        }
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-core_db};" 2>/dev/null || true
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB:-core_db};"
        
        docker-compose -f "$COMPOSE_FILE" exec -T postgres-core \
            psql -U "${POSTGRES_USER:-core_user}" -d "${POSTGRES_DB:-core_db}" < "$temp_dir/database.sql"
        
        rm -rf "$temp_dir"
    else
        print_error "Unknown backup file format"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    print_success "Database restore completed successfully!"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

# List available backups
list_backups() {
    echo ""
    echo -e "${BLUE}Available Backups${NC}"
    echo "================="
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        print_warning "No backups found in $BACKUP_DIR"
        return
    fi
    
    echo -e "${YELLOW}Full Backups:${NC}"
    local found_full=0
    for backup in "$BACKUP_DIR"/core_full_*.tar.gz; do
        if [ -f "$backup" ]; then
            found_full=1
            local size=$(du -h "$backup" | cut -f1)
            local date=$(stat -c %y "$backup" | cut -d'.' -f1)
            echo "  $(basename "$backup")"
            echo "    Size: $size | Date: $date"
            echo "    Path: $backup"
            echo ""
        fi
    done
    [ $found_full -eq 0 ] && echo "  (none)"
    
    echo ""
    echo -e "${YELLOW}Database Backups:${NC}"
    local found_db=0
    for backup in "$BACKUP_DIR"/core_db_*.sql.gz; do
        if [ -f "$backup" ]; then
            found_db=1
            local size=$(du -h "$backup" | cut -f1)
            local date=$(stat -c %y "$backup" | cut -d'.' -f1)
            echo "  $(basename "$backup")"
            echo "    Size: $size | Date: $date"
            echo "    Path: $backup"
            echo ""
        fi
    done
    [ $found_db -eq 0 ] && echo "  (none)"
    
    # Also check auto backup directory
    local auto_dir="/var/lib/core/backups/auto"
    if [ -d "$auto_dir" ] && [ -n "$(ls -A $auto_dir 2>/dev/null)" ]; then
        echo ""
        echo -e "${YELLOW}Automatic Backups (${auto_dir}):${NC}"
        for backup in "$auto_dir"/core_db_*.sql.gz; do
            if [ -f "$backup" ]; then
                local size=$(du -h "$backup" | cut -f1)
                local date=$(stat -c %y "$backup" | cut -d'.' -f1)
                echo "  $(basename "$backup") ($size)"
            fi
        done | head -5
        local total=$(find "$auto_dir" -name "core_db_*.sql.gz" 2>/dev/null | wc -l)
        [ $total -gt 5 ] && echo "  ... and $((total-5)) more"
    fi
    echo ""
}

# Verify backup
verify_backup() {
    local backup_file="$1"
    
    show_banner
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify backup file to verify"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    print_info "Verifying backup: $(basename $backup_file)"
    echo ""
    
    if [[ "$backup_file" == *.sql.gz ]]; then
        # Compressed SQL file
        if gunzip -t "$backup_file" 2>/dev/null; then
            print_success "Archive is valid (gzip)"
            local size=$(du -h "$backup_file" | cut -f1)
            local uncompressed=$(gunzip -c "$backup_file" | wc -c | numfmt --to=iec)
            echo ""
            echo "  Compressed size: $size"
            echo "  Uncompressed size: ~$uncompressed"
        else
            print_error "Archive is corrupted"
            exit 1
        fi
        
    elif [[ "$backup_file" == *.tar.gz ]]; then
        # Full backup archive
        local temp_dir="/tmp/verify_$$"
        mkdir -p "$temp_dir"
        
        if tar tzf "$backup_file" > "$temp_dir/contents.txt" 2>/dev/null; then
            print_success "Archive is valid (tar.gz)"
            echo ""
            echo "Contents:"
            cat "$temp_dir/contents.txt" | while read line; do
                echo "  - $line"
            done
            
            echo ""
            if grep -q "database.sql" "$temp_dir/contents.txt"; then
                print_success "Database backup present"
            else
                print_warning "Database backup missing"
            fi
            
            if grep -q ".env" "$temp_dir/contents.txt"; then
                print_success "Configuration present"
            else
                print_warning "Configuration missing"
            fi
            
            if grep -q "qdrant_data" "$temp_dir/contents.txt"; then
                print_success "Qdrant data present"
            else
                print_warning "Qdrant data missing"
            fi
            
            if grep -q "backup_info" "$temp_dir/contents.txt"; then
                print_success "Backup metadata present"
                tar xzf "$backup_file" -C "$temp_dir" backup_info.json 2>/dev/null || true
                if [ -f "$temp_dir/backup_info.json" ]; then
                    echo ""
                    echo "Backup Info:"
                    cat "$temp_dir/backup_info.json" | sed 's/^/  /'
                fi
            fi
        else
            print_error "Archive is corrupted or invalid"
            rm -rf "$temp_dir"
            exit 1
        fi
        
        rm -rf "$temp_dir"
    else
        print_error "Unknown file format"
        exit 1
    fi
    echo ""
}

# Interactive menu
show_menu() {
    while true; do
        show_banner
        echo "Select an action:"
        echo ""
        echo -e "  ${GREEN}Backup:${NC}"
        echo "    1) Full system backup (DB + Qdrant + Config)"
        echo "    2) Database only backup"
        echo ""
        echo -e "  ${YELLOW}Restore:${NC}"
        echo "    3) Restore from full backup"
        echo "    4) Restore database only"
        echo ""
        echo -e "  ${BLUE}Utilities:${NC}"
        echo "    5) List available backups"
        echo "    6) Verify backup file"
        echo ""
        echo "    0) Exit"
        echo ""
        read -p "Your choice (0-6): " choice
        
        case "$choice" in
            1) backup_full ;;
            2) backup_db ;;
            3)
                list_backups
                echo ""
                read -p "Enter full backup file path: " file_path
                if [ -n "$file_path" ]; then
                    restore_full "$file_path"
                fi
                ;;
            4)
                list_backups
                echo ""
                read -p "Enter backup file path: " file_path
                if [ -n "$file_path" ]; then
                    restore_db "$file_path"
                fi
                ;;
            5) list_backups ;;
            6)
                list_backups
                echo ""
                read -p "Enter backup file path to verify: " file_path
                if [ -n "$file_path" ]; then
                    verify_backup "$file_path"
                fi
                ;;
            0) 
                echo ""
                print_info "Goodbye!"
                exit 0 
                ;;
            *) 
                print_error "Invalid choice"
                sleep 1
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# ==============================================================================
# MAIN
# ==============================================================================

case "${1:-menu}" in
    backup)
        case "${2:-}" in
            full) backup_full ;;
            db) backup_db ;;
            *) 
                print_error "Unknown backup type: ${2:-}"
                echo "Use: $0 backup full|db"
                exit 1
                ;;
        esac
        ;;
    restore)
        case "${2:-}" in
            full) restore_full "$3" ;;
            db) restore_db "$3" ;;
            *)
                print_error "Unknown restore type: ${2:-}"
                echo "Use: $0 restore full|db <FILE>"
                exit 1
                ;;
        esac
        ;;
    list)
        list_backups
        ;;
    verify)
        verify_backup "$2"
        ;;
    menu)
        show_menu
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
