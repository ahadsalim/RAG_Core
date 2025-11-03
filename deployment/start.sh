#!/bin/bash

# Quick Start Script for Core RAG System

set -e

# Colors for output
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

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check for required files
check_prerequisites() {
    local missing_files=()
    
    if [ ! -f "deploy_development.sh" ]; then
        missing_files+=("deploy_development.sh")
    fi
    
    if [ ! -f "deploy_production.sh" ]; then
        missing_files+=("deploy_production.sh")
    fi
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        print_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
}

# Check and create .env file with secure defaults
check_env_file() {
    if [ ! -f "../.env" ]; then
        print_warning ".env file not found!"
        print_info "Creating .env from template..."
        
        if [ -f "config/.env.example" ]; then
            # Copy template
            cp config/.env.example ../.env
            
            # Generate secure random values
            SECRET_KEY=$(openssl rand -hex 32)
            JWT_SECRET=$(openssl rand -hex 32)
            DB_PASSWORD=$(openssl rand -hex 16)
            REDIS_PASSWORD=$(openssl rand -hex 16)
            
            # Update .env with secure values
            sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/g" ../.env
            sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" ../.env
            sed -i "s/core_pass/$DB_PASSWORD/g" ../.env
            sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' ../.env
            
            print_success ".env file created with secure defaults"
            print_info "Generated secure passwords:"
            echo "  ✓ JWT Secret Key"
            echo "  ✓ Database Password"
            echo "  ✓ Redis Password"
            echo ""
            print_warning "⚠️  If you need LLM API keys (OpenAI, Groq, etc.), edit .env:"
            echo "  nano ../.env"
            echo "  Then set: LLM_API_KEY=your-key"
            echo ""
        else
            print_error "Template file not found!"
            exit 1
        fi
    else
        print_success ".env file found"
    fi
}

print_header "🚀 Core RAG System Quick Start"

# Check prerequisites
check_prerequisites

# Check .env file
check_env_file

echo ""
print_info "Select deployment environment:"
echo ""
echo "1️⃣  Development (local development with hot-reload)"
echo "   - Runs on localhost"
echo "   - Debug mode enabled"
echo "   - Suitable for testing and development"
echo ""
echo "2️⃣  Production (production server with full security)"
echo "   - Optimized for production"
echo "   - Security hardening"
echo "   - Auto-restart and monitoring"
echo ""
read -p "Choose (1-2): " choice

case $choice in
    1)
        print_info "Setting up Development environment..."
        echo ""
        print_warning "Development mode will:"
        echo "  • Install Python dependencies"
        echo "  • Start Docker services (PostgreSQL, Redis, Qdrant)"
        echo "  • Initialize database"
        echo "  • Run migrations"
        echo "  • Start API server on http://localhost:7001"
        echo ""
        read -p "Continue? (Y/n): " confirm
        if [[ ! $confirm =~ ^[Nn]$ ]]; then
            if chmod +x deploy_development.sh && ./deploy_development.sh; then
                print_success "Development environment deployed successfully!"
                echo ""
                print_header "🎉 System Ready!"
                echo ""
                echo "📍 Available Services:"
                echo "  🌐 Core API: http://localhost:7001"
                echo "  📚 API Docs: http://localhost:7001/docs"
                echo "  🧪 Test UI: file://${PWD}/../users/index.html"
                echo "  📊 Qdrant: http://localhost:7333/dashboard"
                echo "  🌺 Flower: http://localhost:7555"
                echo ""
            else
                print_error "Error deploying Development environment"
                exit 1
            fi
        else
            echo "Operation cancelled"
            exit 0
        fi
        ;;
    2)
        print_info "Setting up Production environment..."
        echo ""
        print_warning "⚠️  WARNING: This is PRODUCTION deployment!"
        echo ""
        echo "This operation will:"
        echo "  • Install system dependencies"
        echo "  • Configure Docker services"
        echo "  • Setup Nginx reverse proxy"
        echo "  • Configure systemd service"
        echo "  • Setup log rotation"
        echo "  • Generate secure passwords"
        echo ""
        print_error "This requires root access and will modify system configuration"
        echo ""
        read -p "Are you absolutely sure? (type 'yes' to continue): " confirm
        if [[ $confirm == "yes" ]]; then
            if chmod +x deploy_production.sh && sudo ./deploy_production.sh; then
                print_success "Production environment deployed successfully!"
                echo ""
                print_header "🎉 Production System Ready!"
                echo ""
                echo "📍 Important Information:"
                echo "  🔐 Secure passwords generated and stored"
                echo "  🌐 Configure your domain in Nginx"
                echo "  🔒 Setup SSL with: certbot --nginx"
                echo "  📊 Monitor: systemctl status core-api"
                echo "  📝 Logs: docker-compose logs -f"
                echo ""
            else
                print_error "Error deploying Production environment"
                exit 1
            fi
        else
            print_error "Deployment cancelled (you must type 'yes' to continue)"
            exit 0
        fi
        ;;
    *)
        print_error "Invalid selection"
        exit 1
        ;;
esac

echo ""
print_success "Deployment completed successfully!"
echo ""
print_header "📚 Useful Resources"
echo ""
echo "🛠️  Management Tools:"
[ -f "backup_manager.sh" ] && echo "  💾 Backup Manager: ./backup_manager.sh"
echo "  📊 Monitor: docker-compose -f docker/docker-compose.yml ps"
echo ""
echo "📖 Documentation:"
echo "  📄 Quick Start: ../QUICK_START.md"
echo "  🔑 API Keys Setup: ../document/API_KEYS_SETUP.md"
echo "  🔗 Ingest Integration: ../document/INGEST_INTEGRATION_GUIDE.md"
echo ""
echo "🎯 Next Steps:"
echo "  1. Test API: curl http://localhost:7001/health"
echo "  2. Open test UI in browser"
echo "  3. Configure your OpenAI API key if not done"
echo "  4. Review system logs"
echo "  5. Setup automated backups"
echo ""
print_info "For help: ./backup_manager.sh or check documentation"
