DO $$
DECLARE
    v_core_tables int;
    v_knowledge_tables int;
    v_assessment_tables int;
    v_core_functions int;
    v_knowledge_functions int;
    v_assessment_functions int;
    v_gateway_functions int;
    v_acl_rules int;
BEGIN
    -- Check core tables
    SELECT COUNT(*) INTO v_core_tables
    FROM information_schema.tables
    WHERE table_name IN ('procurements', 'triage_results', 'protocols', 'executions')
    AND table_schema = 'public';
    
    -- Check knowledge tables
    SELECT COUNT(*) INTO v_knowledge_tables
    FROM information_schema.tables
    WHERE table_name IN ('oslomodell_knowledge', 'miljokrav_knowledge')
    AND table_schema = 'public';
    
    -- Check assessment tables
    SELECT COUNT(*) INTO v_assessment_tables
    FROM information_schema.tables
    WHERE table_name IN ('environmental_assessments', 'oslomodell_assessments')
    AND table_schema = 'public';
    
    -- Check core functions
    SELECT COUNT(*) INTO v_core_functions
    FROM information_schema.routines
    WHERE routine_name IN ('create_procurement', 'save_triage_result', 'save_protocol', 'log_execution', 'set_procurement_status')
    AND routine_schema = 'public';
    
    -- Check knowledge functions
    SELECT COUNT(*) INTO v_knowledge_functions
    FROM information_schema.routines
    WHERE routine_name IN ('store_knowledge_document', 'search_knowledge_documents', 'list_knowledge_documents',
                           'store_miljokrav_document', 'search_miljokrav_documents', 'list_miljokrav_documents')
    AND routine_schema = 'public';
    
    -- Check assessment functions
    SELECT COUNT(*) INTO v_assessment_functions
    FROM information_schema.routines
    WHERE routine_name IN ('save_environmental_assessment', 'save_oslomodell_assessment')
    AND routine_schema = 'public';
    
    -- Check gateway catalog (commented out as table might not exist)
    SELECT COUNT(*) INTO v_gateway_functions
    FROM gateway_service_catalog
    WHERE is_active = true;
    
    -- Check ACL rules (commented out as table might not exist)
    SELECT COUNT(*) INTO v_acl_rules
    FROM gateway_acl_config
    WHERE is_active = true;
    
    -- Set default values if tables don't exist
    v_gateway_functions := COALESCE(v_gateway_functions, 0);
    v_acl_rules := COALESCE(v_acl_rules, 0);
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'COMPLETE DATABASE SETUP VERIFICATION';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Core Tables: % of 4', v_core_tables;
    RAISE NOTICE 'Knowledge Tables: % of 2', v_knowledge_tables;
    RAISE NOTICE 'Assessment Tables: % of 2', v_assessment_tables;
    RAISE NOTICE 'Core Functions: % of 5', v_core_functions;
    RAISE NOTICE 'Knowledge Functions: % of 6', v_knowledge_functions;
    RAISE NOTICE 'Assessment Functions: % of 2', v_assessment_functions;
    RAISE NOTICE 'Gateway Catalog: % functions', v_gateway_functions;
    RAISE NOTICE 'ACL Rules: % rules', v_acl_rules;
    RAISE NOTICE '========================================';
    
    IF v_core_tables >= 4 AND 
       v_knowledge_tables >= 2 AND 
       v_assessment_tables >= 2 AND
       v_core_functions >= 5 AND 
       v_knowledge_functions >= 6 AND 
       v_assessment_functions >= 2 AND
       v_gateway_functions >= 13 AND 
       v_acl_rules >= 20 THEN
        RAISE NOTICE '✅ COMPLETE DATABASE SETUP SUCCESSFUL!';
        RAISE NOTICE '   All tables, functions and ACL rules created.';
        RAISE NOTICE '   Ready for all agents:';
        RAISE NOTICE '   - Triage Agent';
        RAISE NOTICE '   - Oslomodell Agent (with assessments)';
        RAISE NOTICE '   - Environmental Agent (with assessments)';
        RAISE NOTICE '   - Protocol Agent';
        RAISE NOTICE '   - Reasoning Orchestrator';
    ELSE
        RAISE WARNING '⚠️ SETUP MAY BE INCOMPLETE - CHECK COUNTS ABOVE';
        RAISE WARNING 'Expected minimums:';
        RAISE WARNING '  Core Tables: 4';
        RAISE WARNING '  Knowledge Tables: 2';
        RAISE WARNING '  Assessment Tables: 2';
        RAISE WARNING '  Core Functions: 5';
        RAISE WARNING '  Knowledge Functions: 6';
        RAISE WARNING '  Assessment Functions: 2';
        RAISE WARNING '  Gateway Functions: 13+';
        RAISE WARNING '  ACL Rules: 20+';
    END IF;
    
    RAISE NOTICE '========================================';
END $$;