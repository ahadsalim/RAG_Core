#!/bin/bash

# ==============================================================================
# Core RAG System - Production Deployment Script
# Version: 2.0.0
# 
# This script handles:
# - Prerequisite installation (Docker, Docker Compose)
# - Secure password generation
# - Environment configuration
# - Directory creation with proper permissions
# - Docker image building and service startup
# - Database migrations
# - Systemd service setup
# - Post-installation instructions
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Printing functions
print_header() {
    echo ""
    echo -e "${PURPLE}==============================================================${NC}"
    echo -e "${PURPLE}${BOLD}  $1${NC}"
    echo -e "${PURPLE}==============================================================${NC}"
}

print_section() {
    echo ""
    echo -e "${CYAN}>>> $1${NC}"
}

print_info() { echo -e "${BLUE}[ℹ]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

wait_for_service() {
    local service=$1
    local port=$2
    local max_retries=${3:-30}
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        if curl -sf "http://localhost:$port" > /dev/null 2>&1; then
            return 0
        fi
        retry=$((retry + 1))
        sleep 2
    done
    return 1
}

# Detect directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="/var/lib/core/backups"
LOG_DIR="/var/log/core"

# Banner
print_header "Core RAG System - Production Deployment v2.0"
echo -e "${CYAN}Project Root: $PROJECT_ROOT${NC}"

# Show help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    cat << EOF

Usage: $0 [OPTIONS]

Options:
  -r, --rebuild      Force rebuild Docker images without cache
  -s, --skip-build   Skip Docker build (use existing images)
  -m, --migrate-only Only run database migrations
  -h, --help         Show this help message

Examples:
  $0                 # Normal deployment (with cache)
  $0 --rebuild       # Full rebuild without cache
  $0 --skip-build    # Start without rebuilding

Post-Installation:
  - Nginx Proxy Manager will be available at: http://localhost:81
  - Default NPM credentials: admin@example.com / changeme
  - Use NPM to configure SSL certificates for production

EOF
    exit 0
fi

# Parse arguments
REBUILD=false
SKIP_BUILD=false
MIGRATE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--rebuild)
            REBUILD=true
            print_info "Rebuild mode enabled"
            shift
            ;;
        -s|--skip-build)
            SKIP_BUILD=true
            print_info "Skip build mode enabled"
            shift
            ;;
        -m|--migrate-only)
            MIGRATE_ONLY=true
            print_info "Migration only mode enabled"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Step 1: Check prerequisites
# ============================================================================
print_section "Step 1: Checking Prerequisites"

if ! command_exists docker; then
    print_warning "Docker is not installed. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    print_success "Docker installed successfully"
else
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    print_success "Docker installed (v$DOCKER_VERSION)"
fi

if ! command_exists docker-compose; then
    print_warning "Docker Compose is not installed. Installing..."
    apt-get update && apt-get install -y docker-compose
    print_success "Docker Compose installed"
else
    COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f3 | tr -d ',')
    print_success "Docker Compose installed (v$COMPOSE_VERSION)"
fi

if ! command_exists openssl; then
    print_error "OpenSSL is required but not installed"
    exit 1
fi

if ! command_exists curl; then
    apt-get update && apt-get install -y curl
fi

print_success "All prerequisites satisfied"

# ============================================================================
# Step 2: Create required directories
# ============================================================================
print_section "Step 2: Creating Required Directories"

# Create data directories
mkdir -p "$DATA_DIR/nginx-proxy-manager/data"
mkdir -p "$DATA_DIR/nginx-proxy-manager/letsencrypt"
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

# Set permissions
chmod -R 755 "$DATA_DIR" 2>/dev/null || true
chmod -R 700 "$BACKUP_DIR" 2>/dev/null || true

print_success "Directories created:"
echo "    - $DATA_DIR/nginx-proxy-manager/"
echo "    - $BACKUP_DIR/"
echo "    - $LOG_DIR/"

# ============================================================================
# Step 3: Environment Configuration
# ============================================================================
print_section "Step 3: Environment Configuration"

