# scripts/reset_gateway.py
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def reset_gateway_cache():
    """Force gateway to reload service catalog."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    conn = await asyncpg.connect(database_url)
    
    # Force update timestamp on all catalog entries
    await conn.execute("""
        UPDATE gateway_service_catalog 
        SET created_at = NOW() 
        WHERE is_active = true;
    """)
    
    # Force update ACL config
    await conn.execute("""
        UPDATE gateway_acl_config 
        SET created_at = NOW() 
        WHERE is_active = true;
    """)
    
    await conn.close()
    print("✅ Gateway catalog timestamps updated - will force reload")

if __name__ == "__main__":
    asyncio.run(reset_gateway_cache())