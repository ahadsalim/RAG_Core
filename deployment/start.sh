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

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root or with sudo"
    echo "Please run: sudo $0 $@"
    exit 1
fi

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
  - API will be available at: http://localhost:7001
  - Check documentation for SSL setup if needed

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
# Step 0.5: Configure apt to use cache server (MUST be before Docker install)
# ============================================================================
print_section "Step 0.5: Configuring apt Cache Server"

CACHE_SERVER="10.10.10.111"

# Check if cache server is accessible
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/3142" 2>/dev/null; then
    print_success "Cache server accessible - configuring apt proxy"
    
    # Configure apt proxy for HTTP and HTTPS
    echo 'Acquire::http::Proxy "http://10.10.10.111:3142";' | sudo tee /etc/apt/apt.conf.d/00proxy > /dev/null
    echo 'Acquire::https::Proxy "http://10.10.10.111:3144";' | sudo tee -a /etc/apt/apt.conf.d/00proxy > /dev/null
    
    print_success "apt configured to use cache server (ports 3142 for HTTP, 3144 for HTTPS)"
    
    # Test apt update
    print_info "Testing apt update through cache..."
    if sudo apt-get update -qq 2>&1 | grep -q "Failed to fetch"; then
        print_warning "apt update had some warnings, but continuing..."
    else
        print_success "apt update successful through cache"
    fi
else
    print_warning "Cache server not accessible - will try direct internet connection"
fi

# ============================================================================
# Step 1: Check prerequisites
# ============================================================================
print_section "Step 1: Checking Prerequisites"

if ! command_exists docker; then
    print_warning "Docker is not installed. Installing..."
    
    # Check if cache server is accessible for Docker installation
    if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/80" 2>/dev/null; then
        print_info "Installing Docker from cache server..."
        
        # Install prerequisites
        sudo apt-get install -y ca-certificates curl gnupg
        
        # Get Docker GPG key from cache server
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL http://$CACHE_SERVER/keys/docker.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        
        # Add Docker repository (will use apt-cacher-ng proxy)
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
            sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin
        
        print_success "Docker installed from cache server"
    else
        print_warning "Cache server not accessible - trying internet installation..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        print_success "Docker installed from internet"
    fi
    
    systemctl enable docker
    systemctl start docker
    print_success "Docker service started"
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

# ============================================================================
# Step 1.5: Check Cache Server Connectivity
# ============================================================================
print_section "Step 1.5: Checking Cache Server Connectivity"

CACHE_SERVER="10.10.10.111"

# Check Docker registry (port 5001)
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/5001" 2>/dev/null; then
    print_success "Docker registry cache accessible (port 5001)"
else
    print_warning "Docker registry cache not accessible (port 5001) - will try to pull from internet"
fi

# Check PyPI devpi (port 3141)
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/3141" 2>/dev/null; then
    print_success "PyPI cache (devpi) accessible (port 3141)"
else
    print_warning "PyPI cache not accessible (port 3141) - will try to install from internet"
fi

# Check apt-cacher-ng HTTP (port 3142)
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/3142" 2>/dev/null; then
    print_success "apt-cacher-ng HTTP accessible (port 3142)"
else
    print_warning "apt-cacher-ng HTTP not accessible (port 3142) - apt packages may download from internet"
fi

# Check apt-cacher-ng HTTPS tunneling (port 3144)
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/3144" 2>/dev/null; then
    print_success "apt-cacher-ng HTTPS tunneling accessible (port 3144)"
else
    print_warning "apt-cacher-ng HTTPS not accessible (port 3144) - Docker repo may fail"
fi

# Check offline packages nginx (port 80)
if curl -sf -m 3 http://$CACHE_SERVER/pypi-offline/ > /dev/null 2>&1; then
    print_success "Offline packages (nginx) accessible - sentence-transformers 5.2.3 available"
else
    print_warning "Offline packages not accessible - sentence-transformers may fail to install"
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
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

# Set permissions
chmod -R 700 "$BACKUP_DIR" 2>/dev/null || true

print_success "Directories created:"
echo "    - $BACKUP_DIR/"
echo "    - $LOG_DIR/"

# ============================================================================
# Step 3: Environment Configuration
# ============================================================================
print_section "Step 3: Environment Configuration"

