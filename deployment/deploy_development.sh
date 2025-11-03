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

# Check if running from correct directory
if [ ! -f "deployment/deploy_development.sh" ]; then
    echo -e "${RED}Error: Please run this script from the core project root directory${NC}"
    echo "Usage: ./deployment/deploy_development.sh"
    exit 1
fi

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
mkdir -p logs
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p data/qdrant
echo -e "${GREEN}✓ Directories created${NC}"

# Setup environment file
echo -e "${YELLOW}Setting up environment...${NC}"
if [ ! -f ".env" ]; then
    cp deployment/config/.env.example .env
    
    # Generate secure random values
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    REDIS_PASSWORD=$(openssl rand -hex 16)
    
    # Update .env with secure values
    sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/g" .env
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" .env
    sed -i "s/core_pass/$DB_PASSWORD/g" .env
    sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' .env
    
    echo -e "${GREEN}✓ Created .env file with secure defaults${NC}"
    echo -e "${GREEN}✓ Generated secure passwords (JWT, DB, Redis)${NC}"
    echo -e "${YELLOW}Note: Add LLM API keys if needed (edit .env file)${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Setup Python virtual environment
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r deployment/requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Start Docker services
echo -e "${YELLOW}Starting Docker services...${NC}"
cd deployment/docker
docker-compose up -d postgres-core redis-core qdrant
cd ../..

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check services health
docker-compose -f deployment/docker/docker-compose.yml ps

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python scripts/init_db.py
echo -e "${GREEN}✓ Database initialized${NC}"

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
alembic upgrade head
echo -e "${GREEN}✓ Migrations completed${NC}"

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
