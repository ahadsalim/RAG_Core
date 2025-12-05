#!/bin/bash

# ==============================================================================
# Core RAG System - Configuration Management Script
# Version: 2.0.0
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yml"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Helper functions
print_info() { echo -e "${BLUE}[ℹ]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }

get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | sed -E 's/^'"$1"'="?(.*)"?$/\1/' | tail -n1; }
set_env() { 
    local k="$1"
    local v="$2"
    if grep -q "^$k=" "$ENV_FILE"; then
        sed -i "s#^$k=.*#$k=\"$v\"#g" "$ENV_FILE"
    else
        echo "$k=\"$v\"" >> "$ENV_FILE"
    fi
}

show_menu() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Core RAG System - Management${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "1) Validate .env configuration"
    echo "2) Manage API Keys"
    echo "3) Rotate Secrets"
    echo "4) Exit"
    echo ""
    read -p "Your choice (1-4): " choice
    
    case "$choice" in
        1) validate_env ;;
        2) manage_apikeys ;;
        3) rotate_secrets ;;
        4) exit 0 ;;
        *) print_error "Invalid choice" && show_menu ;;
    esac
}

# ============================================
# 1. Validate .env
# ============================================
validate_env() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Validating .env Configuration${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found at: $ENV_FILE"
        return 1
    fi
    
    print_success ".env file found"
    echo ""
    
    # Required variables
    REQUIRED_VARS=(
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
    
    print_info "Checking required variables..."
    MISSING_VARS=()
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE"; then
            MISSING_VARS+=("$var")
            print_error "Missing: $var"
        else
            print_success "Found: $var"
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        echo ""
        print_error "Missing ${#MISSING_VARS[@]} required variable(s)"
        return 1
    fi
    
    echo ""
    print_info "Checking Docker service names..."
    
    ISSUES=()
    
    # Check DATABASE_URL
    DB_URL=$(get_env DATABASE_URL)
    if echo "$DB_URL" | grep -q "localhost"; then
        print_error "DATABASE_URL uses localhost (should be postgres-core)"
        ISSUES+=("DATABASE_URL")
    elif echo "$DB_URL" | grep -q "postgres-core:5432"; then
        print_success "DATABASE_URL correct"
    fi
    
    # Check REDIS_URL
    REDIS_URL=$(get_env REDIS_URL)
    if echo "$REDIS_URL" | grep -q "localhost"; then
        print_error "REDIS_URL uses localhost (should be redis-core)"
        ISSUES+=("REDIS_URL")
    elif echo "$REDIS_URL" | grep -q "redis-core:6379"; then
        print_success "REDIS_URL correct"
    fi
    
    # Check QDRANT_HOST
    QDRANT_HOST=$(get_env QDRANT_HOST)
    if [ "$QDRANT_HOST" = "localhost" ]; then
        print_error "QDRANT_HOST uses localhost (should be qdrant)"
        ISSUES+=("QDRANT_HOST")
    elif [ "$QDRANT_HOST" = "qdrant" ]; then
        print_success "QDRANT_HOST correct"
    fi
    
    # Check passwords
    echo ""
    print_info "Checking password security..."
    
    POSTGRES_PASS=$(get_env POSTGRES_PASSWORD)
    if [ "$POSTGRES_PASS" = "core_pass" ]; then
        print_error "POSTGRES_PASSWORD is default value!"
        ISSUES+=("POSTGRES_PASSWORD")
    else
        print_success "POSTGRES_PASSWORD is secure"
    fi
    
    # Summary
    echo ""
    echo -e "${BLUE}========================================${NC}"
    if [ ${#ISSUES[@]} -eq 0 ]; then
        print_success "All checks passed!"
        print_success "Your .env file is ready"
    else
        print_error "Found ${#ISSUES[@]} issue(s)"
        for issue in "${ISSUES[@]}"; do
            echo -e "${RED}  - $issue${NC}"
        done
    fi
    
    echo ""
    read -p "Press Enter to continue..."
    show_menu
}

# ============================================
# 2. Manage API Keys
# ============================================
manage_apikeys() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}API Keys Management${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "1) Show INGEST_API_KEY"
    echo "2) Generate new INGEST_API_KEY"
    echo "3) Show USERS_API_KEY"
    echo "4) Generate new USERS_API_KEY"
    echo "5) Back to main menu"
    echo ""
    read -p "Your choice (1-5): " choice
    
    case "$choice" in
        1)
            CURRENT=$(get_env INGEST_API_KEY || true)
            if [ -n "$CURRENT" ]; then
                print_success "INGEST_API_KEY: $CURRENT"
            else
                print_warning "INGEST_API_KEY not set"
            fi
            read -p "Press Enter to continue..."
            manage_apikeys
            ;;
        2)
            read -p "Generate new INGEST_API_KEY? (y/N): " ans
            if [[ $ans =~ ^[Yy]$ ]]; then
                cp "$ENV_FILE" "$ENV_FILE.backup-$TIMESTAMP"
                print_info "Backup created: .env.backup-$TIMESTAMP"
                NEW_KEY=$(openssl rand -base64 48 | tr -d '\n')
                set_env INGEST_API_KEY "$NEW_KEY"
                print_success "New INGEST_API_KEY generated"
                echo ""
                echo "INGEST_API_KEY: $NEW_KEY"
                echo ""
                print_warning "Update this key in Ingest system"
            fi
            read -p "Press Enter to continue..."
            manage_apikeys
            ;;
        3)
            CURRENT=$(get_env USERS_API_KEY || true)
            if [ -n "$CURRENT" ]; then
                print_success "USERS_API_KEY: $CURRENT"
            else
                print_warning "USERS_API_KEY not set"
            fi
            read -p "Press Enter to continue..."
            manage_apikeys
            ;;
        4)
            read -p "Generate new USERS_API_KEY? (y/N): " ans
            if [[ $ans =~ ^[Yy]$ ]]; then
                cp "$ENV_FILE" "$ENV_FILE.backup-$TIMESTAMP"
                print_info "Backup created: .env.backup-$TIMESTAMP"
                NEW_KEY=$(openssl rand -base64 48 | tr -d '\n')
                set_env USERS_API_KEY "$NEW_KEY"
                print_success "New USERS_API_KEY generated"
                echo ""
                echo "USERS_API_KEY: $NEW_KEY"
                echo ""
                print_warning "Update this key in Users system"
            fi
            read -p "Press Enter to continue..."
            manage_apikeys
            ;;
        5)
            show_menu
            ;;
        *)
            print_error "Invalid choice"
            manage_apikeys
            ;;
    esac
}

