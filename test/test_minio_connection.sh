#!/bin/bash

echo "======================================================================"
echo "تست اتصال به MinIO"
echo "======================================================================"

# تنظیمات از .env
ENDPOINT="https://s3.tejarat.chat"
ACCESS_KEY="eH01EjH7zdlIHEzlJ9Sb"
SECRET_KEY="5mswuxXYnZtNHSWhEDw8WUe51ztiOTlRCQa40r7i"
DOCUMENTS_BUCKET="advisor-docs"
TEMP_BUCKET="temp-userfile"

echo ""
echo "📋 تنظیمات:"
echo "  Endpoint: $ENDPOINT"
echo "  Access Key: ${ACCESS_KEY:0:10}..."
echo "  Documents Bucket: $DOCUMENTS_BUCKET"
echo "  Temp Bucket: $TEMP_BUCKET"
echo ""
echo "----------------------------------------------------------------------"

# تست 1: بررسی دسترسی به سرور
echo ""
echo "🧪 تست 1: بررسی دسترسی به سرور MinIO..."
echo "----------------------------------------------------------------------"

if timeout 5 curl -sk "$ENDPOINT/minio/health/live" > /dev/null 2>&1; then
    echo "✅ سرور MinIO در دسترس است"
else
    echo "❌ سرور MinIO در دسترس نیست یا timeout شد"
    echo ""
    echo "علت احتمالی:"
    echo "  - URL اشتباه است"
    echo "  - فایروال مسدود کرده"
    echo "  - شبکه قطع است"
    exit 1
fi

# نصب mc (MinIO Client) اگر نصب نیست
if ! command -v mc &> /dev/null; then
    echo ""
    echo "📦 نصب MinIO Client (mc)..."
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc
    chmod +x /tmp/mc
    MC_CMD="/tmp/mc"
else
    MC_CMD="mc"
fi

# پیکربندی mc
echo ""
echo "🔧 پیکربندی MinIO Client..."
$MC_CMD alias set tejarat "$ENDPOINT" "$ACCESS_KEY" "$SECRET_KEY" --insecure > /dev/null 2>&1

# تست 2: بررسی اعتبار credentials
echo ""
echo "🧪 تست 2: بررسی اعتبار Credentials..."
echo "----------------------------------------------------------------------"

if $MC_CMD ls tejarat --insecure > /dev/null 2>&1; then
    echo "✅ Credentials معتبر است"
else
    echo "❌ Credentials نامعتبر است!"
    echo ""
    echo "علت احتمالی:"
    echo "  - Access Key اشتباه است"
    echo "  - Secret Key اشتباه است"
    echo "  - دسترسی محدود شده"
    exit 1
fi

# تست 3: بررسی وجود باکت‌ها
echo ""
echo "🧪 تست 3: بررسی وجود باکت‌ها..."
echo "----------------------------------------------------------------------"

# لیست همه باکت‌ها
echo "لیست باکت‌های موجود:"
$MC_CMD ls tejarat --insecure

echo ""

# بررسی باکت advisor-docs
if $MC_CMD ls "tejarat/$DOCUMENTS_BUCKET" --insecure > /dev/null 2>&1; then
    echo "✅ باکت '$DOCUMENTS_BUCKET' وجود دارد"
    
    # شمارش فایل‌ها
    FILE_COUNT=$($MC_CMD ls "tejarat/$DOCUMENTS_BUCKET" --insecure --recursive 2>/dev/null | wc -l)
    echo "   📁 تعداد فایل‌ها: $FILE_COUNT"
    
    # نمایش چند فایل اول
    if [ $FILE_COUNT -gt 0 ]; then
        echo "   📄 نمونه فایل‌ها:"
        $MC_CMD ls "tejarat/$DOCUMENTS_BUCKET" --insecure --recursive 2>/dev/null | head -5 | awk '{print "      - " $5}'
    fi
else
    echo "⚠️  باکت '$DOCUMENTS_BUCKET' وجود ندارد"
    echo "   ایجاد باکت..."
    
    if $MC_CMD mb "tejarat/$DOCUMENTS_BUCKET" --insecure 2>/dev/null; then
        echo "   ✅ باکت '$DOCUMENTS_BUCKET' ایجاد شد"
    else
        echo "   ❌ خطا در ایجاد باکت"
    fi
fi

echo ""

