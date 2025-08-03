
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def main():
    # Load environment variables from the gateway's .env file
    dotenv_path = os.path.join(os.path.dirname(__file__), 'gateway', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in gateway/.env")
        return

    print(f"Attempting to connect to: {db_url}")

    try:
        conn = await asyncpg.connect(dsn=db_url)
        print("Successfully connected to the database!")
        await conn.close()
        print("Connection closed.")
    except Exception as e:
        print(f"Failed to connect to the database.")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")

if __name__ == "__main__":
    asyncio.run(main())
