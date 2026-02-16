#!/usr/bin/env python3
"""Initialize database and create tables."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import Base
from app.models.user import *  # Import all models
from app.config.settings import settings


async def init_database():
    """Initialize database and create all tables."""
    print(f"Initializing database: {settings.database_url}")
    
    # Create engine
    engine = create_async_engine(
        str(settings.database_url),
        echo=True
    )
    
    # Create all tables
    async with engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully!")
    
    # Close engine
    await engine.dispose()


async def drop_database():
    """Drop all tables (use with caution!)."""
    print(f"Dropping all tables from: {settings.database_url}")
    
    response = input("Are you sure you want to drop all tables? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return
    
    # Create engine
    engine = create_async_engine(
        str(settings.database_url),
        echo=True
    )
    
    # Drop all tables
    async with engine.begin() as conn:
        print("Dropping tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Tables dropped successfully!")
    
    # Close engine
    await engine.dispose()


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before creating"
    )
    
    args = parser.parse_args()
    
    if args.drop:
        await drop_database()
    
    await init_database()


if __name__ == "__main__":
    asyncio.run(main())
