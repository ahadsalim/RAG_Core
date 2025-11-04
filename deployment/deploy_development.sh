#!/bin/bash

# Core System - Development Deployment Script
# برای محیط توسعه

set -e

echo "========================================="
echo "Core System - Development Deployment"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect directories
# This script is in: /path/to/project/deployment/
# Project root is:   /path/to/project/
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 Paths:"
echo "  Script: $SCRIPT_DIR"
echo "  Project Root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT" || {
    echo -e "${RED}Failed to change to project root: $PROJECT_ROOT${NC}"
    exit 1
}

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

if ! command_exists python3; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.11+${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/data/postgres"
mkdir -p "$PROJECT_ROOT/data/redis"
mkdir -p "$PROJECT_ROOT/data/qdrant"
echo -e "${GREEN}✓ Directories created${NC}"

# Setup environment file
echo -e "${YELLOW}Setting up environment...${NC}"
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/deployment/config/.env.example" "$PROJECT_ROOT/.env"
    
    # Generate secure random values
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    REDIS_PASSWORD=$(openssl rand -hex 16)
    
    # Update .env with secure values
    sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/g" "$PROJECT_ROOT/.env"
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
    sed -i "s/core_pass/$DB_PASSWORD/g" "$PROJECT_ROOT/.env"
    sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' "$PROJECT_ROOT/.env"
    
    echo -e "${GREEN}✓ Created .env file with secure defaults${NC}"
    echo -e "${GREEN}✓ Generated secure passwords (JWT, DB, Redis)${NC}"
    echo -e "${YELLOW}Note: Add LLM API keys if needed (edit $PROJECT_ROOT/.env)${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Create symlink for docker-compose
echo -e "${YELLOW}Creating symlink for docker-compose...${NC}"
if [ -L "$PROJECT_ROOT/deployment/docker/.env" ]; then
    rm "$PROJECT_ROOT/deployment/docker/.env"
fi
ln -sf "$PROJECT_ROOT/.env" "$PROJECT_ROOT/deployment/docker/.env"
echo -e "${GREEN}✓ Symlink created: deployment/docker/.env -> ../../.env${NC}"

# Setup Python virtual environment
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    python3 -m venv "$PROJECT_ROOT/venv"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment and install dependencies
source "$PROJECT_ROOT/venv/bin/activate"
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/deployment/requirements.txt"
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Start Docker services
echo -e "${YELLOW}Starting Docker services...${NC}"
docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" up -d postgres-core redis-core qdrant

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check services health
echo -e "${YELLOW}Checking services health...${NC}"
docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" ps

# Initialize database (if script exists)
if [ -f "$PROJECT_ROOT/scripts/init_db.py" ]; then
    echo -e "${YELLOW}Initializing database...${NC}"
    python "$PROJECT_ROOT/scripts/init_db.py" || echo -e "${YELLOW}⚠️  Database may already be initialized${NC}"
else
    echo -e "${YELLOW}No init_db.py found, skipping database initialization${NC}"
fi

# Run migrations (if alembic exists)
if [ -d "$PROJECT_ROOT/alembic" ]; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    cd "$PROJECT_ROOT" && alembic upgrade head || echo -e "${YELLOW}⚠️  Migrations may have failed${NC}"
else
    echo -e "${YELLOW}No alembic directory found, skipping migrations${NC}"
fi

# Start the application
echo -e "${YELLOW}Starting Core API server...${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Core system is ready!${NC}"
echo -e "${GREEN}API Documentation: http://localhost:7001/docs${NC}"
echo -e "${GREEN}Health Check: http://localhost:7001/health${NC}"
echo -e "${GREEN}=========================================${NC}"

# Option to run with uvicorn
read -p "Do you want to start the API server now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting API server...${NC}"
    uvicorn app.main:app --reload --host 0.0.0.0 --port 7001
else
    echo -e "${YELLOW}To start the API server later, run:${NC}"
    echo "source venv/bin/activate"
    echo "uvicorn app.main:app --reload --host 0.0.0.0 --port 7001"
fi
