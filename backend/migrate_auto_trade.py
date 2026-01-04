
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://hedge_user:hedge_pass@localhost:5432/hedge_db"
)

async def migrate():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Checking if column exists...")
        try:
            # Try to select the column to see if it exists
            await conn.execute(text("SELECT auto_trade FROM bot_configs LIMIT 1"))
            print("Column 'auto_trade' already exists.")
        except Exception:
            print("Column 'auto_trade' missing. Adding it...")
            await conn.execute(text("ALTER TABLE bot_configs ADD COLUMN auto_trade BOOLEAN DEFAULT FALSE"))
            print("Column added successfully.")
            
            # Set it to TRUE for id=1 for convenience since user asked
            print("Enabling auto_trade for config id=1...")
            await conn.execute(text("UPDATE bot_configs SET auto_trade = TRUE WHERE id = 1"))
            print("Auto-trade enabled.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