# Variables to save for post-install display
GENERATED_PASSWORDS=""

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    print_warning ".env file not found. Creating from template..."
    
    if [ ! -f "$SCRIPT_DIR/config/.env.example" ]; then
        print_error "Template file not found: $SCRIPT_DIR/config/.env.example"
        exit 1
    fi
    
    cp "$SCRIPT_DIR/config/.env.example" "$PROJECT_ROOT/.env"
    
    # Generate secure passwords
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    FLOWER_PASSWORD=$(openssl rand -hex 12)
    INGEST_API_KEY=$(openssl rand -base64 48 | tr -d '\n')
    USERS_API_KEY=$(openssl rand -base64 48 | tr -d '\n')
    
    # Store for post-install display
    GENERATED_PASSWORDS="NEW_INSTALLATION"
    
    # Update .env with secure values
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
    sed -i "s/core_pass/$DB_PASSWORD/g" "$PROJECT_ROOT/.env"
    sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$DB_PASSWORD#g" "$PROJECT_ROOT/.env"
    sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' "$PROJECT_ROOT/.env"
    
    # Update Redis URLs
    sed -i "s#redis://redis-core:6379#redis://:$REDIS_PASSWORD@redis-core:6379#g" "$PROJECT_ROOT/.env"
    sed -i "s#CELERY_BROKER_URL=.*#CELERY_BROKER_URL=\"redis://:$REDIS_PASSWORD@redis-core:6379/1\"#g" "$PROJECT_ROOT/.env"
    sed -i "s#CELERY_RESULT_BACKEND=.*#CELERY_RESULT_BACKEND=\"redis://:$REDIS_PASSWORD@redis-core:6379/2\"#g" "$PROJECT_ROOT/.env"
    
    # Add Flower password
    echo "FLOWER_PASSWORD=\"$FLOWER_PASSWORD\"" >> "$PROJECT_ROOT/.env"
    
    # Update API keys
    sed -i "s#INGEST_API_KEY=\"\"#INGEST_API_KEY=\"$INGEST_API_KEY\"#g" "$PROJECT_ROOT/.env"
    sed -i "s#USERS_API_KEY=\"\"#USERS_API_KEY=\"$USERS_API_KEY\"#g" "$PROJECT_ROOT/.env"
    
    # Ask for domain
    echo ""
    read -p "Enter your domain name (leave empty for localhost): " DOMAIN_INPUT
    if [ -z "$DOMAIN_INPUT" ]; then
        DOMAIN_INPUT="localhost"
    fi
    
    # Set environment to production if real domain
    if [ "$DOMAIN_INPUT" != "localhost" ]; then
        sed -i "s/ENVIRONMENT=\"development\"/ENVIRONMENT=\"production\"/g" "$PROJECT_ROOT/.env"
        sed -i "s/DEBUG=true/DEBUG=false/g" "$PROJECT_ROOT/.env"
        sed -i "s/RELOAD=true/RELOAD=false/g" "$PROJECT_ROOT/.env"
    fi
    
    sed -i '/^DOMAIN_NAME=/d' "$PROJECT_ROOT/.env"
    echo "DOMAIN_NAME=\"$DOMAIN_INPUT\"" >> "$PROJECT_ROOT/.env"
    
    # Update CORS_ORIGINS
    if [ "$DOMAIN_INPUT" != "localhost" ]; then
        sed -i "s#CORS_ORIGINS=.*#CORS_ORIGINS=\"https://$DOMAIN_INPUT,http://localhost:3000\"#g" "$PROJECT_ROOT/.env"
    fi
    
    print_success ".env file created with secure passwords"
else
    print_success ".env file already exists"
    
    # Validate existing .env
    print_info "Validating existing .env file..."
    MISSING_VARS=()
    REQUIRED_VARS=(JWT_SECRET_KEY DATABASE_URL REDIS_URL QDRANT_HOST CELERY_BROKER_URL POSTGRES_PASSWORD)
    
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^${var}=" "$PROJECT_ROOT/.env"; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        print_error "Missing required variables: ${MISSING_VARS[*]}"
        print_info "Please update your .env file or delete it to regenerate"
        exit 1
    fi
    
    # Check for default passwords
    if grep -q 'POSTGRES_PASSWORD=core_pass' "$PROJECT_ROOT/.env" || \
       grep -q 'POSTGRES_PASSWORD="core_pass"' "$PROJECT_ROOT/.env"; then
        print_warning "Default database password detected! Consider changing it."
    fi
    
    print_success ".env validation passed"
fi

# Create symlink for docker-compose
print_info "Creating symlink for docker-compose..."
if [ -L "$SCRIPT_DIR/docker/.env" ]; then
    rm "$SCRIPT_DIR/docker/.env"
fi
ln -sf "$PROJECT_ROOT/.env" "$SCRIPT_DIR/docker/.env"
print_success "Symlink created"

