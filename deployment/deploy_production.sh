#!/bin/bash

# Core System - Production Deployment Script
# برای محیط production

set -e

echo "========================================="
echo "Core System - Production Deployment"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root (recommended for production)
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Warning: Not running as root. Some operations may require sudo.${NC}"
fi

# Detect directories
# This script is in: /path/to/project/deployment/
# Project root is:   /path/to/project/
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}📁 Paths:${NC}"
echo "  Script: $SCRIPT_DIR"
echo "  Project Root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT" || {
    echo -e "${RED}Failed to change to project root: $PROJECT_ROOT${NC}"
    exit 1
}

# Production environment check
echo -e "${RED}WARNING: This is PRODUCTION deployment!${NC}"
read -p "Are you sure you want to continue? (y/N): " -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

# Get domain name
echo ""
echo -e "${YELLOW}Domain Configuration:${NC}"
read -p "Enter your domain name (e.g., api.example.com): " DOMAIN_NAME
if [ -z "$DOMAIN_NAME" ]; then
    echo -e "${RED}Domain name is required for production deployment!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Domain: $DOMAIN_NAME${NC}"

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Installing Docker Compose...${NC}"
    apt-get update && apt-get install -y docker-compose
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"

# Create necessary directories with proper permissions
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p /var/log/core
mkdir -p /var/lib/core/data/postgres
mkdir -p /var/lib/core/data/redis
mkdir -p /var/lib/core/data/qdrant
mkdir -p /var/lib/core/backups
chown -R 1000:1000 /var/lib/core
echo -e "${GREEN}✓ Directories created${NC}"

# Setup environment file
echo -e "${YELLOW}Setting up environment file...${NC}"
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/deployment/config/.env.example" "$PROJECT_ROOT/.env"
    
    # Generate secure passwords (hex for URL safety)
    SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    
    # Update .env with secure values
    sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/g" "$PROJECT_ROOT/.env"
    sed -i "s/your-jwt-secret-key-change-in-production/$JWT_SECRET/g" "$PROJECT_ROOT/.env"
    sed -i "s/core_pass/$DB_PASSWORD/g" "$PROJECT_ROOT/.env"
    sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$DB_PASSWORD#g" "$PROJECT_ROOT/.env"
    sed -i 's/REDIS_PASSWORD=""/REDIS_PASSWORD="'$REDIS_PASSWORD'"/g' "$PROJECT_ROOT/.env"
    
    # Update Redis URL with password
    sed -i "s#redis://redis-core:6379#redis://:$REDIS_PASSWORD@redis-core:6379#g" "$PROJECT_ROOT/.env"
    # Update Celery URLs with password
    sed -i "s#CELERY_BROKER_URL=.*#CELERY_BROKER_URL=\"redis://:$REDIS_PASSWORD@redis-core:6379/1\"#g" "$PROJECT_ROOT/.env"
    sed -i "s#CELERY_RESULT_BACKEND=.*#CELERY_RESULT_BACKEND=\"redis://:$REDIS_PASSWORD@redis-core:6379/2\"#g" "$PROJECT_ROOT/.env"
    
    # Set production environment
    sed -i 's/ENVIRONMENT="development"/ENVIRONMENT="production"/g' "$PROJECT_ROOT/.env"
    sed -i 's/DEBUG=true/DEBUG=false/g' "$PROJECT_ROOT/.env"
    sed -i 's/RELOAD=true/RELOAD=false/g' "$PROJECT_ROOT/.env"
    sed -i 's/LOG_LEVEL="INFO"/LOG_LEVEL="WARNING"/g' "$PROJECT_ROOT/.env"
    
    # Add domain to .env (remove duplicates first)
    sed -i '/^DOMAIN_NAME=/d' "$PROJECT_ROOT/.env"
    echo "DOMAIN_NAME=\"$DOMAIN_NAME\"" >> "$PROJECT_ROOT/.env"
    
    echo -e "${GREEN}✓ Created .env with secure defaults${NC}"
    echo -e "${GREEN}✓ Generated secure passwords:${NC}"
    echo "  - SECRET_KEY: $(echo $SECRET_KEY | cut -c1-16)..."
    echo "  - JWT_SECRET: $(echo $JWT_SECRET | cut -c1-16)..."
    echo "  - DB_PASSWORD: $(echo $DB_PASSWORD | cut -c1-8)..."
    echo "  - REDIS_PASSWORD: $(echo $REDIS_PASSWORD | cut -c1-8)..."
    echo ""
    echo -e "${YELLOW}⚠️  Save these passwords! They are stored in $PROJECT_ROOT/.env${NC}"
    echo -e "${YELLOW}Note: Add LLM API keys if needed (edit $PROJECT_ROOT/.env)${NC}"
    echo ""
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

