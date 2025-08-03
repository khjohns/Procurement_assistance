import asyncio
import asyncpg

async def main():
    # Prøv både pooler og direct connection
    urls = {
        "pooler": "postgresql://postgres.yebniyrvscpzjbmdgnwc:TestPassord2025@aws-0-eu-north-1.pooler.supabase.com:6543/postgres",
        "direct": "postgresql://postgres.yebniyrvscpzjbmdgnwc:TestPassord2025@aws-0-eu-north-1.pooler.supabase.com:5432/postgres"
    }
    
    for conn_type, db_url in urls.items():
        print(f"\nTesting {conn_type} connection...")
        print(f"URL: {db_url}")
        
        try:
            conn = await asyncpg.connect(
                dsn=db_url,
                timeout=10,  # 10 sekunder timeout
                command_timeout=10
            )
            print(f"✓ {conn_type} connection successful!")
            
            # Test en enkel query
            version = await conn.fetchval('SELECT version()')
            print(f"  PostgreSQL version: {version[:50]}...")
            
            await conn.close()
        except Exception as e:
            print(f"✗ {conn_type} connection failed")
            print(f"  Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())