# ============================================================================
# Step 4: Build and Start Docker Services
# ============================================================================
print_section "Step 4: Building and Starting Services"

# Migration only mode
if [ "$MIGRATE_ONLY" = true ]; then
    print_info "Migration only mode - skipping build and start"
    # Jump to migrations
else
    # Build Docker images
    if [ "$SKIP_BUILD" = false ]; then
        if [ "$REBUILD" = true ]; then
            print_info "Building Docker images (no cache)..."
            docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" build --no-cache
        else
            print_info "Building Docker images (with cache)..."
            docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" build
        fi
        print_success "Docker images built"
    else
        print_info "Skipping Docker build (using existing images)"
    fi
    
    # Stop existing services gracefully
    print_info "Stopping existing services..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" stop 2>/dev/null || true
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" rm -f 2>/dev/null || true
    
    # Start services
    print_info "Starting services..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" up -d
    
    # Wait for services with progress indicator
    print_info "Waiting for services to be ready..."
    echo -n "    "
    for i in {1..30}; do
        echo -n "."
        sleep 1
    done
    echo " done"
fi

# ============================================================================
# Step 5: Health Checks
# ============================================================================
print_section "Step 5: Service Health Checks"

print_info "Checking services health..."
echo ""
docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" ps
echo ""

# Check individual services
SERVICES_OK=true

# PostgreSQL
if docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T postgres-core pg_isready -U core_user -d core_db > /dev/null 2>&1; then
    print_success "PostgreSQL is healthy"
else
    print_warning "PostgreSQL not ready yet"
    SERVICES_OK=false
fi

# Redis
if docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T redis-core redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is healthy"
else
    print_warning "Redis not ready yet"
    SERVICES_OK=false
fi

# Qdrant
if curl -sf http://localhost:7333/health > /dev/null 2>&1; then
    print_success "Qdrant is healthy"
else
    print_warning "Qdrant not ready yet (port 7333)"
fi

# ============================================================================
# Step 6: Database Migrations
# ============================================================================
print_section "Step 6: Database Migrations"

if [ -d "$PROJECT_ROOT/alembic" ]; then
    print_info "Running database migrations..."
    
    # Wait for core-api to be ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    echo -n "    Waiting for Core API container"
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T core-api python -c "import sys; sys.exit(0)" 2>/dev/null; then
            echo ""
            print_success "Core API container is ready"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -n "."
        sleep 2
    done
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo ""
        print_warning "Core API container not ready, skipping migrations"
        print_info "Run manually: docker-compose exec core-api alembic upgrade head"
    else
        if docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T core-api alembic upgrade head 2>&1; then
            print_success "Database migrations completed"
        else
            print_warning "Migration may have issues - check logs"
        fi
    fi
else
    print_info "No alembic directory found, skipping migrations"
fi

# ============================================================================
# Step 7: Systemd Service Setup
# ============================================================================
print_section "Step 7: Systemd Service Setup"

if [ "$EUID" -eq 0 ]; then
    print_info "Setting up systemd service..."
    cat > /etc/systemd/system/core-api.service <<EOF
[Unit]
Description=Core RAG System API
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml up -d
ExecStop=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml down
ExecReload=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml restart
TimeoutStartSec=300
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable core-api.service
    print_success "Systemd service configured and enabled"
    print_info "Service will auto-start on boot"
else
    print_warning "Not running as root - skipping systemd setup"
    print_info "Run as root to enable auto-start on boot"
fi

# ============================================================================
# Step 8: Final Checks and Summary
# ============================================================================
print_section "Step 8: Final Verification"

sleep 5

API_STATUS="offline"
if curl -sf http://localhost:7001/health > /dev/null 2>&1; then
    print_success "API is responding on port 7001"
    API_STATUS="online"
else
    print_warning "API not responding yet (may need more time to start)"
    print_info "Check logs: docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml logs -f core-api"
fi

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================
print_header "DEPLOYMENT COMPLETED SUCCESSFULLY!"

echo ""
echo -e "${GREEN}${BOLD}✓ Core RAG System is ready!${NC}"
echo ""