# Build Docker images (if needed)
echo -e "${YELLOW}Building Docker images...${NC}"
if [ -f "$PROJECT_ROOT/deployment/docker/Dockerfile" ]; then
    docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" build --no-cache
else
    echo -e "${YELLOW}No custom Dockerfile found, using default images${NC}"
fi

# Start all services
echo -e "${YELLOW}Starting all services...${NC}"
docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 20

# Check services health
echo -e "${YELLOW}Checking services health...${NC}"
docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" ps

# Run database migrations (if alembic exists)
if [ -d "$PROJECT_ROOT/alembic" ]; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    docker-compose -f "$PROJECT_ROOT/deployment/docker/docker-compose.yml" exec -T core-api alembic upgrade head 2>/dev/null || \
        echo -e "${YELLOW}⚠️  Migrations skipped (service may not be ready or alembic not configured)${NC}"
else
    echo -e "${YELLOW}No alembic directory found, skipping migrations${NC}"
fi

# Setup Nginx (if not already configured)
if command_exists nginx; then
    echo -e "${YELLOW}Setting up Nginx reverse proxy...${NC}"
    
    cat > /etc/nginx/sites-available/core-api <<EOF
server {
    listen 80;
    server_name your-domain.com;  # Change this to your domain
    
    location / {
        proxy_pass http://localhost:7001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Increase max body size for file uploads
    client_max_body_size 50M;
}
EOF
    
    ln -sf /etc/nginx/sites-available/core-api /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    echo -e "${GREEN}✓ Nginx configured${NC}"
else
    echo -e "${YELLOW}Nginx not found. Please configure your reverse proxy manually.${NC}"
fi

# Setup systemd service for auto-restart
echo -e "${YELLOW}Setting up systemd service...${NC}"
cat > /etc/systemd/system/core-api.service <<EOF
[Unit]
Description=Core API System
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml up -d
ExecStop=/usr/bin/docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml down
ExecReload=/usr/bin/docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml restart

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable core-api.service
echo -e "${GREEN}✓ Systemd service configured${NC}"

# Setup log rotation
echo -e "${YELLOW}Setting up log rotation...${NC}"
cat > /etc/logrotate.d/core-api <<EOF
/var/log/core/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        docker-compose -f $(pwd)/deployment/docker/docker-compose.yml restart core-api
    endscript
}
EOF
echo -e "${GREEN}✓ Log rotation configured${NC}"

# Setup UFW Firewall
echo -e "${YELLOW}Setting up UFW Firewall...${NC}"
if command_exists ufw; then
    echo -e "${GREEN}✓ UFW is already installed${NC}"
else
    echo -e "${YELLOW}Installing UFW...${NC}"
    apt-get update
    apt-get install -y ufw
    echo -e "${GREEN}✓ UFW installed${NC}"
fi

# Configure UFW rules
echo -e "${YELLOW}Configuring firewall rules...${NC}"

# Reset UFW to default (optional - only for fresh setup)
if [ "$EUID" -eq 0 ]; then
    # Allow SSH first (important!)
    ufw allow 22/tcp comment 'SSH'
    echo -e "${GREEN}✓ Port 22 (SSH) - Allowed${NC}"
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp comment 'HTTP'
    echo -e "${GREEN}✓ Port 80 (HTTP) - Allowed${NC}"
    
    ufw allow 443/tcp comment 'HTTPS'
    echo -e "${GREEN}✓ Port 443 (HTTPS) - Allowed${NC}"
    
    # Allow Nginx Proxy Manager Admin UI
    ufw allow 81/tcp comment 'Nginx Proxy Manager'
    echo -e "${GREEN}✓ Port 81 (Nginx Proxy Manager) - Allowed${NC}"
    
    # Allow Core API port (if needed for direct access)
    # Note: In production with Nginx, this might not be needed externally
    read -p "Allow direct access to Core API on port 7001? (y/N): " allow_api
    if [[ $allow_api =~ ^[Yy]$ ]]; then
        ufw allow 7001/tcp comment 'Core API'
        echo -e "${GREEN}✓ Port 7001 (Core API) - Allowed${NC}"
    else
        echo -e "${YELLOW}⚠️  Port 7001 (Core API) - Blocked (access via Nginx only)${NC}"
    fi
    
    # Deny all other incoming by default
    ufw default deny incoming
    ufw default allow outgoing
    
    # Enable UFW
    echo -e "${YELLOW}Enabling UFW firewall...${NC}"
    echo "y" | ufw enable
    
    echo -e "${GREEN}✓ UFW Firewall configured and enabled${NC}"
    echo -e "${BLUE}Current firewall status:${NC}"
    ufw status numbered