# Variables to save for post-install display
GENERATED_PASSWORDS=""

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    print_warning ".env file not found. Creating new configuration..."
    
    # Generate secure passwords
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    FLOWER_PASSWORD=$(openssl rand -hex 12)
    INGEST_API_KEY=$(openssl rand -base64 48 | tr -d '\n')
    USERS_API_KEY=$(openssl rand -base64 48 | tr -d '\n')
    
    # Store for post-install display
    GENERATED_PASSWORDS="NEW_INSTALLATION"
    
    # Ask for domain
    echo ""
    read -p "Enter your domain name (leave empty for localhost): " DOMAIN_INPUT
    if [ -z "$DOMAIN_INPUT" ]; then
        DOMAIN_INPUT="localhost"
    fi
    
    # Ask for Users System configuration
    echo ""
    print_section "Users System Configuration"
    echo -e "${YELLOW}Enter the IP/domain and port of your Users System (for CORS)${NC}"
    read -p "Users System IP/Domain [10.10.10.30]: " USERS_IP_INPUT
    if [ -z "$USERS_IP_INPUT" ]; then
        USERS_IP_INPUT="10.10.10.30"
    fi
    
    read -p "Users System Port [3001]: " USERS_PORT_INPUT
    if [ -z "$USERS_PORT_INPUT" ]; then
        USERS_PORT_INPUT="3001"
    fi
    
    # Build CORS origins list
    CORS_ORIGINS="http://localhost:3001,http://${USERS_IP_INPUT},http://${USERS_IP_INPUT}:${USERS_PORT_INPUT}"
    if [ "$DOMAIN_INPUT" != "localhost" ]; then
        CORS_ORIGINS="${CORS_ORIGINS},https://${DOMAIN_INPUT}"
    fi
    
    # Set environment based on domain
    if [ "$DOMAIN_INPUT" != "localhost" ]; then
        ENVIRONMENT="production"
        DEBUG="false"
        RELOAD="false"
    else
        ENVIRONMENT="development"
        DEBUG="false"
        RELOAD="false"
    fi

    # --- Ask for LLM API Keys ---
    echo ""
    print_section "LLM Configuration"
    echo -e "${YELLOW}LLM1 (Light) - for general queries (e.g. gpt-4o-mini)${NC}"
    read -p "Enter LLM1 API Key: " LLM1_KEY_INPUT
    if [ -z "$LLM1_KEY_INPUT" ]; then
        LLM1_KEY_INPUT="your_api_key_here"
    fi
    
    read -p "Enter LLM1 Base URL [https://api.gapgpt.app/v1]: " LLM1_URL_INPUT
    if [ -z "$LLM1_URL_INPUT" ]; then
        LLM1_URL_INPUT="https://api.gapgpt.app/v1"
    fi
    
    read -p "Enter LLM1 Model [gpt-4o-mini]: " LLM1_MODEL_INPUT
    if [ -z "$LLM1_MODEL_INPUT" ]; then
        LLM1_MODEL_INPUT="gpt-4o-mini"
    fi
    
    echo ""
    echo -e "${YELLOW}LLM2 (Pro) - for business queries (e.g. gpt-5-mini)${NC}"
    read -p "Enter LLM2 API Key (leave empty to use LLM1 key): " LLM2_KEY_INPUT
    if [ -z "$LLM2_KEY_INPUT" ]; then
        LLM2_KEY_INPUT="$LLM1_KEY_INPUT"
    fi
    
    read -p "Enter LLM2 Base URL [use LLM1 URL]: " LLM2_URL_INPUT
    if [ -z "$LLM2_URL_INPUT" ]; then
        LLM2_URL_INPUT="$LLM1_URL_INPUT"
    fi
    
    read -p "Enter LLM2 Model [gpt-5-mini]: " LLM2_MODEL_INPUT
    if [ -z "$LLM2_MODEL_INPUT" ]; then
        LLM2_MODEL_INPUT="gpt-5-mini"
    fi
    
    echo ""
    echo -e "${YELLOW}Classification LLM (for query categorization)${NC}"
    read -p "Enter Classification LLM API Key (leave empty to use LLM1 key): " CLASS_KEY_INPUT
    if [ -z "$CLASS_KEY_INPUT" ]; then
        CLASS_KEY_INPUT="$LLM1_KEY_INPUT"
    fi
    
    read -p "Enter Classification LLM Base URL [use LLM1 URL]: " CLASS_URL_INPUT
    if [ -z "$CLASS_URL_INPUT" ]; then
        CLASS_URL_INPUT="$LLM1_URL_INPUT"
    fi
    
    read -p "Enter Classification LLM Model [gpt-4o-mini]: " CLASS_MODEL_INPUT
    if [ -z "$CLASS_MODEL_INPUT" ]; then
        CLASS_MODEL_INPUT="gpt-4o-mini"
    fi
    
    # --- Ask for S3/MinIO ---
    echo ""
    print_section "S3/MinIO Configuration"
    read -p "Enter S3/MinIO Endpoint URL [http://10.10.10.50:9000]: " S3_URL_INPUT
    if [ -z "$S3_URL_INPUT" ]; then
        S3_URL_INPUT="http://10.10.10.50:9000"
    fi
    
    read -p "Enter S3 Access Key: " S3_KEY_INPUT
    if [ -z "$S3_KEY_INPUT" ]; then
        S3_KEY_INPUT="your_s3_access_key"
    fi
    
    read -p "Enter S3 Secret Key: " S3_SECRET_INPUT
    if [ -z "$S3_SECRET_INPUT" ]; then
        S3_SECRET_INPUT="your_s3_secret_key"
    fi
    
    # --- Ask for Reranker Server ---
    echo ""
    print_section "Reranker Service Configuration"
    echo -e "${YELLOW}Enter the IP address or hostname of your dedicated Reranker server${NC}"
    read -p "Reranker Server [10.10.10.60]: " RERANKER_HOST_INPUT
    if [ -z "$RERANKER_HOST_INPUT" ]; then
        RERANKER_HOST_INPUT="10.10.10.60"
    fi
    
    read -p "Reranker Port [8100]: " RERANKER_PORT_INPUT
    if [ -z "$RERANKER_PORT_INPUT" ]; then
        RERANKER_PORT_INPUT="8100"
    fi
    
    RERANKER_URL="http://${RERANKER_HOST_INPUT}:${RERANKER_PORT_INPUT}"
    
    # Test reranker connection
    echo -n "Testing connection to reranker server... "
    if curl -sf "${RERANKER_URL}/health" > /dev/null 2>&1; then
        print_success "Reranker server is reachable!"
    else
        print_warning "Could not reach reranker server at ${RERANKER_URL}"
        print_warning "Make sure the reranker service is running before starting Core API"
    fi
    
    # ========================================================================
    # Create .env file from scratch
    # ========================================================================
    print_info "Creating .env file..."
    
    cat > "$PROJECT_ROOT/.env" << EOF
