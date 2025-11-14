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

# Detect directories
# This script is in: /path/to/project/deployment/
# Project root is:   /path/to/project/
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check for required files
check_prerequisites() {
    local missing_files=()
    
    if [ ! -f "$SCRIPT_DIR/deploy_development.sh" ]; then
        missing_files+=("deploy_development.sh")
    fi
    
    if [ ! -f "$SCRIPT_DIR/deploy_production.sh" ]; then
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
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_warning ".env file not found!"
        print_info "Creating .env from template..."
        
        # Prefer project root .env.example if it exists, otherwise fall back to deployment/config/.env.example
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            TEMPLATE_ENV="$PROJECT_ROOT/.env.example"
        elif [ -f "$SCRIPT_DIR/config/.env.example" ]; then
            TEMPLATE_ENV="$SCRIPT_DIR/config/.env.example"
        else
            TEMPLATE_ENV=""
        fi

        if [ -n "$TEMPLATE_ENV" ]; then
            # Copy template
            cp "$TEMPLATE_ENV" "$PROJECT_ROOT/.env"
            
            # Generate secure random values (hex so that there are no URL-breaking characters like '/')
            SECRET_KEY=$(openssl rand -hex 32)
            JWT_SECRET=$(openssl rand -hex 32)
            DB_PASSWORD=$(openssl rand -hex 16)
            REDIS_PASSWORD=$(openssl rand -hex 16)
            
            # Update .env with secure values
            sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/g" "$PROJECT_ROOT/.env"
            sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
            sed -i "s/core_pass/$DB_PASSWORD/g" "$PROJECT_ROOT/.env"
            sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' "$PROJECT_ROOT/.env"
            
            # Ask for domain name (optional now, required for production)
            read -p "Enter domain name for Core (e.g., core.example.com) [leave empty for local dev]: " DOMAIN_INPUT
            if [ -n "$DOMAIN_INPUT" ]; then
                # Always ensure exactly one DOMAIN_NAME line with correct value
                if grep -q '^DOMAIN_NAME=' "$PROJECT_ROOT/.env"; then
                    sed -i "s#^DOMAIN_NAME=.*#DOMAIN_NAME=\"$DOMAIN_INPUT\"#g" "$PROJECT_ROOT/.env"
                else
                    echo "DOMAIN_NAME=\"$DOMAIN_INPUT\"" >> "$PROJECT_ROOT/.env"
                fi
                print_success "DOMAIN_NAME set to $DOMAIN_INPUT"
            else
                print_info "DOMAIN_NAME left empty (OK for development)."
            fi

            print_success ".env file created with secure defaults"
            print_info "Generated secure passwords:"
            echo "  ✓ JWT Secret Key"
            echo "  ✓ Database Password"
            echo "  ✓ Redis Password"
            echo ""
            print_warning "⚠️  If you need LLM API keys (OpenAI, Groq, etc.), edit .env:"
            echo "  nano $PROJECT_ROOT/.env"
            echo "  Then set: LLM_API_KEY=your-key"
            echo ""
        else
            print_error "Template file not found!"
            exit 1
        fi
    else
        print_success ".env file found"
        # If DOMAIN_NAME is empty, offer to set/update it (ensure it is not duplicated)
        CURRENT_DOMAIN=$(grep '^DOMAIN_NAME=' "$PROJECT_ROOT/.env" | sed 's/^DOMAIN_NAME="\(.*\)"/\1/')
        if [ -z "$CURRENT_DOMAIN" ]; then
            print_info "DOMAIN_NAME is empty in existing .env (OK for development; required for production)."
        else
            print_info "Using DOMAIN_NAME from existing .env: $CURRENT_DOMAIN"
        fi
    fi
}

print_header "🚀 Core RAG System Quick Start"

# Check prerequisites
check_prerequisites

# Check .env file
check_env_file
 