# ============================================
# 3. Rotate Secrets
# ============================================
rotate_secrets() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Rotate Secrets${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    print_warning "This will rotate all application secrets"
    print_warning "A backup will be created automatically"
    echo ""
    read -p "Continue? (y/N): " confirm
    
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        print_info "Cancelled"
        show_menu
        return
    fi
    
    # Backup
    cp "$ENV_FILE" "$ENV_FILE.backup-$TIMESTAMP"
    print_success "Backup created: .env.backup-$TIMESTAMP"
    
    # Generate new secrets
    NEW_JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    NEW_REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')
    
    set_env JWT_SECRET_KEY "$NEW_JWT_SECRET"
    set_env REDIS_PASSWORD "$NEW_REDIS_PASSWORD"
    
    print_success "JWT_SECRET_KEY rotated"
    print_success "REDIS_PASSWORD rotated"
    
    # Update REDIS_URL
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
        print_success "REDIS_URL updated"
    fi
    
    # Update Celery URLs
    OLD_BROKER=$(get_env CELERY_BROKER_URL || true)
    if [ -n "$OLD_BROKER" ] && echo "$OLD_BROKER" | grep -q 'redis://'; then
        NEW_BROKER=$(echo "$OLD_BROKER" | sed -E "s#redis://:[^@]*@#redis://:$NEW_REDIS_PASSWORD@#")
        set_env CELERY_BROKER_URL "$NEW_BROKER"
        print_success "CELERY_BROKER_URL updated"
    fi
    
    OLD_BACKEND=$(get_env CELERY_RESULT_BACKEND || true)
    if [ -n "$OLD_BACKEND" ] && echo "$OLD_BACKEND" | grep -q 'redis://'; then
        NEW_BACKEND=$(echo "$OLD_BACKEND" | sed -E "s#redis://:[^@]*@#redis://:$NEW_REDIS_PASSWORD@#")
        set_env CELERY_RESULT_BACKEND "$NEW_BACKEND"
        print_success "CELERY_RESULT_BACKEND updated"
    fi
    
    echo ""
    print_success "Rotation complete!"
    print_warning "Restart services to apply changes:"
    echo "  cd $SCRIPT_DIR/docker"
    echo "  docker-compose restart"
    
    echo ""
    read -p "Press Enter to continue..."
    show_menu
}

# Main
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found at: $ENV_FILE"
    print_info "Run ./deploy.sh first to create .env"
    exit 1
fi

show_menu