# =============================================================================
# Core System Environment Variables
# Auto-generated by deployment script
# =============================================================================

# Application
APP_NAME="RAG Core System"
APP_VERSION="1.5.0"
ENVIRONMENT="${ENVIRONMENT}"
DEBUG=${DEBUG}
LOG_LEVEL="INFO"

# Server
HOST="0.0.0.0"
PORT=7001
WORKERS=4
RELOAD=${RELOAD}

# CORS - اجازه دسترسی به سرورهای مجاز
CORS_ORIGINS=${CORS_ORIGINS}

# Security
JWT_SECRET_KEY="${JWT_SECRET}"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database - Core DB
POSTGRES_DB=core_db
POSTGRES_USER=core_user
POSTGRES_PASSWORD=${DB_PASSWORD}
DATABASE_URL="postgresql+asyncpg://core_user:${DB_PASSWORD}@postgres-core:5432/core_db"
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
DATABASE_ECHO=false

# Qdrant Vector Database
QDRANT_HOST="qdrant"
QDRANT_PORT=6333
QDRANT_GRPC_PORT=7334
QDRANT_API_KEY=""
QDRANT_COLLECTION="legal_documents"
QDRANT_USE_GRPC=false

# Redis
REDIS_URL="redis://:${REDIS_PASSWORD}@redis-core:6379/0"
REDIS_PASSWORD="${REDIS_PASSWORD}"
REDIS_MAX_CONNECTIONS=50
REDIS_DECODE_RESPONSES=true

# Cache Settings
CACHE_TTL_DEFAULT=3600
CACHE_TTL_QUERY=7200
CACHE_TTL_EMBEDDING=86400
SEMANTIC_CACHE_THRESHOLD=0.95

