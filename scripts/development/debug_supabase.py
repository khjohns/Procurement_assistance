

import asyncio
import os
import json
from datetime import datetime
from tools.simple_supabase_gateway import SimpleSupabaseGateway
from models.procurement_models import TriageResult

async def debug_supabase():
    """Comprehensive debugging of Supabase operations"""
    
    gateway = SimpleSupabaseGateway()
    
    try:
        await gateway.connect()
        print("\n=== Connected to Supabase ===")
        
        # 1. Test basic connection
        print("\n1. Testing basic SQL execution:")
        result = await gateway.execute_sql("SELECT current_database(), current_user, now();")
        print(f"Database info: {json.dumps(result, indent=2)}")
        
        # 2. Check if table exists
        print("\n2. Checking if triage_results table exists:")
        table_check = await gateway.execute_sql("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'triage_results';
        """)
        print(f"Table exists check: {json.dumps(table_check, indent=2)}")
        
        # 3. Check table structure
        print("\n3. Checking table structure:")
        column_check = await gateway.execute_sql("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = 'triage_results'
            ORDER BY ordinal_position;
        """)
        print(f"Table columns: {json.dumps(column_check, indent=2)}")
        
        # 4. Check RLS (Row Level Security) status
        print("\n4. Checking RLS status:")
        rls_check = await gateway.execute_sql("""
            SELECT schemaname, tablename, rowsecurity 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename = 'triage_results';
        """)
        print(f"RLS status: {json.dumps(rls_check, indent=2)}")
        
        # 5. Check current policies
        print("\n5. Checking RLS policies:")
        policy_check = await gateway.execute_sql("""
            SELECT pol.polname, pol.polcmd, pol.polpermissive,
                   pg_get_expr(pol.polqual, pol.polrelid) as qual,
                   pg_get_expr(pol.polwithcheck, pol.polrelid) as with_check,
                   rol.rolname
            FROM pg_policy pol
            JOIN pg_class cls ON pol.polrelid = cls.oid
            JOIN pg_roles rol ON pol.polroles @> ARRAY[rol.oid]
            WHERE cls.relname = 'triage_results';
        """)
        print(f"Policies: {json.dumps(policy_check, indent=2)}")
        
        # 6. Try to insert with explicit returning
        print("\n6. Testing INSERT with explicit RETURNING:")
        test_id = f"debug-test-{datetime.utcnow().timestamp()}"
        insert_result = await gateway.execute_sql(f"""
            INSERT INTO triage_results (request_id, farge, begrunnelse, confidence, created_at)
            VALUES ('{test_id}', 'grønn', 'Debug test', 0.99, NOW())
            RETURNING *;
        """)
        print(f"Insert result: {json.dumps(insert_result, indent=2)}")
        
        # 7. Immediately check if it was inserted
        print("\n7. Checking if insert was successful:")
        verify_result = await gateway.execute_sql(f"""
            SELECT * FROM triage_results WHERE request_id = '{test_id}';
        """)
        print(f"Verification: {json.dumps(verify_result, indent=2)}")
        
        # 8. Count all rows
        print("\n8. Counting all rows in table:")
        count_result = await gateway.execute_sql("""
            SELECT COUNT(*) as total_rows FROM triage_results;
        """)
        print(f"Total rows: {json.dumps(count_result, indent=2)}")
        
        # 9. Check authentication context
        print("\n9. Checking authentication context:")
        auth_check = await gateway.execute_sql("""
            SELECT 
                current_setting('request.jwt.claims', true)::json->>'role' as jwt_role,
                current_setting('request.jwt.claims', true)::json->>'sub' as jwt_sub,
                auth.uid() as auth_uid,
                auth.role() as auth_role;
        """)
        print(f"Auth context: {json.dumps(auth_check, indent=2)}")
        
        # 10. Try disabling RLS temporarily (only if you have permissions)
        print("\n10. Testing with RLS disabled (if permitted):")
        try:
            # First check if we can alter table
            alter_result = await gateway.execute_sql("""
                ALTER TABLE triage_results DISABLE ROW LEVEL SECURITY;
            """)
            print("RLS disabled successfully")
            
            # Try insert again
            test_id_2 = f"debug-no-rls-{datetime.utcnow().timestamp()}"
            insert_no_rls = await gateway.execute_sql(f"""
                INSERT INTO triage_results (request_id, farge, begrunnelse, confidence, created_at)
                VALUES ('{test_id_2}', 'gul', 'Test without RLS', 0.88, NOW())
                RETURNING *;
            """)
            print(f"Insert without RLS: {json.dumps(insert_no_rls, indent=2)}")
            
            # Re-enable RLS
            await gateway.execute_sql("ALTER TABLE triage_results ENABLE ROW LEVEL SECURITY;")
            print("RLS re-enabled")
            
        except Exception as e:
            print(f"Could not alter RLS settings: {e}")
        
        # 11. Additional diagnostics
        print("\n11. Additional diagnostics:")
        project_ref = os.getenv("SUPABASE_PROJECT_REF")
        access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
        print(f"Project Ref: {project_ref}")
        print(f"Access Token Type: {'Service Role' if 'service_role' in access_token else 'Anon/Other'}")
        print(f"Token prefix: {access_token[:20]}...")
        
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await gateway.close()