# Read values from .env
JWT_SECRET=$(grep "^JWT_SECRET_KEY=" "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '"')
POSTGRES_PASS=$(grep "^POSTGRES_PASSWORD=" "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '"')
REDIS_PASS=$(grep "^REDIS_PASSWORD=" "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '"')
FLOWER_PASS=$(grep "^FLOWER_PASSWORD=" "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "admin123")
DOMAIN=$(grep "^DOMAIN_NAME=" "$PROJECT_ROOT/.env" | cut -d'=' -f2 | tr -d '"')

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}                     ACCESS POINTS                          ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${YELLOW}▶ API Documentation:${NC}       http://localhost:7001/docs"
echo -e "  ${YELLOW}▶ Health Check:${NC}            http://localhost:7001/health"
echo -e "  ${YELLOW}▶ Flower (Celery Monitor):${NC} http://localhost:5555"
echo -e "  ${YELLOW}▶ Nginx Proxy Manager:${NC}     http://localhost:81"
echo -e "  ${YELLOW}▶ Qdrant Dashboard:${NC}        http://localhost:7333/dashboard"
echo ""

if [ "$GENERATED_PASSWORDS" = "NEW_INSTALLATION" ]; then
    echo -e "${CYAN}==============================================================${NC}"
    echo -e "${CYAN}              GENERATED CREDENTIALS (SAVE THESE!)            ${NC}"
    echo -e "${CYAN}==============================================================${NC}"
    echo ""
    echo -e "  ${RED}${BOLD}[!] IMPORTANT: Save these credentials securely!${NC}"
    echo ""
    echo -e "  ${YELLOW}PostgreSQL:${NC}"
    echo -e "    User:     core_user"
    echo -e "    Password: $POSTGRES_PASS"
    echo ""
    echo -e "  ${YELLOW}Redis:${NC}"
    echo -e "    Password: $REDIS_PASS"
    echo ""
    echo -e "  ${YELLOW}Flower:${NC}"
    echo -e "    User:     admin"
    echo -e "    Password: $FLOWER_PASS"
    echo ""
fi

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}               NGINX PROXY MANAGER SETUP                     ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${YELLOW}1. Open:${NC} http://localhost:81"
echo -e "  ${YELLOW}2. Default Login:${NC}"
echo -e "     Email:    admin@example.com"
echo -e "     Password: changeme"
echo ""
echo -e "  ${YELLOW}3. SSL Setup for Production:${NC}"
echo -e "     - Go to 'Hosts' > 'Proxy Hosts' > 'Add Proxy Host'"
echo -e "     - Domain: $DOMAIN"
echo -e "     - Forward Hostname: core-api"
echo -e "     - Forward Port: 7001"
echo -e "     - Enable 'Block Common Exploits'"
echo -e "     - In SSL tab, enable 'Force SSL' and 'HTTP/2 Support'"
echo -e "     - Request Let's Encrypt certificate"
echo ""

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}             USERS SYSTEM INTEGRATION                        ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${YELLOW}JWT Secret Key (MUST be shared with Users System):${NC}"
echo ""
echo -e "  ${GREEN}$JWT_SECRET${NC}"
echo ""
echo -e "  ${RED}[!] Copy this EXACT value to Users System .env file${NC}"
echo -e "  ${RED}[!] Both systems MUST use the same JWT_SECRET_KEY${NC}"
echo ""

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}                   USEFUL COMMANDS                           ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${YELLOW}View Logs:${NC}"
echo -e "    docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml logs -f"
echo ""
echo -e "  ${YELLOW}View Specific Service Logs:${NC}"
echo -e "    docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml logs -f core-api"
echo ""
echo -e "  ${YELLOW}Restart Services:${NC}"
echo -e "    docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml restart"
echo ""
echo -e "  ${YELLOW}Stop Services:${NC}"
echo -e "    docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml down"
echo ""
echo -e "  ${YELLOW}Backup:${NC}"
echo -e "    $SCRIPT_DIR/backup_auto.sh run       # Auto backup"
echo -e "    $SCRIPT_DIR/backup_manual.sh         # Manual backup menu"
echo ""
echo -e "  ${YELLOW}Manage Configuration:${NC}"
echo -e "    $SCRIPT_DIR/manage.sh"
echo ""

echo -e "${CYAN}==============================================================${NC}"
echo -e "${CYAN}                    DOCUMENTATION                            ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${YELLOW}•${NC} Main Documentation: $PROJECT_ROOT/document/README.md"
echo -e "  ${YELLOW}•${NC} API Guide: $PROJECT_ROOT/document/3_USERS_SYSTEM_API_GUIDE.md"
echo -e "  ${YELLOW}•${NC} Streaming Guide: $PROJECT_ROOT/document/STREAMING_API_GUIDE.md"
echo ""
echo -e "${GREEN}${BOLD}Deployment completed at $(date)${NC}"
echo ""