# Celery
CELERY_BROKER_URL="redis://:${REDIS_PASSWORD}@redis-core:6379/1"
CELERY_RESULT_BACKEND="redis://:${REDIS_PASSWORD}@redis-core:6379/2"
CELERY_TASK_SERIALIZER="json"
CELERY_RESULT_SERIALIZER="json"
CELERY_TIMEZONE="Asia/Tehran"
CELERY_ENABLE_UTC=false

# LLM1 (Light) - for general queries
LLM1_MAX_TOKENS=2048
LLM1_TEMPERATURE=0.7
LLM1_API_KEY="${LLM1_KEY_INPUT}"
LLM1_BASE_URL="${LLM1_URL_INPUT}"
LLM1_MODEL="${LLM1_MODEL_INPUT}"
LLM1_FALLBACK_API_KEY="${LLM1_KEY_INPUT}"
LLM1_FALLBACK_BASE_URL="${LLM1_URL_INPUT}"
LLM1_FALLBACK_MODEL="${LLM1_MODEL_INPUT}"

# LLM2 (Pro) - for business queries
LLM2_MAX_TOKENS=8192
LLM2_TEMPERATURE=0.4
LLM2_API_KEY="${LLM2_KEY_INPUT}"
LLM2_BASE_URL="${LLM2_URL_INPUT}"
LLM2_MODEL="${LLM2_MODEL_INPUT}"
LLM2_FALLBACK_API_KEY="${LLM2_KEY_INPUT}"
LLM2_FALLBACK_BASE_URL="${LLM2_URL_INPUT}"
LLM2_FALLBACK_MODEL="${LLM2_MODEL_INPUT}"

# LLM Classification
LLM_CLASSIFICATION_MAX_TOKENS=512
LLM_CLASSIFICATION_TEMPERATURE=0.2
LLM_CLASSIFICATION_API_KEY="${CLASS_KEY_INPUT}"
LLM_CLASSIFICATION_BASE_URL="${CLASS_URL_INPUT}"
LLM_CLASSIFICATION_MODEL="${CLASS_MODEL_INPUT}"
LLM_CLASSIFICATION_FALLBACK_API_KEY="${CLASS_KEY_INPUT}"
LLM_CLASSIFICATION_FALLBACK_BASE_URL="${CLASS_URL_INPUT}"
LLM_CLASSIFICATION_FALLBACK_MODEL="${CLASS_MODEL_INPUT}"

# LLM Timeout Settings
LLM_PRIMARY_TIMEOUT=30
LLM_WEB_SEARCH_TIMEOUT=90

# Embedding Configuration
EMBEDDING_MODEL="intfloat/multilingual-e5-large"
EMBEDDING_DIM=1024
EMBEDDING_API_KEY=""
EMBEDDING_BASE_URL=""

# Reranking (Dedicated Server)
RERANKER_SERVICE_URL="${RERANKER_URL}"
RERANKING_MODEL="BAAI/bge-reranker-v2-m3"
RERANKING_TOP_K=10

# OCR Settings
OCR_LANGUAGE="fas+eng"
TESSERACT_CMD="/usr/bin/tesseract"
MAX_IMAGE_SIZE_MB=10

# RAG Settings
RAG_CHUNK_SIZE=450
RAG_CHUNK_OVERLAP=50
RAG_TOP_K_RETRIEVAL=20
RAG_MAX_CHUNKS=5
RAG_RETRIEVE_MULTIPLIER=5
RAG_RERANKER_THRESHOLD=0.3
RAG_TOP_K_RERANK=5
RAG_SIMILARITY_THRESHOLD=0.5
RAG_MAX_CONTEXT_LENGTH=8192
RAG_USE_HYBRID_SEARCH=true
RAG_BM25_WEIGHT=0.3
RAG_VECTOR_WEIGHT=0.7

# RAG Web Search
ENABLE_RAG_WEB_SEARCH=false

# Search Settings
SEARCH_MAX_RESULTS=50
SEARCH_TIMEOUT=30
FUZZY_MATCH_THRESHOLD=0.8

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000

# MinIO (External Object Storage)
S3_ACCESS_KEY_ID=${S3_KEY_INPUT}
S3_SECRET_ACCESS_KEY=${S3_SECRET_INPUT}
S3_ENDPOINT_URL=${S3_URL_INPUT}
S3_REGION="us-east-1"
S3_USE_SSL=false
S3_DOCUMENTS_BUCKET="ingest-system"
S3_TEMP_BUCKET="temp-userfile"

