# scripts/sync_gateway_catalog.py
"""
Script to automatically sync SDK registry with database.
Run this during deployment to update gateway_service_catalog and gateway_acl_config.
"""
import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv
import structlog

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import registry functions
from src.agent_library.registry import (
    TOOL_REGISTRY, 
    generate_gateway_catalog_sql, 
    generate_acl_config_sql
)

# Import all agents to populate registry
# This triggers the @register_tool decorators
import src.specialists.triage_agent
# Import other agents as you create them:
# import src.specialists.oslomodell_agent
# import src.specialists.protocol_generator

logger = structlog.get_logger()

async def sync_gateway_catalog():
    """
    Sync TOOL_REGISTRY with database gateway_service_catalog.
    This is the ONLY time code and database communicate directly.
    """
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        return False
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        # Generate SQL statements from registry
        catalog_sql = generate_gateway_catalog_sql()
        acl_sql = generate_acl_config_sql()
        
        if not catalog_sql:
            logger.warning("No tools found in registry. Did you import the agent modules?")
            return False
        
        # Execute in transaction
        async with conn.transaction():
            # Update service catalog
            logger.info("Updating gateway_service_catalog...")
            for statement in catalog_sql.split(';'):
                if statement.strip():
                    await conn.execute(statement)
            
            # Update ACL config
            logger.info("Updating gateway_acl_config...")
            for statement in acl_sql.split(';'):
                if statement.strip():
                    await conn.execute(statement)
        
        # Report results
        tool_count = len(TOOL_REGISTRY)
        logger.info(f"✅ Successfully synced {tool_count} tools to database")
        
        # Print registered tools for verification
        print("\n📋 Registered Tools:")
        for method_name, tool_info in TOOL_REGISTRY.items():
            print(f"  • {method_name}")
            print(f"    Class: {tool_info['class'].__name__}")
            print(f"    Type: {tool_info['service_type']}")
            print(f"    Dependencies: {tool_info['dependencies']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error("Failed to sync gateway catalog", error=str(e), exc_info=True)
        return False

async def verify_sync():
    """Verify that the sync was successful by querying the database."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        return
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check service catalog
        catalog_rows = await conn.fetch("""
            SELECT service_name, function_key, service_type, is_active
            FROM gateway_service_catalog
            WHERE is_active = true
            ORDER BY service_name, function_key
        """)
        
        print("\n✅ Gateway Service Catalog:")
        for row in catalog_rows:
            print(f"  • {row['service_name']}.{row['function_key']} ({row['service_type']})")
        
        # Check ACL config
        acl_rows = await conn.fetch("""
            SELECT DISTINCT allowed_method
            FROM gateway_acl_config
            WHERE agent_id = 'reasoning_orchestrator' AND is_active = true
            ORDER BY allowed_method
        """)
        
        print("\n✅ Orchestrator Permissions:")
        for row in acl_rows:
            print(f"  • {row['allowed_method']}")
        
        await conn.close()
        
    except Exception as e:
        logger.error("Failed to verify sync", error=str(e))

async def main():
    """Main entry point for sync script."""
    print("🚀 Starting Gateway Catalog Sync...")
    print(f"📁 Found {len(TOOL_REGISTRY)} tools in registry\n")
    
    success = await sync_gateway_catalog()
    
    if success:
        print("\n🔍 Verifying database state...")
        await verify_sync()
        print("\n✅ Sync completed successfully!")
    else:
        print("\n❌ Sync failed. Check logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    
    asyncio.run(main())