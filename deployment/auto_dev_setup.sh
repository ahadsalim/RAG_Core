#!/bin/bash

# Auto Development Setup for Core System
# این اسکریپت بدون نیاز به ورودی کاربر، محیط development را راه‌اندازی می‌کند

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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "🚀 Core RAG System - Auto Development Setup"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found! Creating from template..."
    
    if [ -f "deployment/config/.env.example" ]; then
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
        
        print_success ".env file created with secure defaults"
        print_success "Generated secure passwords (JWT, DB, Redis)"
        print_warning "⚠️  Add LLM API keys if needed:"
        echo "  - LLM_API_KEY=hf_xxxxx (برای Llama/Groq)"
        echo "  - LLM_API_KEY=sk-xxxxx (برای OpenAI)"
    else
        print_error "Template file not found!"
        exit 1
    fi
fi

print_info "Starting Development environment..."

# Stop any running containers
print_info "Stopping any running containers..."
docker-compose -f docker/docker-compose.yml down 2>/dev/null || true

# Start Docker services
print_info "Starting Docker services..."
docker-compose -f docker/docker-compose.yml up -d postgres-core redis-core qdrant

# Wait for services
print_info "Waiting for services to be ready..."
sleep 10

# Check PostgreSQL
print_info "Checking PostgreSQL..."
until docker exec postgres-core pg_isready -U core_user -d core_db > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
print_success "PostgreSQL is ready"

# Check Redis
print_info "Checking Redis..."
until docker exec redis-core redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
print_success "Redis is ready"

# Check Qdrant
print_info "Checking Qdrant..."
until curl -s http://localhost:7333/health > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
print_success "Qdrant is ready"

# Initialize database
print_info "Initializing database..."
cd ..
python scripts/init_db.py || print_warning "Database may already be initialized"
cd deployment

# Check if Python venv exists
if [ ! -d "../venv" ]; then
    print_info "Creating Python virtual environment..."
    cd ..
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r deployment/requirements.txt
    cd deployment
else
    print_info "Virtual environment exists"
fi

print_success "Setup completed successfully!"
echo ""
print_header "🎉 System Ready!"
echo ""
echo "📍 Services:"
echo "  🌐 Core API: http://localhost:7001"
echo "  📚 API Docs: http://localhost:7001/docs"
echo "  📊 Qdrant: http://localhost:7333/dashboard"
echo "  💾 PostgreSQL: localhost:7433"
echo "  📦 Redis: localhost:7379"
echo ""
echo "🚀 To start the API server:"
echo "  cd /home/ahad/project/core"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload"
echo ""
echo "🧪 Test UI:"
echo "  firefox /home/ahad/project/users/index.html"
echo ""
print_warning "⚠️  Remember to configure your API keys in .env:"
echo "  - HUGGINGFACE_API_KEY for Llama-3.1"
echo "  - ACTIVE_LLM_PROVIDER=huggingface"
echo ""
print_info "راهنمای کامل Llama: document/HUGGINGFACE_LLAMA_SETUP.md"