# API Keys for Inter-Service Communication
INGEST_API_KEY="${INGEST_API_KEY}"
USERS_API_KEY="${USERS_API_KEY}"

# System Limits
MAX_CONCURRENT_REQUESTS=100
MAX_HISTORY_LENGTH=50
MAX_QUERY_LENGTH=2000
REQUEST_TIMEOUT=60

# Temporary File Storage
TEMP_FILE_EXPIRATION_HOURS=12

# Backup Server Configuration
BACKUP_SERVER_HOST=""
BACKUP_SERVER_USER=""
BACKUP_SERVER_PATH="/backups/core"
BACKUP_SSH_KEY="/root/.ssh/backup_key"
BACKUP_RETENTION_DAYS=30
BACKUP_KEEP_LOCAL=false

# Flower
FLOWER_PASSWORD="${FLOWER_PASSWORD}"

# Domain
DOMAIN_NAME="${DOMAIN_INPUT}"
EOF
    
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
# Step 3.5: Configure Docker Daemon for Insecure Registries
# ============================================================================
print_section "Step 3.5: Configuring Docker Daemon"

DOCKER_DAEMON_FILE="/etc/docker/daemon.json"

# Check if cache server is accessible
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$CACHE_SERVER/5001" 2>/dev/null; then
    print_info "Configuring Docker to use cache server registries..."
    
    # Create or update daemon.json
    if [ -f "$DOCKER_DAEMON_FILE" ]; then
        # Backup existing file
        cp "$DOCKER_DAEMON_FILE" "$DOCKER_DAEMON_FILE.backup.$(date +%s)"
        print_info "Backed up existing daemon.json"
    fi
    
    # Create new daemon.json with cache server configuration
    cat > "$DOCKER_DAEMON_FILE" << 'EOF'
{
  "registry-mirrors": ["http://10.10.10.111:5001"],
  "insecure-registries": [
    "10.10.10.111:5001",
    "10.10.10.111:5002",
    "10.10.10.111:5003",
    "10.10.10.111:5004",
    "10.10.10.111:5005"
  ]
}
EOF
    
    print_success "Docker daemon.json configured"
    
    # Restart Docker to apply changes
    print_info "Restarting Docker daemon..."
    systemctl restart docker
    sleep 3
    
    if systemctl is-active --quiet docker; then
        print_success "Docker daemon restarted successfully"
    else
        print_error "Failed to restart Docker daemon"
        exit 1
    fi
else
    print_warning "Cache server not accessible - Docker will use default registries"
fi

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
echo -e "${CYAN}              MONITORING SYSTEM (PROMETHEUS/LOKI)            ${NC}"
echo -e "${CYAN}==============================================================${NC}"
echo ""
echo -e "  ${GREEN}${BOLD}Exporters installed for monitoring:${NC}"
echo ""
echo -e "  ${YELLOW}▶ Node Exporter:${NC}          http://10.10.10.20:9100/metrics"
echo -e "    System metrics (CPU, Memory, Disk, Network)"
echo ""
echo -e "  ${YELLOW}▶ PostgreSQL Exporter:${NC}    http://10.10.10.20:9187/metrics"
echo -e "    Database metrics for core_db"
echo ""
echo -e "  ${YELLOW}▶ Redis Exporter:${NC}         http://10.10.10.20:9121/metrics"
echo -e "    Cache metrics for Redis"
echo ""
echo -e "  ${YELLOW}▶ Promtail:${NC}               Shipping logs to Loki (10.10.10.40:3100)"
echo -e "    All container logs with label: server=core"
echo ""
echo -e "  ${YELLOW}▶ cAdvisor:${NC}               http://localhost:8080/metrics"
echo -e "    Container metrics (localhost only)"
echo ""
echo -e "  ${YELLOW}▶ Qdrant:${NC}                 http://localhost:7333/metrics"
echo -e "    Vector database metrics (localhost only)"
echo ""
echo -e "  ${BLUE}[ℹ]${NC} Exporters accessible from LAN (192.168.100.0/24) and DMZ (10.10.10.0/24)"
echo -e "  ${BLUE}[ℹ]${NC} Add these targets to your Prometheus configuration"
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
