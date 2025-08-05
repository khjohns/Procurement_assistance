# scripts/setup/run_db_setup.py (Corrected to run as single transaction)
import os
import sys
import psycopg2
from dotenv import load_dotenv
import argparse

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

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
                for command in sql_commands:
                    print(f"\n🚀 Running query:\n{command[:200]}...\n")
                    cur.execute(command + ';')
                    if cur.description:
                        print("✨ Result:")
                        rows = cur.fetchall()
                        colnames = [desc[0] for desc in cur.description]
                        print(" | ".join(colnames))
                        print("-" * (len(" | ".join(colnames))))
                        for row in rows:
                            print(" | ".join(map(str, row)))
                    else:
                        conn.commit()
                        print("✅ Command completed.")
            else:
                # For setup, run the whole script as one transaction
                print(f"\n🚀 Executing the entire script as a single transaction...")
                cur.execute(sql_content)
                conn.commit()
                print("✅ Script executed successfully.")

        print(f"\n🎉 Script '{os.path.basename(filepath)}' finished.")

    except psycopg2.Error as e:
        print(f"❌ Database Error while running {os.path.basename(filepath)}: {e}")
        if conn: conn.rollback()
    except FileNotFoundError:
        print(f"❌ Error: SQL script not found at '{filepath}'")

def main():
    parser = argparse.ArgumentParser(description="Run database setup or verification scripts.")
    parser.add_argument('action', choices=['setup', 'verify'], help="'setup' to reset the DB, 'verify' to check it.")
    args = parser.parse_args()

    print(f"--- Starting database operation: {args.action.upper()} ---")
    
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        print(f"❌ Error: .env file not found at '{env_path}'")
        return
    
    load_dotenv(dotenv_path=env_path)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL is not set in .env file.")
        return

    print("✅ .env file loaded and DATABASE_URL found.")

    conn = None
    try:
        print("🔌 Connecting to the database...")
        conn = psycopg2.connect(db_url)
        print("✅ Database connection successful.")
        
        sql_file = 'reset_database.sql' if args.action == 'setup' else 'verify_database.sql'
        is_verification = args.action == 'verify'
        sql_file_path = os.path.join(os.path.dirname(__file__), sql_file)
        
        run_sql_from_file(conn, sql_file_path, is_verification)

    except psycopg2.Error as e:
        print(f"❌ Failed to connect to the database: {e}")
    finally:
        if conn:
            conn.close()
            print("\n🔌 Database connection closed.")

    print(f"--- Database operation '{args.action.upper()}' finished ---")

if __name__ == "__main__":
    main()
