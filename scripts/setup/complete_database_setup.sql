-- complete_database_setup.sql
-- CONSOLIDATED database setup for entire Procurement Assistant system
-- Includes: Core tables, Oslomodell, Miljokrav, Gateway services, ACL, and assessment tables
-- Run this for a complete, fresh setup with full reasoning_orchestrator access

-- ========================================
-- STEP 1: CLEAN UP (DROP EVERYTHING)
-- ========================================

-- Drop specialized assessment tables first
DROP TABLE IF EXISTS environmental_assessments CASCADE;
DROP TABLE IF EXISTS oslomodell_assessments CASCADE;

-- Drop specialized knowledge tables
DROP TABLE IF EXISTS miljokrav_knowledge CASCADE;
DROP TABLE IF EXISTS oslomodell_knowledge CASCADE;

-- Drop specialized functions
DROP FUNCTION IF EXISTS store_miljokrav_document(jsonb) CASCADE;
DROP FUNCTION IF EXISTS search_miljokrav_documents(jsonb) CASCADE;
DROP FUNCTION IF EXISTS list_miljokrav_documents(jsonb) CASCADE;
DROP FUNCTION IF EXISTS store_knowledge_document(jsonb) CASCADE;
DROP FUNCTION IF EXISTS search_knowledge_documents(jsonb) CASCADE;
DROP FUNCTION IF EXISTS list_knowledge_documents(jsonb) CASCADE;

