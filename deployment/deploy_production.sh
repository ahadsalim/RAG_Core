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

# Check if running from correct directory
if [ ! -f "deployment/deploy_production.sh" ]; then
    echo -e "${RED}Error: Please run this script from the core project root directory${NC}"
    echo "Usage: ./deployment/deploy_production.sh"
    exit 1
fi

# Production environment check
echo -e "${RED}WARNING: This is PRODUCTION deployment!${NC}"
read -p "Are you sure you want to continue? (yes/no) " -r
if [[ ! $REPLY == "yes" ]]; then
    echo "Deployment cancelled."
    exit 1
fi

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
echo -e "${YELLOW}Setting up production environment...${NC}"
if [ ! -f ".env.production" ]; then
    cp deployment/config/.env.example .env.production
    
    # Generate secure passwords
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    REDIS_PASSWORD=$(openssl rand -hex 16)
    
    # Update .env.production with secure values
    sed -i "s/your-secret-jwt-key-change-this-in-production/$JWT_SECRET/" .env.production
    sed -i "s/core_pass/$DB_PASSWORD/" .env.production
    sed -i "s/REDIS_PASSWORD=/REDIS_PASSWORD=$REDIS_PASSWORD/" .env.production
    
    echo -e "${GREEN}✓ Created .env.production with secure defaults${NC}"
    echo -e "${YELLOW}Please edit .env.production to add your API keys and final configurations${NC}"
    echo -e "${YELLOW}Especially: OPENAI_API_KEY, QDRANT_API_KEY, etc.${NC}"
    read -p "Press enter to continue after editing .env.production file..."
else
    echo -e "${GREEN}✓ .env.production file already exists${NC}"
fi

# Copy environment file to .env for Docker
cp .env.production .env

# Build Docker images
echo -e "${YELLOW}Building Docker images...${NC}"
cd deployment/docker
docker-compose build --no-cache
cd ../..

# Start all services
echo -e "${YELLOW}Starting all services...${NC}"
cd deployment/docker
docker-compose up -d
cd ../..

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 20

# Check services health
docker-compose -f deployment/docker/docker-compose.yml ps

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose -f deployment/docker/docker-compose.yml exec core-api alembic upgrade head
echo -e "${GREEN}✓ Migrations completed${NC}"

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
WorkingDirectory=$(pwd)/deployment/docker
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
ExecReload=/usr/bin/docker-compose restart

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

# Setup monitoring
echo -e "${YELLOW}Setting up monitoring...${NC}"
echo -e "${GREEN}Prometheus metrics available at: http://localhost:7001/metrics${NC}"
echo -e "${GREEN}Flower (Celery monitoring) available at: http://localhost:7555${NC}"

# Final checks
echo -e "${YELLOW}Running final health checks...${NC}"
sleep 5

# Test API endpoint
if curl -f http://localhost:7001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is responding${NC}"
else
    echo -e "${RED}✗ API is not responding. Check logs: docker-compose logs core-api${NC}"
fi

# Test Qdrant
if curl -f http://localhost:7333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Qdrant is responding${NC}"
else
    echo -e "${RED}✗ Qdrant is not responding. Check logs: docker-compose logs qdrant${NC}"
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Production deployment completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}Important next steps:${NC}"
echo "1. Configure your domain in Nginx: /etc/nginx/sites-available/core-api"
echo "2. Setup SSL certificate with Let's Encrypt:"
echo "   certbot --nginx -d your-domain.com"
echo "3. Configure firewall rules"
echo "4. Setup backup cron job: crontab -e"
echo "   0 2 * * * /path/to/core/deployment/backup.sh"
echo "5. Monitor logs: docker-compose -f deployment/docker/docker-compose.yml logs -f"
echo ""
echo -e "${GREEN}API Documentation: http://your-domain.com/docs${NC}"
echo -e "${GREEN}Admin Panel: http://your-domain.com/api/v1/admin${NC}"
