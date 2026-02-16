#!/bin/bash
# اسکریپت خودکار برای تست تمام ترکیبات LLM
# 20 سوال × 8 تنظیمات = 160 تست

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="/srv/.env"
BACKUP_ENV="/tmp/.env.backup"
DOCKER_COMPOSE_DIR="/srv/deployment/docker"

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "================================================================================"
echo "🔬 تست جامع مقایسه‌ای LLM ها - 160 تست"
echo "================================================================================"
echo ""
echo "⚠️  این اسکریپت .env را تغییر داده و service را چندین بار restart می‌کند"
echo "⚠️  زمان تقریبی: 60-90 دقیقه"
echo ""
read -p "آیا ادامه می‌دهید؟ (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "لغو شد."
    exit 1
fi

# Backup .env
echo -e "${YELLOW}📦 پشتیبان‌گیری از .env...${NC}"
cp "$ENV_FILE" "$BACKUP_ENV"

# تنظیمات تست
declare -a CONFIGS=(
    "GapGPT|gpt-4o-mini|https://api.gapgpt.ir/v1"
    "GapGPT|gpt-5-mini|https://api.gapgpt.ir/v1"
    "GapGPT|gpt-5.1|https://api.gapgpt.ir/v1"
    "GapGPT|gpt-5.2-chat-latest|https://api.gapgpt.ir/v1"
    "OpenAI|gpt-4o-mini|https://api.openai.com/v1"
    "OpenAI|gpt-4o|https://api.openai.com/v1"
    "OpenAI|gpt-4o|https://api.openai.com/v1"
    "OpenAI|gpt-4o|https://api.openai.com/v1"
)

TOTAL_CONFIGS=${#CONFIGS[@]}
CURRENT=0

for config in "${CONFIGS[@]}"; do
    CURRENT=$((CURRENT + 1))
    IFS='|' read -r PROVIDER MODEL BASE_URL <<< "$config"
    
    echo ""
    echo "================================================================================"
    echo -e "${GREEN}[$CURRENT/$TOTAL_CONFIGS] تست: $PROVIDER - $MODEL${NC}"
    echo "================================================================================"
    
    # تغییر .env
    echo -e "${YELLOW}📝 بروزرسانی .env...${NC}"
    sed -i "s|^LLM2_MODEL=.*|LLM2_MODEL=\"$MODEL\"|g" "$ENV_FILE"
    sed -i "s|^LLM2_BASE_URL=.*|LLM2_BASE_URL=\"$BASE_URL\"|g" "$ENV_FILE"
    
    # Restart service
    echo -e "${YELLOW}🔄 Restart core-api...${NC}"
    cd "$DOCKER_COMPOSE_DIR"
    sudo docker compose restart core-api > /dev/null 2>&1
    
    # صبر برای آماده شدن service
    echo -e "${YELLOW}⏳ صبر برای آماده شدن service (10 ثانیه)...${NC}"
    sleep 10
    
    # اجرای تست
    echo -e "${GREEN}🚀 اجرای تست...${NC}"
    sudo docker compose exec -T core-api python /app/tests/test_llm_comparison_simple.py
    
    echo -e "${GREEN}✅ تست $PROVIDER - $MODEL تکمیل شد${NC}"
done

# بازگردانی .env
echo ""
echo -e "${YELLOW}📦 بازگردانی .env اصلی...${NC}"
cp "$BACKUP_ENV" "$ENV_FILE"

echo -e "${YELLOW}🔄 Restart نهایی core-api...${NC}"
cd "$DOCKER_COMPOSE_DIR"
sudo docker compose restart core-api > /dev/null 2>&1

echo ""
echo "================================================================================"
echo -e "${GREEN}✅ تمام تست‌ها تکمیل شد!${NC}"
echo "================================================================================"
echo ""
echo "📊 نتایج در /tmp/llm_test_*.json ذخیره شده‌اند"
echo ""
echo "برای تحلیل نتایج:"
echo "  python /app/tests/analyze_benchmark_results.py"
echo ""