echo ""
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
echo "  • Generate and apply secure passwords/keys (one-time display)"
echo ""
print_error "This requires root access and will modify system configuration"
echo ""
read -p "Are you absolutely sure? (y/N): " confirm
if [[ $confirm =~ ^[Yy]$ ]]; then
    # --- One-time secure credential generation for PRODUCTION ---
    PROD_ENV_PATH="$PROJECT_ROOT/.env"
    PROD_ENV_TEMPLATE="$SCRIPT_DIR/config/.env.example"

    print_info "Preparing production .env and generating strong credentials..."

    if [ ! -f "$PROD_ENV_PATH" ]; then
        cp "$PROD_ENV_TEMPLATE" "$PROD_ENV_PATH"
        print_info "Created .env from template"
    fi

    # Generate secure values
    SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    # Use hex for passwords used inside URLs to avoid characters like '/' that may break URL parsing
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    INGEST_API_KEY=$(openssl rand -base64 48 | tr -d '\n')
    USERS_API_KEY=$(openssl rand -base64 48 | tr -d '\n')

    # Ensure ENV is production and hardened
    sed -i 's/^ENVIRONMENT=.*/ENVIRONMENT="production"/g' "$PROD_ENV_PATH"
    sed -i 's/^DEBUG=.*/DEBUG=false/g' "$PROD_ENV_PATH"
    sed -i 's/^RELOAD=.*/RELOAD=false/g' "$PROD_ENV_PATH"
    sed -i 's/^LOG_LEVEL=.*/LOG_LEVEL="WARNING"/g' "$PROD_ENV_PATH"

    # Apply secrets/keys
    # SECRET_KEY / JWT_SECRET_KEY
    if grep -q '^SECRET_KEY=' "$PROD_ENV_PATH"; then
        sed -i "s#^SECRET_KEY=.*#SECRET_KEY=\"$SECRET_KEY\"#g" "$PROD_ENV_PATH"
    else
        echo "SECRET_KEY=\"$SECRET_KEY\"" >> "$PROD_ENV_PATH"
    fi
    if grep -q '^JWT_SECRET_KEY=' "$PROD_ENV_PATH"; then
        sed -i "s#^JWT_SECRET_KEY=.*#JWT_SECRET_KEY=\"$JWT_SECRET\"#g" "$PROD_ENV_PATH"
    else
        echo "JWT_SECRET_KEY=\"$JWT_SECRET\"" >> "$PROD_ENV_PATH"
    fi

    # Redis password and URL (inject password into URL if host present)
    if grep -q '^REDIS_PASSWORD=' "$PROD_ENV_PATH"; then
        sed -i "s#^REDIS_PASSWORD=.*#REDIS_PASSWORD=\"$REDIS_PASSWORD\"#g" "$PROD_ENV_PATH"
    else
        echo "REDIS_PASSWORD=\"$REDIS_PASSWORD\"" >> "$PROD_ENV_PATH"
    fi
    if grep -q '^REDIS_URL=' "$PROD_ENV_PATH"; then
        # Transform redis://host:port/db -> redis://:pass@host:port/db
        OLD_REDIS_URL=$(grep '^REDIS_URL=' "$PROD_ENV_PATH" | sed 's/^REDIS_URL=\"\(.*\)\"/\1/')
        if echo "$OLD_REDIS_URL" | grep -q '^redis://'; then
            URL_NO_SCHEME=${OLD_REDIS_URL#redis://}
            if echo "$URL_NO_SCHEME" | grep -q '@'; then
                # replace existing password
                HOSTPART=${URL_NO_SCHEME#*@}
                NEW_REDIS_URL="redis://:$REDIS_PASSWORD@$HOSTPART"
            else
                NEW_REDIS_URL="redis://:$REDIS_PASSWORD@$URL_NO_SCHEME"
            fi
            sed -i "s#^REDIS_URL=\".*\"#REDIS_URL=\"$NEW_REDIS_URL\"#g" "$PROD_ENV_PATH"
        fi
    fi

    # Ensure Celery broker/backend URLs use the new Redis password and are URL-safe
    if grep -q '^CELERY_BROKER_URL=' "$PROD_ENV_PATH"; then
        sed -i "s#^CELERY_BROKER_URL=\".*\"#CELERY_BROKER_URL=\"redis://:$REDIS_PASSWORD@redis-core:6379/1\"#g" "$PROD_ENV_PATH"
    else
        echo "CELERY_BROKER_URL=\"redis://:$REDIS_PASSWORD@redis-core:6379/1\"" >> "$PROD_ENV_PATH"
    fi

    if grep -q '^CELERY_RESULT_BACKEND=' "$PROD_ENV_PATH"; then
        sed -i "s#^CELERY_RESULT_BACKEND=\".*\"#CELERY_RESULT_BACKEND=\"redis://:$REDIS_PASSWORD@redis-core:6379/2\"#g" "$PROD_ENV_PATH"
    else
        echo "CELERY_RESULT_BACKEND=\"redis://:$REDIS_PASSWORD@redis-core:6379/2\"" >> "$PROD_ENV_PATH"
    fi

    # Database URL password rotation (only for core_user in template form)
    if grep -q '^DATABASE_URL=' "$PROD_ENV_PATH"; then
        OLD_DB_URL=$(grep '^DATABASE_URL=' "$PROD_ENV_PATH" | sed 's/^DATABASE_URL=\"\(.*\)\"/\1/')
        # Replace password between user:pass@
        if echo "$OLD_DB_URL" | grep -q 'core_user:'; then
            NEW_DB_URL=$(echo "$OLD_DB_URL" | sed -E "s#(core_user:)[^@]*@#\1$DB_PASSWORD@#")
            sed -i "s#^DATABASE_URL=\".*\"#DATABASE_URL=\"$NEW_DB_URL\"#g" "$PROD_ENV_PATH"
        fi
    fi

    # Inter-service API keys
    if grep -q '^INGEST_API_KEY=' "$PROD_ENV_PATH"; then
        sed -i "s#^INGEST_API_KEY=.*#INGEST_API_KEY=\"$INGEST_API_KEY\"#g" "$PROD_ENV_PATH"
    else
        echo "INGEST_API_KEY=\"$INGEST_API_KEY\"" >> "$PROD_ENV_PATH"
    fi
    if grep -q '^USERS_API_KEY=' "$PROD_ENV_PATH"; then
        sed -i "s#^USERS_API_KEY=.*#USERS_API_KEY=\"$USERS_API_KEY\"#g" "$PROD_ENV_PATH"
    else
        echo "USERS_API_KEY=\"$USERS_API_KEY\"" >> "$PROD_ENV_PATH"
    fi

    print_success "Production credentials generated and applied to .env"

    # Proceed with production deployment
    if chmod +x "$SCRIPT_DIR/deploy_production.sh" && sudo "$SCRIPT_DIR/deploy_production.sh"; then
        print_success "Production environment deployed successfully!"
        echo ""
        print_header "🎉 Production System Ready!"
        echo ""
        echo "📍 Important Information: (displayed ONCE)"
        echo "  🔐 Secrets (store them securely):"
        echo "    - SECRET_KEY: ${SECRET_KEY}"
        echo "    - JWT_SECRET_KEY: ${JWT_SECRET}"
        echo "    - DATABASE_PASSWORD (core_user): ${DB_PASSWORD}"
        echo "    - REDIS_PASSWORD: ${REDIS_PASSWORD}"
        echo "    - INGEST_API_KEY: ${INGEST_API_KEY}"
        echo "    - USERS_API_KEY: ${USERS_API_KEY}"
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
    print_error "Deployment cancelled"
    exit 0
fi

echo ""
print_success "Deployment completed successfully!"
echo ""
print_header "📚 Useful Resources"
echo ""
echo "🛠️  Management Tools:"
[ -f "$SCRIPT_DIR/backup_manager.sh" ] && echo "  💾 Backup Manager: $SCRIPT_DIR/backup_manager.sh"
echo "  📊 Monitor: docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml ps"
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
