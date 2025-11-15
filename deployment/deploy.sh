#!/bin/bash

# Core RAG System - Unified Deployment Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

print_info() { echo -e "${BLUE}[INFO] $1${NC}"; }
print_success() { echo -e "${GREEN}[OK] $1${NC}"; }
print_error() { echo -e "${RED}[ERROR] $1${NC}"; }
print_warning() { echo -e "${YELLOW}[WARN] $1${NC}"; }

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_header "Core RAG System - Deployment"

# Show help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -r, --rebuild    Force rebuild Docker images without cache"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0               # Normal deployment (with cache)"
    echo "  $0 --rebuild     # Full rebuild without cache"
    echo ""
    exit 0
fi

# Parse arguments
REBUILD=false
if [[ "$1" == "--rebuild" ]] || [[ "$1" == "-r" ]]; then
    REBUILD=true
    print_info "Rebuild mode enabled"
fi

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Installing..."
    apt-get update && apt-get install -y docker-compose
fi

print_success "Prerequisites checked"

# Create .env if not exists
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
    
    # Update .env with secure values
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
    sed -i "s/core_pass/$DB_PASSWORD/g" "$PROJECT_ROOT/.env"
    sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$DB_PASSWORD#g" "$PROJECT_ROOT/.env"
    sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' "$PROJECT_ROOT/.env"
    
    # Update Redis URLs
    sed -i "s#redis://redis-core:6379#redis://:$REDIS_PASSWORD@redis-core:6379#g" "$PROJECT_ROOT/.env"
    sed -i "s#CELERY_BROKER_URL=.*#CELERY_BROKER_URL=\"redis://:$REDIS_PASSWORD@redis-core:6379/1\"#g" "$PROJECT_ROOT/.env"
    sed -i "s#CELERY_RESULT_BACKEND=.*#CELERY_RESULT_BACKEND=\"redis://:$REDIS_PASSWORD@redis-core:6379/2\"#g" "$PROJECT_ROOT/.env"
    
    # Ask for domain
    read -p "Enter your domain name (or press Enter for localhost): " DOMAIN_INPUT
    if [ -z "$DOMAIN_INPUT" ]; then
        DOMAIN_INPUT="localhost"
    fi
    
    sed -i '/^DOMAIN_NAME=/d' "$PROJECT_ROOT/.env"
    echo "DOMAIN_NAME=\"$DOMAIN_INPUT\"" >> "$PROJECT_ROOT/.env"
    
    print_success ".env file created with secure passwords"
else
    print_success ".env file already exists"
    
    # Validate existing .env
    print_info "Validating existing .env file..."
    MISSING_VARS=()
    for var in JWT_SECRET_KEY DATABASE_URL REDIS_URL QDRANT_HOST CELERY_BROKER_URL; do
        if ! grep -q "^${var}=" "$PROJECT_ROOT/.env"; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        print_warning "Missing variables in .env: ${MISSING_VARS[*]}"
        print_warning "Consider running: ./manage.sh (option 1 to validate)"
    else
        print_success ".env validation passed"
    fi
fi

# Create symlink for docker-compose
print_info "Creating symlink for docker-compose..."
if [ -L "$SCRIPT_DIR/docker/.env" ]; then
    rm "$SCRIPT_DIR/docker/.env"
fi
ln -sf "$PROJECT_ROOT/.env" "$SCRIPT_DIR/docker/.env"
print_success "Symlink created"

# Build Docker images
if [ "$REBUILD" = true ]; then
    print_info "Building Docker images (no cache)..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" build --no-cache
else
    print_info "Building Docker images (with cache)..."
    docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" build
fi

# Start services (with fix for ContainerConfig error)
print_info "Starting services..."
docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" stop 2>/dev/null || true
docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" rm -f 2>/dev/null || true
docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" up -d

# Wait for services
print_info "Waiting for services to be ready..."
sleep 20

# Check health
print_info "Checking services health..."
docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" ps

# Run migrations
if [ -d "$PROJECT_ROOT/alembic" ]; then
    print_info "Running database migrations..."
    
    # Wait for core-api to be ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T core-api python -c "import sys; sys.exit(0)" 2>/dev/null; then
            print_success "Core API container is ready"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -n "."
        sleep 2
    done
    echo ""
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        print_warning "Core API container not ready, skipping migrations"
    else
        docker-compose -f "$SCRIPT_DIR/docker/docker-compose.yml" exec -T core-api alembic upgrade head || \
            print_warning "Migration failed, may need manual intervention"
    fi
fi

# Setup systemd service
if [ "$EUID" -eq 0 ]; then
    print_info "Setting up systemd service..."
    cat > /etc/systemd/system/core-api.service <<EOF
[Unit]
Description=Core API System
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml up -d
ExecStop=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml down
ExecReload=/usr/bin/docker-compose -f $SCRIPT_DIR/docker/docker-compose.yml restart

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable core-api.service
    print_success "Systemd service configured"
fi

# Final checks
print_info "Running final checks..."
sleep 5

if curl -f http://localhost:7001/health > /dev/null 2>&1; then
    print_success "API is responding"
else
    print_warning "API is not responding yet. Check logs: docker-compose logs core-api"
fi

print_header "Deployment Completed!"

echo ""
echo -e "${GREEN}Core RAG System is ready!${NC}"
echo ""
echo -e "${YELLOW}Access Points:${NC}"
echo "  • API Documentation: http://localhost:7001/docs"
echo "  • Health Check: http://localhost:7001/health"
echo "  • Flower (Celery): http://localhost:5555"
echo "  • Nginx Proxy Manager: http://localhost:81"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  • View logs: cd $SCRIPT_DIR/docker && docker-compose logs -f"
echo "  • Restart: cd $SCRIPT_DIR/docker && docker-compose restart"
echo "  • Stop: cd $SCRIPT_DIR/docker && docker-compose stop"
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo "  • $PROJECT_ROOT/document/README.md"
echo ""