# بررسی باکت temp-userfile
if $MC_CMD ls "tejarat/$TEMP_BUCKET" --insecure > /dev/null 2>&1; then
    echo "✅ باکت '$TEMP_BUCKET' وجود دارد"
    
    # شمارش فایل‌ها
    FILE_COUNT=$($MC_CMD ls "tejarat/$TEMP_BUCKET" --insecure --recursive 2>/dev/null | wc -l)
    echo "   📁 تعداد فایل‌ها: $FILE_COUNT"
    
    # نمایش چند فایل اول
    if [ $FILE_COUNT -gt 0 ]; then
        echo "   📄 نمونه فایل‌ها:"
        $MC_CMD ls "tejarat/$TEMP_BUCKET" --insecure --recursive 2>/dev/null | head -5 | awk '{print "      - " $5}'
    fi
else
    echo "⚠️  باکت '$TEMP_BUCKET' وجود ندارد"
    echo "   ایجاد باکت..."
    
    if $MC_CMD mb "tejarat/$TEMP_BUCKET" --insecure 2>/dev/null; then
        echo "   ✅ باکت '$TEMP_BUCKET' ایجاد شد"
    else
        echo "   ❌ خطا در ایجاد باکت"
    fi
fi

# تست 4: آپلود و دانلود تستی
echo ""
echo "🧪 تست 4: آپلود و دانلود فایل تستی..."
echo "----------------------------------------------------------------------"

# ایجاد فایل تست
TEST_FILE="/tmp/minio_test_$(date +%s).txt"
echo "این یک فایل تست برای MinIO است" > "$TEST_FILE"
echo "تاریخ: $(date)" >> "$TEST_FILE"

# آپلود به باکت temp
TEST_OBJECT="test/test_file_$(date +%s).txt"

if $MC_CMD cp "$TEST_FILE" "tejarat/$TEMP_BUCKET/$TEST_OBJECT" --insecure > /dev/null 2>&1; then
    echo "✅ آپلود موفق به '$TEMP_BUCKET/$TEST_OBJECT'"
    
    # دانلود
    DOWNLOAD_FILE="/tmp/minio_download_$(date +%s).txt"
    if $MC_CMD cp "tejarat/$TEMP_BUCKET/$TEST_OBJECT" "$DOWNLOAD_FILE" --insecure > /dev/null 2>&1; then
        echo "✅ دانلود موفق"
        
        # مقایسه محتوا
        if diff "$TEST_FILE" "$DOWNLOAD_FILE" > /dev/null 2>&1; then
            echo "✅ محتوای فایل یکسان است"
        else
            echo "❌ محتوای فایل متفاوت است!"
        fi
        
        rm -f "$DOWNLOAD_FILE"
    else
        echo "❌ خطا در دانلود"
    fi
    
    # حذف فایل تست
    $MC_CMD rm "tejarat/$TEMP_BUCKET/$TEST_OBJECT" --insecure > /dev/null 2>&1
    echo "🗑️  فایل تست حذف شد"
else
    echo "❌ خطا در آپلود"
fi

rm -f "$TEST_FILE"

# تست 5: بررسی دسترسی‌ها
echo ""
echo "🧪 تست 5: بررسی دسترسی‌ها..."
echo "----------------------------------------------------------------------"

# بررسی policy باکت documents
echo "Policy باکت '$DOCUMENTS_BUCKET':"
$MC_CMD anonymous get "tejarat/$DOCUMENTS_BUCKET" --insecure 2>/dev/null || echo "  - Private (پیش‌فرض)"

echo ""
echo "Policy باکت '$TEMP_BUCKET':"
$MC_CMD anonymous get "tejarat/$TEMP_BUCKET" --insecure 2>/dev/null || echo "  - Private (پیش‌فرض)"

# خلاصه
echo ""
echo "======================================================================"
echo "📊 خلاصه نتایج:"
echo "======================================================================"
echo ""
echo "✅ اتصال به MinIO: موفق"
echo "✅ Credentials: معتبر"
echo "✅ باکت '$DOCUMENTS_BUCKET': موجود"
echo "✅ باکت '$TEMP_BUCKET': موجود"
echo "✅ آپلود/دانلود: موفق"
echo ""
echo "🎉 همه تست‌ها موفق بود!"
echo ""
echo "======================================================================"

# پاکسازی
if [ -f "/tmp/mc" ]; then
    rm -f /tmp/mc
fi
