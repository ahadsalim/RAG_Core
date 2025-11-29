#!/bin/bash

echo "======================================================================"
echo "تست اتصال به LLM خارجی (GapGPT)"
echo "======================================================================"

API_KEY="sk-QGiGf0uwYr2mqmCUR1zUMQVSwU4t8if48aspRjGalnum9zIE"
BASE_URL="https://api.gapgpt.app/v1"
MODEL="gpt-4o-mini"

echo ""
echo "📋 تنظیمات:"
echo "  Base URL: $BASE_URL"
echo "  Model: $MODEL"
echo "  API Key: ${API_KEY:0:20}..."
echo ""
echo "----------------------------------------------------------------------"

# تست 1: بررسی دسترسی به سرور
echo ""
echo "🧪 تست 1: بررسی دسترسی به سرور..."
echo "----------------------------------------------------------------------"

if timeout 5 curl -s -I "$BASE_URL" > /dev/null 2>&1; then
    echo "✅ سرور در دسترس است"
else
    echo "❌ سرور در دسترس نیست یا timeout شد"
    echo ""
    echo "علت احتمالی:"
    echo "  - URL اشتباه است"
    echo "  - فایروال مسدود کرده"
    echo "  - شبکه قطع است"
    exit 1
fi

# تست 2: ارسال درخواست ساده
echo ""
echo "🧪 تست 2: ارسال درخواست به LLM..."
echo "----------------------------------------------------------------------"

RESPONSE=$(timeout 10 curl -s -w "\n%{http_code}" \
  -X POST "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$MODEL"'",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "سلام"}
    ],
    "max_tokens": 50,
    "temperature": 0.2
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo "HTTP Status: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ موفق! پاسخ دریافت شد:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    
elif [ "$HTTP_CODE" = "401" ]; then
    echo "❌ خطای 401: API Key نامعتبر است!"
    echo "$BODY"
    
elif [ "$HTTP_CODE" = "404" ]; then
    echo "❌ خطای 404: Base URL یا Model اشتباه است!"
    echo "$BODY"
    
elif [ "$HTTP_CODE" = "429" ]; then
    echo "❌ خطای 429: محدودیت درخواست (Rate Limit)"
    echo "$BODY"
    
elif [ "$HTTP_CODE" = "500" ] || [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "503" ]; then
    echo "❌ خطای سرور ($HTTP_CODE): سرور LLM مشکل دارد"
    echo "$BODY"
    
elif [ -z "$HTTP_CODE" ]; then
    echo "❌ Timeout! سرور بیش از 10 ثانیه پاسخ نداد"
    echo ""
    echo "علت احتمالی:"
    echo "  - سرور خیلی کند است"
    echo "  - شبکه مشکل دارد"
    echo "  - سرور hang شده"
    
else
    echo "❌ خطای نامشخص (HTTP $HTTP_CODE)"
    echo "$BODY"
fi

echo ""
echo "======================================================================"
echo "پایان تست"
echo "======================================================================"