else
    echo -e "${YELLOW}⚠️  Skipping UFW setup (requires root access)${NC}"
    echo -e "${YELLOW}Please run manually:${NC}"
    echo "  sudo ufw allow 22/tcp"
    echo "  sudo ufw allow 80/tcp"
    echo "  sudo ufw allow 443/tcp"
    echo "  sudo ufw allow 81/tcp"
    echo "  sudo ufw enable"
fi

# Setup monitoring
echo -e "${YELLOW}Setting up monitoring...${NC}"
echo -e "${GREEN}Prometheus metrics available at: http://localhost:7001/metrics${NC}"
echo -e "${GREEN}Flower (Celery monitoring) available at: http://localhost:7555${NC}"

# Final checks
echo -e "${YELLOW}Running final health checks...${NC}"
sleep 5

# Test services
echo -e "${YELLOW}Testing services...${NC}"

# Test API endpoint (local)
if curl -f http://localhost:7001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is responding (localhost)${NC}"
else
    echo -e "${YELLOW}⚠️  API is not responding yet. Check logs: docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml logs core-api${NC}"
fi

# Test Qdrant
if curl -f http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Qdrant is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Qdrant is not responding yet. Check logs: docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml logs qdrant${NC}"
fi

# Test Nginx Proxy Manager
if curl -f http://localhost:81 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Nginx Proxy Manager is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Nginx Proxy Manager is not responding yet${NC}"
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Production Deployment Completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${BLUE}📋 Important Information:${NC}"
echo ""
echo -e "${YELLOW}🌐 Domain Configuration:${NC}"
read -p "Enter your domain name: " DOMAIN_NAME
echo "DOMAIN_NAME=$DOMAIN_NAME" >> $PROJECT_ROOT/.env
echo "  Domain: $DOMAIN_NAME"
echo ""
echo -e "${YELLOW}🔐 Generated Passwords (saved in $PROJECT_ROOT/.env):${NC}"
echo "  - JWT Secret: ✓"
echo "  - Database Password: ✓"
echo "  - Redis Password: ✓"
echo ""
echo -e "${YELLOW}🔧 Nginx Proxy Manager Setup:${NC}"
echo "  1. Access Admin UI: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP'):81"
echo "     Default credentials:"
echo "       Email: admin@example.com"
echo "       Password: changeme"
echo ""
echo "  2. After login, change password immediately!"
echo ""
echo "  3. Add Proxy Host:"
echo "     - Domain Names: $DOMAIN_NAME"
echo "     - Scheme: http"
echo "     - Forward Hostname/IP: core-api"
echo "     - Forward Port: 7001"
echo "     - Enable: Websockets Support"
echo "     - Custom Nginx Config (Advanced tab):"
echo "         proxy_set_header Host \$host;"
echo "         proxy_set_header X-Real-IP \$remote_addr;"
echo "         proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
echo "         proxy_set_header X-Forwarded-Proto \$scheme;"
echo ""
echo "  4. Request SSL Certificate:"
echo "     - SSL tab → Request new certificate"
echo "     - Email: your-email@example.com"
echo "     - Enable: Force SSL, HTTP/2 Support, HSTS"
echo ""
echo -e "${YELLOW}🔥 Firewall Status:${NC}"
if [ "$EUID" -eq 0 ]; then
    ufw status numbered | head -10
else
    echo "  ✅ Ports 22, 80, 443 configured"
fi
echo ""
echo -e "${YELLOW}📊 Service URLs:${NC}"
echo "  - API (local): http://localhost:7001"
echo "  - API (domain): https://$DOMAIN_NAME"
echo "  - API Docs: https://$DOMAIN_NAME/docs"
echo "  - Flower (Celery): http://localhost:5555"
echo "  - Nginx Proxy Manager: http://$(curl -s ifconfig.me):81"
echo ""
echo -e "${YELLOW}📦 Next Steps:${NC}"
echo "  1. ✅ Configure Nginx Proxy Manager (see above)"
echo "  2. ✅ Point DNS A record: $DOMAIN_NAME → $(curl -s ifconfig.me)"
echo "  3. ✅ Request SSL certificate via Nginx Proxy Manager"
echo "  4. Setup backup cron job:"
echo "     crontab -e"
echo "     0 2 * * * $PROJECT_ROOT/deployment/backup_manager.sh --auto-backup"
echo "  5. Monitor logs:"
echo "     docker-compose -f $PROJECT_ROOT/deployment/docker/docker-compose.yml logs -f"
echo ""
echo -e "${YELLOW}🧪 Test Your API:${NC}"
echo "  curl https://$DOMAIN_NAME/health"
echo "  curl https://$DOMAIN_NAME/docs"
echo ""
echo -e "${GREEN}✨ Deployment successful! Your API is ready.${NC}"
