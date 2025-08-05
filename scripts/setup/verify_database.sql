-- ========================================
-- STEG 7: VERIFISER OPPSETT
-- ========================================


-- Vis registrerte funksjoner
-- \echo '\n--- Registered functions in service catalog ---
SELECT service_name, function_key, service_type, is_active
FROM gateway_service_catalog
ORDER BY service_name, function_key;

-- Vis ACL for reasoning_orchestrator
-- \echo '\n--- Access control for reasoning_orchestrator ---
SELECT allowed_method
FROM gateway_acl_config
WHERE agent_id = 'reasoning_orchestrator'
ORDER BY allowed_method;

-- Vis database-funksjoner
-- \echo '\n--- Database functions ---
SELECT proname as function_name, 
       pg_get_function_arguments(oid) as arguments,
       pg_get_function_result(oid) as returns
FROM pg_proc
WHERE proname IN ('opprett_anskaffelse', 'lagre_triage_resultat', 'sett_status', 'lagre_protokoll', 'log_orchestrator_execution')
AND pronamespace = 'public'::regnamespace
ORDER BY proname;

-- ========================================
-- STEG 8: KJØR EN ENKEL TEST
-- ========================================

-- \echo '\n=== STEP 8: Running simple test ==='

-- Test opprett_anskaffelse
SELECT create_procurement(jsonb_build_object(
    'name', 'Verification Test',
    'value', 10000,
    'description', 'Verify that the database is working'
));
