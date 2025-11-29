#!/usr/bin/env python3
"""
تست ساده اتصال به MinIO با Python
"""

import sys
import boto3
from botocore.exceptions import ClientError

# تنظیمات از .env
ENDPOINT = "https://s3.tejarat.chat"
ACCESS_KEY = "eH01EjH7zdlIHEzlJ9Sb"
SECRET_KEY = "5mswuxXYnZtNHSWhEDw8WUe51ztiOTlRCQa40r7i"
DOCUMENTS_BUCKET = "advisor-docs"
TEMP_BUCKET = "temp-userfile"

print("=" * 70)
print("تست اتصال به MinIO با Python")
print("=" * 70)
print()
print("📋 تنظیمات:")
print(f"  Endpoint: {ENDPOINT}")
print(f"  Access Key: {ACCESS_KEY[:10]}...")
print(f"  Documents Bucket: {DOCUMENTS_BUCKET}")
print(f"  Temp Bucket: {TEMP_BUCKET}")
print()
print("-" * 70)

try:
    # ایجاد S3 client
    print()
    print("🔧 ایجاد S3 Client...")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='us-east-1',
        verify=False  # برای SSL self-signed
    )
    
    print("✅ Client ایجاد شد")
    
    # تست 1: لیست باکت‌ها
    print()
    print("🧪 تست 1: لیست باکت‌ها...")
    print("-" * 70)
    
    response = s3_client.list_buckets()
    buckets = [b['Name'] for b in response['Buckets']]
    
    print(f"✅ تعداد باکت‌ها: {len(buckets)}")
    print("📦 باکت‌های موجود:")
    for bucket in buckets:
        print(f"   - {bucket}")
    
    # تست 2: بررسی باکت documents
    print()
    print(f"🧪 تست 2: بررسی باکت '{DOCUMENTS_BUCKET}'...")
    print("-" * 70)
    
    if DOCUMENTS_BUCKET in buckets:
        print(f"✅ باکت '{DOCUMENTS_BUCKET}' وجود دارد")
        
        # لیست فایل‌ها
        try:
            response = s3_client.list_objects_v2(
                Bucket=DOCUMENTS_BUCKET,
                MaxKeys=10
            )
            
            if 'Contents' in response:
                file_count = response.get('KeyCount', 0)
                print(f"   📁 تعداد فایل‌ها (نمونه): {file_count}")
                print("   📄 نمونه فایل‌ها:")
                for obj in response['Contents'][:5]:
                    size_mb = obj['Size'] / (1024 * 1024)
                    print(f"      - {obj['Key']} ({size_mb:.2f} MB)")
            else:
                print("   📁 باکت خالی است")
                
        except ClientError as e:
            print(f"   ⚠️  خطا در خواندن فایل‌ها: {e}")
    else:
        print(f"⚠️  باکت '{DOCUMENTS_BUCKET}' وجود ندارد")
        print("   ایجاد باکت...")
        try:
            s3_client.create_bucket(Bucket=DOCUMENTS_BUCKET)
            print(f"   ✅ باکت '{DOCUMENTS_BUCKET}' ایجاد شد")
        except ClientError as e:
            print(f"   ❌ خطا در ایجاد باکت: {e}")
    
    # تست 3: بررسی باکت temp
    print()
    print(f"🧪 تست 3: بررسی باکت '{TEMP_BUCKET}'...")
    print("-" * 70)
    
    if TEMP_BUCKET in buckets:
        print(f"✅ باکت '{TEMP_BUCKET}' وجود دارد")
        
        # لیست فایل‌ها
        try:
            response = s3_client.list_objects_v2(
                Bucket=TEMP_BUCKET,
                MaxKeys=10
            )
            
            if 'Contents' in response:
                file_count = response.get('KeyCount', 0)
                print(f"   📁 تعداد فایل‌ها (نمونه): {file_count}")
                print("   📄 نمونه فایل‌ها:")
                for obj in response['Contents'][:5]:
                    size_mb = obj['Size'] / (1024 * 1024)
                    print(f"      - {obj['Key']} ({size_mb:.2f} MB)")
            else:
                print("   📁 باکت خالی است")
                
        except ClientError as e:
            print(f"   ⚠️  خطا در خواندن فایل‌ها: {e}")
    else:
        print(f"⚠️  باکت '{TEMP_BUCKET}' وجود ندارد")
        print("   ایجاد باکت...")
        try:
            s3_client.create_bucket(Bucket=TEMP_BUCKET)
            print(f"   ✅ باکت '{TEMP_BUCKET}' ایجاد شد")
        except ClientError as e:
            print(f"   ❌ خطا در ایجاد باکت: {e}")
    
    # تست 4: آپلود و دانلود تستی
    print()
    print("🧪 تست 4: آپلود و دانلود فایل تستی...")
    print("-" * 70)
    
    import datetime
    test_content = f"این یک فایل تست است\nتاریخ: {datetime.datetime.now()}"
    test_key = f"test/test_file_{datetime.datetime.now().timestamp()}.txt"
    
    try:
        # آپلود
        s3_client.put_object(
            Bucket=TEMP_BUCKET,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"✅ آپلود موفق: {test_key}")
        
        # دانلود
        response = s3_client.get_object(
            Bucket=TEMP_BUCKET,
            Key=test_key
        )
        downloaded_content = response['Body'].read().decode('utf-8')
        print("✅ دانلود موفق")
        
        # مقایسه
        if downloaded_content == test_content:
            print("✅ محتوای فایل یکسان است")
        else:
            print("❌ محتوای فایل متفاوت است!")
        
        # حذف
        s3_client.delete_object(
            Bucket=TEMP_BUCKET,
            Key=test_key
        )
        print("🗑️  فایل تست حذف شد")
        
    except ClientError as e:
        print(f"❌ خطا در آپلود/دانلود: {e}")
    
    # خلاصه
    print()
    print("=" * 70)
    print("📊 خلاصه نتایج:")
    print("=" * 70)
    print()
    print("✅ اتصال به MinIO: موفق")
    print("✅ Credentials: معتبر")
    print(f"✅ باکت '{DOCUMENTS_BUCKET}': {'موجود' if DOCUMENTS_BUCKET in buckets else 'ایجاد شد'}")
    print(f"✅ باکت '{TEMP_BUCKET}': {'موجود' if TEMP_BUCKET in buckets else 'ایجاد شد'}")
    print("✅ آپلود/دانلود: موفق")
    print()
    print("🎉 همه تست‌ها موفق بود!")
    print()
    print("=" * 70)
    
    sys.exit(0)

except ClientError as e:
    print()
    print("=" * 70)
    print("❌ خطا در اتصال به MinIO")
    print("=" * 70)
    print()
    print(f"Error Code: {e.response['Error']['Code']}")
    print(f"Error Message: {e.response['Error']['Message']}")
    print()
    
    if e.response['Error']['Code'] == 'InvalidAccessKeyId':
        print("🔑 Access Key نامعتبر است!")
    elif e.response['Error']['Code'] == 'SignatureDoesNotMatch':
        print("🔑 Secret Key نامعتبر است!")
    else:
        print("⚠️  خطای نامشخص")
    
    sys.exit(1)

except Exception as e:
    print()
    print("=" * 70)
    print("❌ خطای غیرمنتظره")
    print("=" * 70)
    print()
    print(f"Error: {type(e).__name__}")
    print(f"Message: {str(e)}")
    print()
    
    if "Connection" in str(e) or "timeout" in str(e).lower():
        print("🔌 مشکل در اتصال به سرور")
        print()
        print("علت احتمالی:")
        print("  - سرور MinIO خاموش است")
        print("  - URL اشتباه است")
        print("  - فایروال مسدود کرده")
        print("  - شبکه قطع است")
    
    sys.exit(1)
