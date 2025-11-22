#!/usr/bin/env python3
"""
Cleanup Orphan Conversations Script
حذف گفتگوهایی که در سیستم کاربران وجود ندارند
"""

import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, delete
from app.db.session import init_db, close_db, core_session_factory
from app.models.user import Conversation, Message


async def cleanup_orphan_conversations():
    """حذف تمام گفتگوهای orphan از دیتابیس Core"""
    
    print("🔧 راه‌اندازی اتصال به دیتابیس...")
    await init_db()
    
    try:
        from app.db.session import core_session_factory as factory
        
        if not factory:
            raise RuntimeError("Session factory not initialized")
            
        async with factory() as session:
            # بررسی تعداد گفتگوها
            result = await session.execute(select(func.count(Conversation.id)))
            total_conversations = result.scalar()
            
            print(f"\n📊 تعداد کل گفتگوها در Core: {total_conversations}")
            
            if total_conversations > 0:
                # دریافت لیست گفتگوها
                result = await session.execute(select(Conversation))
                conversations = result.scalars().all()
                
                print(f"\n🗑️  حذف {len(conversations)} گفتگوی orphan...")
                print("="*60)
                
                deleted_count = 0
                total_messages = 0
                
                for conv in conversations:
                    # شمارش پیام‌ها
                    msg_result = await session.execute(
                        select(func.count(Message.id)).where(Message.conversation_id == conv.id)
                    )
                    msg_count = msg_result.scalar()
                    total_messages += msg_count
                    
                    print(f"  ✓ حذف گفتگو {conv.id}")
                    print(f"    - تعداد پیام‌ها: {msg_count}")
                    print(f"    - تاریخ ایجاد: {conv.created_at}")
                    
                    await session.delete(conv)
                    deleted_count += 1
                
                await session.commit()
                
                print("="*60)
                print(f"\n✅ خلاصه:")
                print(f"   - گفتگوهای حذف شده: {deleted_count}")
                print(f"   - پیام‌های حذف شده: {total_messages}")
                print(f"\n✅ تمام گفتگوهای orphan با موفقیت حذف شدند")
            else:
                print("\n✅ هیچ گفتگوی orphan وجود ندارد")
                
    except Exception as e:
        print(f"\n❌ خطا در حذف گفتگوها: {e}")
        raise
    finally:
        await close_db()
        print("\n🔒 اتصال به دیتابیس بسته شد")


if __name__ == "__main__":
    print("="*60)
    print("🧹 Cleanup Orphan Conversations")
    print("="*60)
    
    asyncio.run(cleanup_orphan_conversations())