-- Drop assessment functions
DROP FUNCTION IF EXISTS save_environmental_assessment(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_oslomodell_assessment(jsonb) CASCADE;
DROP FUNCTION IF EXISTS get_assessment_by_procurement(jsonb) CASCADE;

-- Drop core functions
DROP FUNCTION IF EXISTS create_procurement(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_triage_result(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_triage(jsonb) CASCADE; -- Alias for compatibility
DROP FUNCTION IF EXISTS set_procurement_status(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_protocol(jsonb) CASCADE;
DROP FUNCTION IF EXISTS log_execution(jsonb) CASCADE;

-- Drop core tables
DROP TABLE IF EXISTS gateway_acl_config CASCADE;
DROP TABLE IF EXISTS gateway_service_catalog CASCADE;
DROP TABLE IF EXISTS protocols CASCADE;
DROP TABLE IF EXISTS triage_results CASCADE;
DROP TABLE IF EXISTS procurements CASCADE;
DROP TABLE IF EXISTS executions CASCADE;

-- ========================================
-- STEP 2: ENSURE EXTENSIONS
-- ========================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- STEP 3: CREATE CORE APPLICATION TABLES
-- ========================================

CREATE TABLE procurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    value INTEGER NOT NULL,
    description TEXT,
    category TEXT,
    duration_months INTEGER,
    includes_construction BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE triage_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    -- ENDRING: Bytter til norske verdier for å matche Pydantic-modellene
    color TEXT NOT NULL CHECK (color IN ('GRØNN', 'GUL', 'RØD')),
    reasoning TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    risk_factors JSONB DEFAULT '[]'::jsonb,
    mitigation_measures JSONB DEFAULT '[]'::jsonb,
    requires_special_attention BOOLEAN DEFAULT FALSE,
    escalation_recommended BOOLEAN DEFAULT FALSE,
    assessed_by TEXT DEFAULT 'triage_agent',
    assessment_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(procurement_id)
);

CREATE TABLE protocols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    action JSONB NOT NULL,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- STEP 4: CREATE ASSESSMENT TABLES
-- ========================================

CREATE TABLE environmental_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    procurement_name TEXT NOT NULL,
    
    -- Core assessment fields
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    assessed_by TEXT DEFAULT 'environmental_agent',
    assessment_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Environmental specific fields
    environmental_risk TEXT CHECK (environmental_risk IN ('lav', 'middels', 'høy')),
    climate_impact_assessed BOOLEAN DEFAULT TRUE,
    
    -- Requirements as JSONB arrays
    applied_requirements JSONB DEFAULT '[]'::jsonb,
    transport_requirements JSONB DEFAULT '[]'::jsonb,
    exceptions_recommended JSONB DEFAULT '[]'::jsonb,
    
    -- Flags and booleans
    minimum_biofuel_required BOOLEAN DEFAULT FALSE,
    market_dialogue_recommended BOOLEAN DEFAULT FALSE,
    
    -- Structured data as JSONB
    important_deadlines JSONB DEFAULT '{}'::jsonb,
    documentation_requirements JSONB DEFAULT '[]'::jsonb,
    follow_up_points JSONB DEFAULT '[]'::jsonb,
    award_criteria_recommended JSONB DEFAULT '[]'::jsonb,
    
    -- Common assessment fields
    recommendations JSONB DEFAULT '[]'::jsonb,
    warnings JSONB DEFAULT '[]'::jsonb,
    information_gaps JSONB DEFAULT '[]'::jsonb,
    context_documents_used JSONB DEFAULT '[]'::jsonb,
    confidence_factors JSONB DEFAULT '{}'::jsonb,
    
    -- Full assessment data backup
    assessment_data JSONB NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(procurement_id)
);

CREATE TABLE oslomodell_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    procurement_name TEXT NOT NULL,
    
    -- Core assessment fields
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    assessed_by TEXT DEFAULT 'oslomodell_agent',
    assessment_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Risk assessments
    crime_risk_assessment TEXT CHECK (crime_risk_assessment IN ('høy', 'moderat', 'lav')),
    dd_risk_assessment TEXT CHECK (dd_risk_assessment IN ('høy', 'moderat', 'lav')),
    social_dumping_risk TEXT CHECK (social_dumping_risk IN ('høy', 'moderat', 'lav')),
    
    -- Subcontractor info
    subcontractor_levels INTEGER CHECK (subcontractor_levels >= 0 AND subcontractor_levels <= 2),
    subcontractor_justification TEXT,
    
    -- Requirements as JSONB
    required_requirements JSONB DEFAULT '[]'::jsonb,
    apprenticeship_requirement JSONB DEFAULT '{}'::jsonb,
    
    -- Due diligence
    due_diligence_requirement TEXT CHECK (due_diligence_requirement IN ('A', 'B', 'Ikke påkrevd')),
    
    -- Oslo specific metadata
    applicable_instruction_points JSONB DEFAULT '[]'::jsonb,
    identified_risk_areas JSONB DEFAULT '[]'::jsonb,
    
    -- Common assessment fields
    recommendations JSONB DEFAULT '[]'::jsonb,
    warnings JSONB DEFAULT '[]'::jsonb,
    information_gaps JSONB DEFAULT '[]'::jsonb,
    context_documents_used JSONB DEFAULT '[]'::jsonb,
    confidence_factors JSONB DEFAULT '{}'::jsonb,
    
    -- Full assessment data backup
    assessment_data JSONB NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(procurement_id)
);

-- ========================================
-- STEP 5: CREATE KNOWLEDGE TABLES
-- ========================================

CREATE TABLE oslomodell_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE miljokrav_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for vector similarity search
CREATE INDEX idx_oslomodell_embedding ON oslomodell_knowledge USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_miljokrav_embedding ON miljokrav_knowledge USING ivfflat (embedding vector_cosine_ops);

-- ========================================
-- STEP 6: CREATE GATEWAY CONFIGURATION TABLES
-- ========================================

CREATE TABLE gateway_service_catalog (
    service_name TEXT NOT NULL,
    service_type TEXT NOT NULL,
    function_key TEXT NOT NULL,
    sql_function_name TEXT NOT NULL,
    function_metadata JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (service_name, function_key)
);

CREATE TABLE gateway_acl_config (
    agent_id TEXT NOT NULL,
    allowed_method TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (agent_id, allowed_method)
);

-- ========================================
-- STEP 7: CREATE CORE FUNCTIONS
-- ========================================

-- Create procurement
CREATE OR REPLACE FUNCTION create_procurement(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO procurements (name, value, description, category, duration_months, includes_construction)
    VALUES (
        input_data->>'name',
        (input_data->>'value')::INTEGER,
        input_data->>'description',
        input_data->>'category',
        (input_data->>'duration_months')::INTEGER,
        COALESCE((input_data->>'includes_construction')::BOOLEAN, FALSE)
    )
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'procurementId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$;

-- Save triage result with extended fields
CREATE OR REPLACE FUNCTION save_triage_result(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO triage_results (
        procurement_id, 
        color, 
        reasoning, 
        confidence,
        risk_factors,
        mitigation_measures,
        requires_special_attention,
        escalation_recommended,
        assessed_by,
        assessment_date
    )
    VALUES (
        (input_data->>'procurementId')::UUID,
        input_data->>'color',
        input_data->>'reasoning',
        (input_data->>'confidence')::FLOAT,
        COALESCE(input_data->'riskFactors', '[]'::jsonb),
        COALESCE(input_data->'mitigationMeasures', '[]'::jsonb),
        COALESCE((input_data->>'requiresSpecialAttention')::BOOLEAN, FALSE),
        COALESCE((input_data->>'escalationRecommended')::BOOLEAN, FALSE),
        COALESCE(input_data->>'assessedBy', 'triage_agent'),
        COALESCE((input_data->>'assessmentDate')::TIMESTAMPTZ, NOW())
    )
    ON CONFLICT (procurement_id) DO UPDATE SET
        color = EXCLUDED.color,
        reasoning = EXCLUDED.reasoning,
        confidence = EXCLUDED.confidence,
        risk_factors = EXCLUDED.risk_factors,
        mitigation_measures = EXCLUDED.mitigation_measures,
        requires_special_attention = EXCLUDED.requires_special_attention,
        escalation_recommended = EXCLUDED.escalation_recommended,
        assessed_by = EXCLUDED.assessed_by,
        assessment_date = EXCLUDED.assessment_date,
        updated_at = NOW()
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'message', 'Triage result saved',
        'triageId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$;

-- Create alias for save_triage pointing to save_triage_result
-- This ensures compatibility with both naming conventions
CREATE OR REPLACE FUNCTION save_triage(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $
BEGIN
    -- Simply call save_triage_result with the same parameters
    RETURN save_triage_result(input_data);
END;
$;

-- Set procurement status
CREATE OR REPLACE FUNCTION set_procurement_status(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE procurements
    SET status = input_data->>'status',
        updated_at = NOW()
    WHERE id = (input_data->>'procurementId')::UUID;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'message', 'Status updated'
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Save protocol
CREATE OR REPLACE FUNCTION save_protocol(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO protocols (procurement_id, content, confidence)
    VALUES (
        (input_data->>'procurementId')::UUID,
        input_data->>'content',
        (input_data->>'confidence')::FLOAT
    )
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'protocolId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Log execution
CREATE OR REPLACE FUNCTION log_execution(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO executions (session_id, action, result)
    VALUES (
        input_data->>'sessionId',
        input_data->'action',
        input_data->'result'
    )
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'executionId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- ========================================
-- STEP 8: CREATE ASSESSMENT FUNCTIONS
-- ========================================

-- Save environmental assessment with rich data
CREATE OR REPLACE FUNCTION save_environmental_assessment(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $
DECLARE
    v_id UUID;
    v_assessment_data JSONB;
BEGIN
    -- Build complete assessment data from input
    v_assessment_data := input_data->'assessmentData';
    
    INSERT INTO environmental_assessments (
        procurement_id,
        procurement_name,
        confidence,
        assessed_by,
        assessment_date,
        environmental_risk,
        climate_impact_assessed,
        applied_requirements,
        transport_requirements,
        exceptions_recommended,
        minimum_biofuel_required,
        market_dialogue_recommended,
        important_deadlines,
        documentation_requirements,
        follow_up_points,
        award_criteria_recommended,
        recommendations,
        warnings,
        information_gaps,
        context_documents_used,
        confidence_factors,
        assessment_data
    )
    VALUES (
        (input_data->>'procurementId')::UUID,
        COALESCE(v_assessment_data->>'procurement_name', input_data->>'procurementName', ''),
        COALESCE((v_assessment_data->>'confidence')::FLOAT, 0.5),
        COALESCE(v_assessment_data->>'assessed_by', 'environmental_agent'),
        COALESCE((v_assessment_data->>'assessment_date')::TIMESTAMPTZ, NOW()),
        v_assessment_data->>'environmental_risk',
        COALESCE((v_assessment_data->>'climate_impact_assessed')::BOOLEAN, TRUE),
        COALESCE(v_assessment_data->'applied_requirements', '[]'::jsonb),
        COALESCE(v_assessment_data->'transport_requirements', '[]'::jsonb),
        COALESCE(v_assessment_data->'exceptions_recommended', '[]'::jsonb),
        COALESCE((v_assessment_data->>'minimum_biofuel_required')::BOOLEAN, FALSE),
        COALESCE((v_assessment_data->>'market_dialogue_recommended')::BOOLEAN, FALSE),
        COALESCE(v_assessment_data->'important_deadlines', '{}'::jsonb),
        COALESCE(v_assessment_data->'documentation_requirements', '[]'::jsonb),
        COALESCE(v_assessment_data->'follow_up_points', '[]'::jsonb),
        COALESCE(v_assessment_data->'award_criteria_recommended', '[]'::jsonb),
        COALESCE(v_assessment_data->'recommendations', '[]'::jsonb),
        COALESCE(v_assessment_data->'warnings', '[]'::jsonb),
        COALESCE(v_assessment_data->'information_gaps', '[]'::jsonb),
        COALESCE(v_assessment_data->'context_documents_used', '[]'::jsonb),
        COALESCE(v_assessment_data->'confidence_factors', '{}'::jsonb),
        v_assessment_data
    )
    ON CONFLICT (procurement_id) DO UPDATE SET
        procurement_name = EXCLUDED.procurement_name,
        confidence = EXCLUDED.confidence,
        assessed_by = EXCLUDED.assessed_by,
        assessment_date = EXCLUDED.assessment_date,
        environmental_risk = EXCLUDED.environmental_risk,
        climate_impact_assessed = EXCLUDED.climate_impact_assessed,
        applied_requirements = EXCLUDED.applied_requirements,
        transport_requirements = EXCLUDED.transport_requirements,
        exceptions_recommended = EXCLUDED.exceptions_recommended,
        minimum_biofuel_required = EXCLUDED.minimum_biofuel_required,
        market_dialogue_recommended = EXCLUDED.market_dialogue_recommended,
        important_deadlines = EXCLUDED.important_deadlines,
        documentation_requirements = EXCLUDED.documentation_requirements,
        follow_up_points = EXCLUDED.follow_up_points,
        award_criteria_recommended = EXCLUDED.award_criteria_recommended,
        recommendations = EXCLUDED.recommendations,
        warnings = EXCLUDED.warnings,
        information_gaps = EXCLUDED.information_gaps,
        context_documents_used = EXCLUDED.context_documents_used,
        confidence_factors = EXCLUDED.confidence_factors,
        assessment_data = EXCLUDED.assessment_data,
        updated_at = NOW()
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'message', 'Environmental assessment saved',
        'assessmentId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$;

-- Save Oslomodell assessment with rich data
CREATE OR REPLACE FUNCTION save_oslomodell_assessment(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $
DECLARE
    v_id UUID;
    v_assessment_data JSONB;
BEGIN
    -- Build complete assessment data from input
    v_assessment_data := input_data->'assessmentData';

    IF v_assessment_data IS NULL OR jsonb_typeof(v_assessment_data) != 'object' THEN
        RAISE EXCEPTION 'Input parameter must be a JSON object with a root key "assessmentData".';
    END IF;
    IF NOT v_assessment_data ? 'procurement_id' THEN
        RAISE EXCEPTION 'Missing required field "procurement_id" inside assessmentData.';
    END IF;
    
    INSERT INTO oslomodell_assessments (
        procurement_id,
        procurement_name,
        confidence,
        assessed_by,
        assessment_date,
        crime_risk_assessment,
        dd_risk_assessment,
        social_dumping_risk,
        subcontractor_levels,
        subcontractor_justification,
        required_requirements,
        apprenticeship_requirement,
        due_diligence_requirement,
        applicable_instruction_points,
        identified_risk_areas,
        recommendations,
        warnings,
        information_gaps,
        context_documents_used,
        confidence_factors,
        assessment_data
    )
    VALUES (
        (input_data->>'procurementId')::UUID,
        COALESCE(v_assessment_data->>'procurement_name', input_data->>'procurementName', ''),
        COALESCE((v_assessment_data->>'confidence')::FLOAT, 0.5),
        COALESCE(v_assessment_data->>'assessed_by', 'oslomodell_agent'),
        COALESCE((v_assessment_data->>'assessment_date')::TIMESTAMPTZ, NOW()),
        v_assessment_data->>'crime_risk_assessment',
        v_assessment_data->>'dd_risk_assessment',
        v_assessment_data->>'social_dumping_risk',
        (v_assessment_data->>'subcontractor_levels')::INTEGER,
        v_assessment_data->>'subcontractor_justification',
        COALESCE(v_assessment_data->'required_requirements', '[]'::jsonb),
        COALESCE(v_assessment_data->'apprenticeship_requirement', '{}'::jsonb),
        v_assessment_data->>'due_diligence_requirement',
        COALESCE(v_assessment_data->'applicable_instruction_points', '[]'::jsonb),
        COALESCE(v_assessment_data->'identified_risk_areas', '[]'::jsonb),
        COALESCE(v_assessment_data->'recommendations', '[]'::jsonb),
        COALESCE(v_assessment_data->'warnings', '[]'::jsonb),
        COALESCE(v_assessment_data->'information_gaps', '[]'::jsonb),
        COALESCE(v_assessment_data->'context_documents_used', '[]'::jsonb),
        COALESCE(v_assessment_data->'confidence_factors', '{}'::jsonb),
        v_assessment_data
    )
    ON CONFLICT (procurement_id) DO UPDATE SET
        procurement_name = EXCLUDED.procurement_name,
        confidence = EXCLUDED.confidence,
        assessed_by = EXCLUDED.assessed_by,
        assessment_date = EXCLUDED.assessment_date,
        crime_risk_assessment = EXCLUDED.crime_risk_assessment,
        dd_risk_assessment = EXCLUDED.dd_risk_assessment,
        social_dumping_risk = EXCLUDED.social_dumping_risk,
        subcontractor_levels = EXCLUDED.subcontractor_levels,
        subcontractor_justification = EXCLUDED.subcontractor_justification,
        required_requirements = EXCLUDED.required_requirements,
        apprenticeship_requirement = EXCLUDED.apprenticeship_requirement,
        due_diligence_requirement = EXCLUDED.due_diligence_requirement,
        applicable_instruction_points = EXCLUDED.applicable_instruction_points,
        identified_risk_areas = EXCLUDED.identified_risk_areas,
        recommendations = EXCLUDED.recommendations,
        warnings = EXCLUDED.warnings,
        information_gaps = EXCLUDED.information_gaps,
        context_documents_used = EXCLUDED.context_documents_used,
        confidence_factors = EXCLUDED.confidence_factors,
        assessment_data = EXCLUDED.assessment_data,
        updated_at = NOW()
    RETURNING id INTO v_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'message', 'Oslomodell assessment saved',
        'assessmentId', v_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$;

-- ========================================
-- STEP 9: CREATE OSLOMODELL KNOWLEDGE FUNCTIONS
-- ========================================

-- Store Oslomodell document
CREATE OR REPLACE FUNCTION store_knowledge_document(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO oslomodell_knowledge (document_id, content, embedding, metadata)
    VALUES (
        input_data->>'documentId',
        input_data->>'content',
        (input_data->'embedding')::vector,
        COALESCE(input_data->'metadata', '{}'::jsonb)
    )
    ON CONFLICT (document_id) DO UPDATE SET
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documentId', input_data->>'documentId'
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Search Oslomodell documents
CREATE OR REPLACE FUNCTION search_knowledge_documents(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_results jsonb;
    v_threshold FLOAT := COALESCE((input_data->>'threshold')::FLOAT, 0.7);
    v_limit INTEGER := COALESCE((input_data->>'limit')::INTEGER, 10);
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'documentId', document_id,
            'content', content,
            'metadata', metadata,
            'similarity', similarity
        ) ORDER BY similarity DESC
    ) INTO v_results
    FROM (
        SELECT 
            document_id,
            content,
            metadata,
            1 - (embedding <=> (input_data->'queryEmbedding')::vector) AS similarity
        FROM oslomodell_knowledge
        WHERE 1 - (embedding <=> (input_data->'queryEmbedding')::vector) >= v_threshold
        ORDER BY similarity DESC
        LIMIT v_limit
    ) AS matches;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'results', COALESCE(v_results, '[]'::jsonb)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- List Oslomodell documents
CREATE OR REPLACE FUNCTION list_knowledge_documents(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_results jsonb;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'documentId', document_id,
            'metadata', metadata,
            'contentLength', length(content),
            'createdAt', created_at
        ) ORDER BY created_at DESC
    ) INTO v_results
    FROM oslomodell_knowledge;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documents', COALESCE(v_results, '[]'::jsonb),
        'total', COALESCE(jsonb_array_length(v_results), 0)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- ========================================
-- STEP 10: CREATE MILJOKRAV KNOWLEDGE FUNCTIONS
-- ========================================

-- Store Miljokrav document
CREATE OR REPLACE FUNCTION store_miljokrav_document(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO miljokrav_knowledge (document_id, content, embedding, metadata)
    VALUES (
        input_data->>'documentId',
        input_data->>'content',
        (input_data->'embedding')::vector,
        COALESCE(input_data->'metadata', '{}'::jsonb)
    )
    ON CONFLICT (document_id) DO UPDATE SET
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documentId', input_data->>'documentId'
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Search Miljokrav documents
CREATE OR REPLACE FUNCTION search_miljokrav_documents(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_results jsonb;
    v_threshold FLOAT := COALESCE((input_data->>'threshold')::FLOAT, 0.7);
    v_limit INTEGER := COALESCE((input_data->>'limit')::INTEGER, 10);
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'documentId', document_id,
            'content', content,
            'metadata', metadata,
            'similarity', similarity
        ) ORDER BY similarity DESC
    ) INTO v_results
    FROM (
        SELECT 
            document_id,
            content,
            metadata,
            1 - (embedding <=> (input_data->'queryEmbedding')::vector) AS similarity
        FROM miljokrav_knowledge
        WHERE 1 - (embedding <=> (input_data->'queryEmbedding')::vector) >= v_threshold
        ORDER BY similarity DESC
        LIMIT v_limit
    ) AS matches;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'results', COALESCE(v_results, '[]'::jsonb)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- List Miljokrav documents
CREATE OR REPLACE FUNCTION list_miljokrav_documents(input_data jsonb)
RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    v_results jsonb;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'documentId', document_id,
            'metadata', metadata,
            'contentLength', length(content),
            'createdAt', created_at
        ) ORDER BY created_at DESC
    ) INTO v_results
    FROM miljokrav_knowledge;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documents', COALESCE(v_results, '[]'::jsonb),
        'total', COALESCE(jsonb_array_length(v_results), 0)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- ========================================
-- STEP 11: POPULATE GATEWAY SERVICE CATALOG
-- ========================================

-- Register all functions in the service catalog
INSERT INTO gateway_service_catalog (service_name, service_type, function_key, sql_function_name, function_metadata)
VALUES
    -- Core procurement functions
    ('database', 'postgres_rpc', 'create_procurement', 'create_procurement',
     '{"description": "Creates a new procurement record", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "integer"}, "description": {"type": "string"}, "category": {"type": "string"}, "duration_months": {"type": "integer"}, "includes_construction": {"type": "boolean"}}, "required": ["name", "value"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_triage_result', 'save_triage_result',
     '{"description": "Saves enriched triage assessment result", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "color": {"type": "string"}, "reasoning": {"type": "string"}, "confidence": {"type": "number"}, "riskFactors": {"type": "array", "items": {"type": "string"}}, "mitigationMeasures": {"type": "array", "items": {"type": "string"}}, "requiresSpecialAttention": {"type": "boolean"}, "escalationRecommended": {"type": "boolean"}, "assessedBy": {"type": "string"}, "assessmentDate": {"type": "string", "format": "date-time"}}, "required": ["procurementId", "color", "reasoning", "confidence"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_triage', 'save_triage',
     '{"description": "Alias for save_triage_result", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "color": {"type": "string"}, "reasoning": {"type": "string"}, "confidence": {"type": "number"}, "riskFactors": {"type": "array", "items": {"type": "string"}}, "mitigationMeasures": {"type": "array", "items": {"type": "string"}}, "requiresSpecialAttention": {"type": "boolean"}, "escalationRecommended": {"type": "boolean"}, "assessedBy": {"type": "string"}, "assessmentDate": {"type": "string", "format": "date-time"}}, "required": ["procurementId", "color", "reasoning", "confidence"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'set_procurement_status', 'set_procurement_status',
     '{"description": "Updates procurement status", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "status": {"type": "string"}}, "required": ["procurementId", "status"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_protocol', 'save_protocol',
     '{"description": "Saves protocol content", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "content": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["procurementId", "content", "confidence"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'log_execution', 'log_execution',
     '{"description": "Logs execution step", "input_schema": {"type": "object", "properties": {"sessionId": {"type": "string"}, "action": {"type": "object"}, "result": {"type": "object"}}, "required": ["sessionId", "action"]}}'::jsonb),
    
    -- Assessment functions with rich data models
    ('database', 'postgres_rpc', 'save_environmental_assessment', 'save_environmental_assessment',
     '{"description": "Saves enriched environmental assessment result", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "procurementName": {"type": "string"}, "assessmentData": {"type": "object", "properties": {"environmental_risk": {"type": "string", "enum": ["lav", "middels", "høy"]}, "climate_impact_assessed": {"type": "boolean"}, "applied_requirements": {"type": "array"}, "transport_requirements": {"type": "array"}, "exceptions_recommended": {"type": "array"}, "minimum_biofuel_required": {"type": "boolean"}, "market_dialogue_recommended": {"type": "boolean"}, "important_deadlines": {"type": "object"}, "documentation_requirements": {"type": "array"}, "follow_up_points": {"type": "array"}, "award_criteria_recommended": {"type": "array"}, "recommendations": {"type": "array"}, "warnings": {"type": "array"}, "confidence": {"type": "number"}}}}, "required": ["procurementId", "assessmentData"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_oslomodell_assessment', 'save_oslomodell_assessment',
     '{"description": "Saves enriched Oslomodell assessment result", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "procurementName": {"type": "string"}, "assessmentData": {"type": "object", "properties": {"crime_risk_assessment": {"type": "string", "enum": ["høy", "moderat", "lav"]}, "dd_risk_assessment": {"type": "string", "enum": ["høy", "moderat", "lav"]}, "social_dumping_risk": {"type": "string", "enum": ["høy", "moderat", "lav"]}, "subcontractor_levels": {"type": "integer", "minimum": 0, "maximum": 2}, "subcontractor_justification": {"type": "string"}, "required_requirements": {"type": "array"}, "apprenticeship_requirement": {"type": "object"}, "due_diligence_requirement": {"type": "string", "enum": ["A", "B", "Ikke påkrevd"]}, "applicable_instruction_points": {"type": "array"}, "identified_risk_areas": {"type": "array"}, "recommendations": {"type": "array"}, "warnings": {"type": "array"}, "confidence": {"type": "number"}}}}, "required": ["procurementId", "assessmentData"]}}'::jsonb),
    
    -- Oslomodell knowledge functions
    ('database', 'postgres_rpc', 'store_knowledge_document', 'store_knowledge_document',
     '{"description": "Stores an Oslomodell knowledge document with embedding", "input_schema": {"type": "object", "properties": {"documentId": {"type": "string"}, "content": {"type": "string"}, "embedding": {"type": "array", "items": {"type": "number"}}, "metadata": {"type": "object"}}, "required": ["documentId", "content", "embedding"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'search_knowledge_documents', 'search_knowledge_documents',
     '{"description": "Searches Oslomodell knowledge documents using vector similarity", "input_schema": {"type": "object", "properties": {"queryEmbedding": {"type": "array", "items": {"type": "number"}}, "threshold": {"type": "number", "minimum": 0, "maximum": 1}, "limit": {"type": "integer", "minimum": 1}, "metadataFilter": {"type": "object"}}, "required": ["queryEmbedding"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'list_knowledge_documents', 'list_knowledge_documents',
     '{"description": "Lists all Oslomodell knowledge documents", "input_schema": {"type": "object", "properties": {}}}'::jsonb),
    
    -- Miljokrav knowledge functions
    ('database', 'postgres_rpc', 'store_miljokrav_document', 'store_miljokrav_document',
     '{"description": "Stores a Miljokrav knowledge document with embedding", "input_schema": {"type": "object", "properties": {"documentId": {"type": "string"}, "content": {"type": "string"}, "embedding": {"type": "array", "items": {"type": "number"}}, "metadata": {"type": "object"}}, "required": ["documentId", "content", "embedding"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'search_miljokrav_documents', 'search_miljokrav_documents',
     '{"description": "Searches Miljokrav knowledge documents using vector similarity", "input_schema": {"type": "object", "properties": {"queryEmbedding": {"type": "array", "items": {"type": "number"}}, "threshold": {"type": "number", "minimum": 0, "maximum": 1}, "limit": {"type": "integer", "minimum": 1}, "metadataFilter": {"type": "object"}}, "required": ["queryEmbedding"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'list_miljokrav_documents', 'list_miljokrav_documents',
     '{"description": "Lists all Miljokrav knowledge documents", "input_schema": {"type": "object", "properties": {}}}'::jsonb)

ON CONFLICT (service_name, function_key) DO UPDATE SET
    sql_function_name = EXCLUDED.sql_function_name,
    function_metadata = EXCLUDED.function_metadata,
    is_active = true;

-- ========================================
-- STEP 12: POPULATE GATEWAY ACL CONFIG
-- ========================================

-- Grant full access to reasoning_orchestrator for ALL functions
INSERT INTO gateway_acl_config (agent_id, allowed_method)
VALUES
    -- Reasoning orchestrator needs everything
    ('reasoning_orchestrator', 'database.create_procurement'),
    ('reasoning_orchestrator', 'database.save_triage_result'),
    ('reasoning_orchestrator', 'database.save_triage'),
    ('reasoning_orchestrator', 'database.set_procurement_status'),
    ('reasoning_orchestrator', 'database.save_protocol'),
    ('reasoning_orchestrator', 'database.log_execution'),
    ('reasoning_orchestrator', 'database.save_environmental_assessment'),
    ('reasoning_orchestrator', 'database.save_oslomodell_assessment'),
    ('reasoning_orchestrator', 'database.store_knowledge_document'),
    ('reasoning_orchestrator', 'database.search_knowledge_documents'),
    ('reasoning_orchestrator', 'database.list_knowledge_documents'),
    ('reasoning_orchestrator', 'database.store_miljokrav_document'),
    ('reasoning_orchestrator', 'database.search_miljokrav_documents'),
    ('reasoning_orchestrator', 'database.list_miljokrav_documents'),
    
    -- Triage agent permissions
    ('triage_agent', 'database.save_triage_result'),
    ('triage_agent', 'database.save_triage'),
    
    -- Protocol agent permissions
    ('protocol_agent', 'database.save_protocol'),
    
    -- Oslomodell agent permissions
    ('oslomodell_agent', 'database.search_knowledge_documents'),
    ('oslomodell_agent', 'database.list_knowledge_documents'),
    ('oslomodell_agent', 'database.save_oslomodell_assessment'),
    
    -- Environmental agent (miljokrav) permissions
    ('environmental_agent', 'database.search_miljokrav_documents'),
    ('environmental_agent', 'database.list_miljokrav_documents'),
    ('environmental_agent', 'database.save_environmental_assessment'),
    
    -- Knowledge ingester permissions (for loading data)
    ('knowledge_ingester', 'database.store_knowledge_document'),
    ('knowledge_ingester', 'database.search_knowledge_documents'),
    ('knowledge_ingester', 'database.list_knowledge_documents'),
    ('knowledge_ingester', 'database.store_miljokrav_document'),
    ('knowledge_ingester', 'database.search_miljokrav_documents'),
    ('knowledge_ingester', 'database.list_miljokrav_documents')

ON CONFLICT (agent_id, allowed_method) DO UPDATE SET
    is_active = true;

-- ========================================
-- STEP 13: VERIFICATION
-- ========================================

-- Output verification information
DO $$
DECLARE
    v_tables_count INTEGER;
    v_functions_count INTEGER;
    v_catalog_count INTEGER;
    v_acl_count INTEGER;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO v_tables_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('procurements', 'triage_results', 'protocols', 'executions', 
                       'environmental_assessments', 'oslomodell_assessments',
                       'oslomodell_knowledge', 'miljokrav_knowledge',
                       'gateway_service_catalog', 'gateway_acl_config');
    
    -- Count functions
    SELECT COUNT(*) INTO v_functions_count
    FROM information_schema.routines
    WHERE routine_schema = 'public'
    AND routine_type = 'FUNCTION';
    
    -- Count service catalog entries
    SELECT COUNT(*) INTO v_catalog_count
    FROM gateway_service_catalog
    WHERE is_active = true;
    
    -- Count ACL entries
    SELECT COUNT(*) INTO v_acl_count
    FROM gateway_acl_config
    WHERE is_active = true;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'DATABASE SETUP COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables created: %', v_tables_count;
    RAISE NOTICE 'Functions created: %', v_functions_count;
    RAISE NOTICE 'Service catalog entries: %', v_catalog_count;
    RAISE NOTICE 'ACL rules configured: %', v_acl_count;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RICH DATA MODELS ENABLED:';
    RAISE NOTICE '✓ Triage: risk_factors, mitigation_measures, flags';
    RAISE NOTICE '✓ Environmental: transport_requirements, deadlines, criteria';
    RAISE NOTICE '✓ Oslomodell: crime/dd/social risk, requirements, apprentices';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Reasoning orchestrator has full access to all % functions', v_catalog_count;
    RAISE NOTICE '========================================';
END $$;