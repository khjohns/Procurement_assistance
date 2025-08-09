#!/usr/bin/env python3
"""
run_db_setup.py - CONSOLIDATED DATABASE SETUP
Updated to use the new consolidated setup file
which includes Core, Oslomodell, and Miljokrav in a coordinated setup.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv
import argparse
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def run_sql_from_file(conn, filepath, is_verification=False):
    """Runs a SQL script from a file."""
    print(f"\n--- Running script: {os.path.basename(filepath)} ---")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        with conn.cursor() as cur:
            if is_verification:
                # For verification, split and run commands to show individual results
                sql_commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
                for i, command in enumerate(sql_commands, 1):
                    if len(command) < 10:  # Skip very short commands
                        continue
                    print(f"\n🚀 Running query {i}/{len(sql_commands)}:\n{command[:100]}...\n")
                    try:
                        cur.execute(command + ';')
                        if cur.description:
                            print("✨ Result:")
                            rows = cur.fetchall()
                            colnames = [desc[0] for desc in cur.description]
                            print(" | ".join(colnames))
                            print("-" * (len(" | ".join(colnames))))
                            for row in rows[:5]:  # Limit to first 5 rows
                                print(" | ".join(str(val)[:50] for val in row))
                            if len(rows) > 5:
                                print(f"... and {len(rows) - 5} more rows")
                        else:
                            conn.commit()
                            print("✅ Command completed.")
                    except psycopg2.Error as e:
                        print(f"❌ Error in command {i}: {e}")
                        conn.rollback()
            else:
                # For setup, run the whole script as one transaction
                print(f"\n🚀 Executing complete database setup...")
                print("   This includes: Core tables, Oslomodell, Miljokrav, Gateway config")
                cur.execute(sql_content)
                conn.commit()
                print("✅ Complete setup executed successfully.")

        print(f"\n🎉 Script '{os.path.basename(filepath)}' finished.")

    except psycopg2.Error as e:
        print(f"❌ Database Error while running {os.path.basename(filepath)}: {e}")
        if conn: 
            conn.rollback()
        raise
    except FileNotFoundError:
        print(f"❌ Error: SQL script not found at '{filepath}'")
        raise

def run_post_setup_tasks():
    """Run additional setup tasks after database is ready."""
    print("\n--- POST-SETUP TASKS ---")
    
    # List of knowledge loading scripts to run
    knowledge_scripts = [
        "scripts/load_oslomodell_knowledge.py",
        "scripts/load_miljokrav_knowledge.py"
    ]
    
    for script_path in knowledge_scripts:
        script_full_path = project_root / script_path
        if script_full_path.exists():
            print(f"\n📚 Loading knowledge: {script_path}")
            print(f"   Run manually: python {script_path}")
        else:
            print(f"⚠️ Knowledge script not found: {script_path}")
    
    # List of agent registration scripts
    agent_scripts = [
        "scripts/sync_gateway_catalog_oslomodell.py",
        "scripts/sync_gateway_catalog_miljokrav.py"
    ]
    
    for script_path in agent_scripts:
        script_full_path = project_root / script_path
        if script_full_path.exists():
            print(f"\n🔧 Agent registration: {script_path}")
            print(f"   Run manually: python {script_path}")
        else:
            print(f"⚠️ Agent script not found: {script_path}")

def check_prerequisites():
    """Check that all required files and dependencies are available."""
    print("\n--- CHECKING PREREQUISITES ---")
    
    # Check for .env file
    env_path = project_root / '.env'
    if not env_path.exists():
        print(f"❌ Error: .env file not found at '{env_path}'")
        print("   Please create .env file with DATABASE_URL")
        return False
    
    # Check for required directories
    required_dirs = [
        project_root / "src" / "specialists",
        project_root / "src" / "models",
        project_root / "gateway"
    ]
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            print(f"❌ Error: Required directory not found: {dir_path}")
            return False
        else:
            print(f"✅ Directory found: {dir_path}")
    
    # Check for key Python files
    key_files = [
        project_root / "src" / "models" / "procurement_models.py",
        project_root / "src" / "orchestrators" / "reasoning_orchestrator.py",
        project_root / "gateway" / "main.py"
    ]
    
    for file_path in key_files:
        if not file_path.exists():
            print(f"⚠️ Warning: Key file not found: {file_path}")
        else:
            print(f"✅ Key file found: {file_path}")
    
    print("✅ Prerequisites check completed.")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Consolidated database setup for Procurement Assistant",
        epilog="Example: python scripts/setup/run_db_setup.py setup"
    )
    parser.add_argument(
        'action',
        choices=['setup', 'verify', 'check'],
        help="'setup' for full database reset, 'verify' to check current state, 'check' for prerequisites"
    )
    parser.add_argument(
        '--skip-post-setup',
        action='store_true',
        help="Skip post-setup knowledge loading instructions"
    )
    
    args = parser.parse_args()

    print(f"=== PROCUREMENT ASSISTANT DATABASE {args.action.upper()} ===")
    print(f"Project root: {project_root}")
    
    if args.action == 'check':
        return 0 if check_prerequisites() else 1
    
    # Check prerequisites for setup/verify
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed. Please fix issues above.")
        return 1
    
    # Load environment
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL is not set in .env file.")
        return 1

    print("✅ .env file loaded and DATABASE_URL found.")

    conn = None
    try:
        print("🔌 Connecting to the database...")
        conn = psycopg2.connect(db_url)
        print("✅ Database connection successful.")
        
        # Determine which SQL file to use
        if args.action == 'setup':
            sql_file = 'complete_database_setup.sql'  # New consolidated file
        else:  # verify
            sql_file = 'updated_verify_database.sql'  # Keep existing verify
        
        is_verification = args.action == 'verify'
        sql_file_path = Path(__file__).parent / sql_file
        
        if not sql_file_path.exists():
            print(f"❌ Error: SQL file not found: {sql_file_path}")
            print(f"   Make sure {sql_file} is in scripts/setup/")
            return 1
        
        run_sql_from_file(conn, sql_file_path, is_verification)
        
        # Show post-setup instructions for setup action
        if args.action == 'setup' and not args.skip_post_setup:
            run_post_setup_tasks()
            
            print("\n" + "="*60)
            print("🎉 DATABASE SETUP COMPLETED!")
            print("="*60)
            print("\nNext steps:")
            print("1. Load knowledge bases (see scripts above)")
            print("2. Register agents in gateway (see scripts above)")
            print("3. Start gateway: cd gateway && python main.py")
            print("4. Test with: python tests/integration/test_triage_orchestration.py")
            print("\nFor troubleshooting, run: python scripts/setup/run_db_setup.py verify")

    except psycopg2.Error as e:
        print(f"❌ Failed to connect to or execute on database: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1
    finally:
        if conn:
            conn.close()
            print("\n🔌 Database connection closed.")

    print(f"\n=== Database operation '{args.action.upper()}' completed ===")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