# Also create a script to set up proper RLS policies
async def setup_rls_policies():
    """Set up proper RLS policies for the table"""
    gateway = SimpleSupabaseGateway()
    
    try:
        await gateway.connect()
        
        print("\n=== Setting up RLS policies ===")
        
        # 1. Disable RLS first to ensure we can set it up properly
        print("\n1. Disabling RLS temporarily...")
        await gateway.execute_sql("ALTER TABLE public.triage_results DISABLE ROW LEVEL SECURITY;")
        
        # 2. Drop existing policies
        print("\n2. Dropping existing policies...")
        await gateway.execute_sql("DROP POLICY IF EXISTS \"Enable all for service role\" ON public.triage_results;")
        await gateway.execute_sql("DROP POLICY IF EXISTS \"Enable read for all\" ON public.triage_results;")
        await gateway.execute_sql("DROP POLICY IF EXISTS \"Enable insert for all\" ON public.triage_results;")
        
        # 3. Create new policies
        print("\n3. Creating new policies...")
        
        # Policy for service role (full access)
        service_policy = await gateway.execute_sql("""
            CREATE POLICY \"Enable all for service role\" ON public.triage_results
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
        """)
        print("Service role policy created")
        
        # Policy for authenticated users (if using authenticated key)
        auth_policy = await gateway.execute_sql("""
            CREATE POLICY \"Enable all for authenticated\" ON public.triage_results
            FOR ALL
            TO authenticated
            USING (true)
            WITH CHECK (true);
        """)
        print("Authenticated policy created")
        
        # Policy for anon (if needed)
        anon_policy = await gateway.execute_sql("""
            CREATE POLICY \"Enable all for anon\" ON public.triage_results
            FOR ALL
            TO anon
            USING (true)
            WITH CHECK (true);
        """)
        print("Anon policy created")
        
        # 4. Re-enable RLS
        print("\n4. Re-enabling RLS...")
        await gateway.execute_sql("ALTER TABLE public.triage_results ENABLE ROW LEVEL SECURITY;")
        
        print("\nRLS policies set up successfully!")
        
    except Exception as e:
        print(f"\nERROR setting up policies: {e}")
    
    finally:
        await gateway.close()


if __name__ == "__main__":
    print("=== SUPABASE DEBUG SCRIPT ===")
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    print("\n1. Running comprehensive debug...")
    asyncio.run(debug_supabase())
    
    print("\n" + "="*50)
    print("\n2. Would you like to set up RLS policies? (y/n)")
    user_input = input().lower()
    if user_input == 'y':
        asyncio.run(setup_rls_policies())
