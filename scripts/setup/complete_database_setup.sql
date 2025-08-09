-- complete_database_setup.sql
-- CONSOLIDATED database setup for entire Procurement Assistant system
-- Includes: Core tables, Oslomodell, Miljokrav, Gateway services, ACL, and new assessment tables
-- Run this for a complete, fresh setup

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
    category TEXT, -- New field for category
    duration_months INTEGER, -- New field for duration
    includes_construction BOOLEAN DEFAULT FALSE, -- New field
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE triage_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID UNIQUE NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    color TEXT NOT NULL CHECK (color IN ('GRØNN', 'GUL', 'RØD')),
    reasoning TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE protocols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    action JSONB NOT NULL,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- STEP 4: CREATE GATEWAY MANAGEMENT TABLES
-- ========================================

CREATE TABLE gateway_service_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name TEXT NOT NULL,
    service_type TEXT NOT NULL DEFAULT 'postgres_rpc',
    function_key TEXT NOT NULL,
    sql_function_name TEXT NOT NULL,
    function_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(service_name, function_key)
);

CREATE TABLE gateway_acl_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    allowed_method TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(agent_id, allowed_method)
);

-- ========================================
-- STEP 5: CREATE ASSESSMENT TABLES (NEW)
-- ========================================

CREATE TABLE environmental_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    assessed_by TEXT NOT NULL DEFAULT 'environmental_agent',
    environmental_risk TEXT NOT NULL CHECK (environmental_risk IN ('lav', 'middels', 'høy')),
    climate_impact_assessed BOOLEAN DEFAULT TRUE,
    transport_requirements JSONB DEFAULT '[]',
    exceptions_recommended JSONB DEFAULT '[]',
    minimum_biofuel_required BOOLEAN DEFAULT FALSE,
    important_deadlines JSONB DEFAULT '{}',
    documentation_requirements TEXT[],
    follow_up_points TEXT[],
    market_dialogue_recommended BOOLEAN DEFAULT FALSE,
    award_criteria_recommended TEXT[],
    recommendations TEXT[],
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    assessment_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    context_documents_used TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(procurement_id, assessed_by)
);

CREATE TABLE oslomodell_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    assessed_by TEXT NOT NULL DEFAULT 'oslomodell_agent',
    applicable_requirements JSONB DEFAULT '[]',
    threshold_requirements JSONB DEFAULT '[]',
    recommendation TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    assessment_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    context_documents_used TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(procurement_id, assessed_by)
);

-- ========================================
-- STEP 6: CREATE OSLOMODELL KNOWLEDGE TABLES
-- ========================================

CREATE TABLE oslomodell_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX oslomodell_knowledge_embedding_idx 
ON oslomodell_knowledge 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for metadata queries
CREATE INDEX oslomodell_knowledge_metadata_idx 
ON oslomodell_knowledge 
USING gin (metadata);

-- ========================================
-- STEP 7: CREATE MILJOKRAV KNOWLEDGE TABLES
-- ========================================

CREATE TABLE miljokrav_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX miljokrav_knowledge_embedding_idx 
ON miljokrav_knowledge 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for metadata queries
CREATE INDEX miljokrav_knowledge_metadata_idx 
ON miljokrav_knowledge 
USING gin (metadata);

-- ========================================
-- STEP 8: CREATE CORE RPC FUNCTIONS
-- ========================================

-- Function to create procurement
CREATE OR REPLACE FUNCTION create_procurement(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_procurement_id UUID;
BEGIN
    INSERT INTO procurements (name, value, description, category, duration_months, includes_construction)
    VALUES (
        params->>'name',
        (params->>'value')::integer,
        params->>'description',
        params->>'category',
        (params->>'duration_months')::integer,
        COALESCE((params->>'includes_construction')::boolean, FALSE)
    )
    RETURNING id INTO v_procurement_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'procurementId', v_procurement_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Function to save triage result
CREATE OR REPLACE FUNCTION save_triage_result(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_triage_id UUID;
BEGIN
    INSERT INTO triage_results (procurement_id, color, reasoning, confidence)
    VALUES (
        (params->>'procurementId')::uuid,
        params->>'color',
        params->>'reasoning',
        (params->>'confidence')::float
    )
    ON CONFLICT (procurement_id) DO UPDATE SET
        color = EXCLUDED.color,
        reasoning = EXCLUDED.reasoning,
        confidence = EXCLUDED.confidence,
        updated_at = NOW()
    RETURNING id INTO v_triage_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'triageId', v_triage_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Function to set procurement status
CREATE OR REPLACE FUNCTION set_procurement_status(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    UPDATE procurements
    SET 
        status = params->>'status',
        updated_at = NOW()
    WHERE id = (params->>'procurementId')::uuid;
    
    RETURN jsonb_build_object('status', 'success');
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Function to save protocol
CREATE OR REPLACE FUNCTION save_protocol(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_protocol_id UUID;
BEGIN
    INSERT INTO protocols (procurement_id, content, confidence)
    VALUES (
        (params->>'procurementId')::uuid,
        params->>'content',
        (params->>'confidence')::float
    )
    RETURNING id INTO v_protocol_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'protocolId', v_protocol_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Function to log execution
CREATE OR REPLACE FUNCTION log_execution(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_execution_id UUID;
BEGIN
    INSERT INTO executions (session_id, action, result)
    VALUES (
        (params->>'sessionId')::uuid,
        params->'action',
        params->'result'
    )
    RETURNING id INTO v_execution_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'executionId', v_execution_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- ========================================
-- STEP 9: CREATE ASSESSMENT RPC FUNCTIONS (NEW)
-- ========================================

-- Function to save environmental assessment
CREATE OR REPLACE FUNCTION save_environmental_assessment(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_assessment_id UUID;
BEGIN
    INSERT INTO environmental_assessments (
        procurement_id,
        assessed_by,
        environmental_risk,
        climate_impact_assessed,
        transport_requirements,
        exceptions_recommended,
        minimum_biofuel_required,
        important_deadlines,
        documentation_requirements,
        follow_up_points,
        market_dialogue_recommended,
        award_criteria_recommended,
        recommendations,
        confidence,
        context_documents_used
    )
    VALUES (
        (params->>'procurement_id')::uuid,
        COALESCE(params->>'assessed_by', 'environmental_agent'),
        params->>'environmental_risk',
        COALESCE((params->>'climate_impact_assessed')::boolean, TRUE),
        COALESCE(params->'transport_requirements', '[]'::jsonb),
        COALESCE(params->'exceptions_recommended', '[]'::jsonb),
        COALESCE((params->>'minimum_biofuel_required')::boolean, FALSE),
        COALESCE(params->'important_deadlines', '{}'::jsonb),
        ARRAY(SELECT jsonb_array_elements_text(params->'documentation_requirements')),
        ARRAY(SELECT jsonb_array_elements_text(params->'follow_up_points')),
        COALESCE((params->>'market_dialogue_recommended')::boolean, FALSE),
        ARRAY(SELECT jsonb_array_elements_text(params->'award_criteria_recommended')),
        ARRAY(SELECT jsonb_array_elements_text(params->'recommendations')),
        (params->>'confidence')::float,
        ARRAY(SELECT jsonb_array_elements_text(params->'context_documents_used'))
    )
    ON CONFLICT (procurement_id, assessed_by) DO UPDATE SET
        environmental_risk = EXCLUDED.environmental_risk,
        climate_impact_assessed = EXCLUDED.climate_impact_assessed,
        transport_requirements = EXCLUDED.transport_requirements,
        exceptions_recommended = EXCLUDED.exceptions_recommended,
        minimum_biofuel_required = EXCLUDED.minimum_biofuel_required,
        important_deadlines = EXCLUDED.important_deadlines,
        documentation_requirements = EXCLUDED.documentation_requirements,
        follow_up_points = EXCLUDED.follow_up_points,
        market_dialogue_recommended = EXCLUDED.market_dialogue_recommended,
        award_criteria_recommended = EXCLUDED.award_criteria_recommended,
        recommendations = EXCLUDED.recommendations,
        confidence = EXCLUDED.confidence,
        context_documents_used = EXCLUDED.context_documents_used,
        updated_at = NOW()
    RETURNING id INTO v_assessment_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'assessmentId', v_assessment_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- Function to save oslomodell assessment
CREATE OR REPLACE FUNCTION save_oslomodell_assessment(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_assessment_id UUID;
BEGIN
    INSERT INTO oslomodell_assessments (
        procurement_id,
        assessed_by,
        applicable_requirements,
        threshold_requirements,
        recommendation,
        confidence,
        context_documents_used
    )
    VALUES (
        (params->>'procurement_id')::uuid,
        COALESCE(params->>'assessed_by', 'oslomodell_agent'),
        COALESCE(params->'applicable_requirements', '[]'::jsonb),
        COALESCE(params->'threshold_requirements', '[]'::jsonb),
        params->>'recommendation',
        (params->>'confidence')::float,
        ARRAY(SELECT jsonb_array_elements_text(params->'context_documents_used'))
    )
    ON CONFLICT (procurement_id, assessed_by) DO UPDATE SET
        applicable_requirements = EXCLUDED.applicable_requirements,
        threshold_requirements = EXCLUDED.threshold_requirements,
        recommendation = EXCLUDED.recommendation,
        confidence = EXCLUDED.confidence,
        context_documents_used = EXCLUDED.context_documents_used,
        updated_at = NOW()
    RETURNING id INTO v_assessment_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'assessmentId', v_assessment_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM
    );
END;
$$;

-- ========================================
-- STEP 10: CREATE OSLOMODELL RPC FUNCTIONS
-- ========================================

-- Function to store oslomodell knowledge document
CREATE OR REPLACE FUNCTION store_knowledge_document(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_doc_id UUID;
    v_embedding_array float[];
BEGIN
    -- Parse embedding from JSON array to float array
    SELECT array_agg(value::float)::float[]
    INTO v_embedding_array
    FROM jsonb_array_elements_text(params->'embedding');
    
    -- Insert or update document
    INSERT INTO oslomodell_knowledge (document_id, content, embedding, metadata)
    VALUES (
        params->>'documentId',
        params->>'content',
        v_embedding_array::vector,
        COALESCE(params->'metadata', '{}'::jsonb)
    )
    ON CONFLICT (document_id) DO UPDATE SET
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        updated_at = NOW()
    RETURNING id INTO v_doc_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documentId', params->>'documentId',
        'id', v_doc_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM,
        'detail', SQLSTATE
    );
END;
$$;

-- Function to search oslomodell knowledge documents
CREATE OR REPLACE FUNCTION search_knowledge_documents(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_results jsonb;
    v_query_embedding vector;
    v_embedding_array float[];
    v_threshold float;
    v_limit int;
    v_metadata_filter jsonb;
BEGIN
    -- Parse parameters
    v_threshold := COALESCE((params->>'threshold')::float, 0.7);
    v_limit := COALESCE((params->>'limit')::int, 5);
    v_metadata_filter := COALESCE(params->'metadataFilter', '{}'::jsonb);
    
    -- Parse embedding from JSON array to float array then to vector
    SELECT array_agg(value::float)::float[]
    INTO v_embedding_array
    FROM jsonb_array_elements_text(params->'queryEmbedding');
    
    v_query_embedding := v_embedding_array::vector;
    
    -- Perform search
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
            1 - (embedding <=> v_query_embedding) as similarity
        FROM oslomodell_knowledge
        WHERE 
            (v_metadata_filter = '{}'::jsonb OR metadata @> v_metadata_filter)
            AND 1 - (embedding <=> v_query_embedding) > v_threshold
        ORDER BY embedding <=> v_query_embedding
        LIMIT v_limit
    ) AS search_results;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'results', COALESCE(v_results, '[]'::jsonb),
        'count', COALESCE(jsonb_array_length(v_results), 0)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM,
        'detail', SQLSTATE,
        'results', '[]'::jsonb
    );
END;
$$;

-- Function to list oslomodell knowledge documents
CREATE OR REPLACE FUNCTION list_knowledge_documents(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
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
-- STEP 11: CREATE MILJOKRAV RPC FUNCTIONS
-- ========================================

-- Function to store miljokrav document
CREATE OR REPLACE FUNCTION store_miljokrav_document(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_doc_id UUID;
    v_embedding_array float[];
BEGIN
    -- Parse embedding from JSON array to float array
    SELECT array_agg(value::float)::float[]
    INTO v_embedding_array
    FROM jsonb_array_elements_text(params->'embedding');
    
    -- Insert or update document
    INSERT INTO miljokrav_knowledge (document_id, content, embedding, metadata)
    VALUES (
        params->>'documentId',
        params->>'content',
        v_embedding_array::vector,
        COALESCE(params->'metadata', '{}'::jsonb)
    )
    ON CONFLICT (document_id) DO UPDATE SET
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        updated_at = NOW()
    RETURNING id INTO v_doc_id;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'documentId', params->>'documentId',
        'id', v_doc_id
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM,
        'detail', SQLSTATE
    );
END;
$$;

-- Function to search miljokrav documents
CREATE OR REPLACE FUNCTION search_miljokrav_documents(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_results jsonb;
    v_query_embedding vector;
    v_embedding_array float[];
    v_threshold float;
    v_limit int;
    v_metadata_filter jsonb;
BEGIN
    -- Parse parameters
    v_threshold := COALESCE((params->>'threshold')::float, 0.7);
    v_limit := COALESCE((params->>'limit')::int, 5);
    v_metadata_filter := COALESCE(params->'metadataFilter', '{}'::jsonb);
    
    -- Parse embedding
    SELECT array_agg(value::float)::float[]
    INTO v_embedding_array
    FROM jsonb_array_elements_text(params->'queryEmbedding');
    
    v_query_embedding := v_embedding_array::vector;
    
    -- Perform search
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
            1 - (embedding <=> v_query_embedding) as similarity
        FROM miljokrav_knowledge
        WHERE 
            (v_metadata_filter = '{}'::jsonb OR metadata @> v_metadata_filter)
            AND 1 - (embedding <=> v_query_embedding) > v_threshold
        ORDER BY embedding <=> v_query_embedding
        LIMIT v_limit
    ) AS search_results;
    
    RETURN jsonb_build_object(
        'status', 'success',
        'results', COALESCE(v_results, '[]'::jsonb),
        'count', COALESCE(jsonb_array_length(v_results), 0)
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'status', 'error',
        'message', SQLERRM,
        'results', '[]'::jsonb
    );
END;
$$;

-- Function to list miljokrav documents
CREATE OR REPLACE FUNCTION list_miljokrav_documents(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
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
-- STEP 12: POPULATE GATEWAY SERVICE CATALOG
-- ========================================

-- Register all functions
INSERT INTO gateway_service_catalog (service_name, service_type, function_key, sql_function_name, function_metadata)
VALUES
    -- Core procurement functions
    ('database', 'postgres_rpc', 'create_procurement', 'create_procurement',
     '{"description": "Creates a new procurement record", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "integer"}, "description": {"type": "string"}, "category": {"type": "string"}, "duration_months": {"type": "integer"}, "includes_construction": {"type": "boolean"}}, "required": ["name", "value"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_triage_result', 'save_triage_result',
     '{"description": "Saves triage assessment result", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "color": {"type": "string"}, "reasoning": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["procurementId", "color", "reasoning", "confidence"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'set_procurement_status', 'set_procurement_status',
     '{"description": "Updates procurement status", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "status": {"type": "string"}}, "required": ["procurementId", "status"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_protocol', 'save_protocol',
     '{"description": "Saves protocol content", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "content": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["procurementId", "content", "confidence"]}}'::jsonb),
    
    ('database', 'postgres_rpc', 'log_execution', 'log_execution',
     '{"description": "Logs execution step", "input_schema": {"type": "object", "properties": {"sessionId": {"type": "string"}, "action": {"type": "object"}, "result": {"type": "object"}}, "required": ["sessionId", "action"]}}'::jsonb),
    
    -- Assessment functions
    ('database', 'postgres_rpc', 'save_environmental_assessment', 'save_environmental_assessment',
     '{"description": "Saves environmental assessment result", "input_schema": {"type": "object"}}'::jsonb),
    
    ('database', 'postgres_rpc', 'save_oslomodell_assessment', 'save_oslomodell_assessment',
     '{"description": "Saves Oslomodell assessment result", "input_schema": {"type": "object"}}'::jsonb),
    
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
-- STEP 13: POPULATE GATEWAY ACL CONFIG
-- ========================================

-- Grant access to all relevant agents
INSERT INTO gateway_acl_config (agent_id, allowed_method)
VALUES
    -- Reasoning orchestrator needs everything
    ('reasoning_orchestrator', 'database.create_procurement'),
    ('reasoning_orchestrator', 'database.save_triage_result'),
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
    
    -- Triage agent
    ('triage_agent', 'database.save_triage_result'),
    
    -- Protocol agent
    ('protocol_agent', 'database.save_protocol'),
    
    -- Oslomodell agent
    ('oslomodell_agent', 'database.search_knowledge_documents'),
    ('oslomodell_agent', 'database.list_knowledge_documents'),
    ('oslomodell_agent', 'database.save_oslomodell_assessment'),
    
    -- Environmental agent (miljokrav)
    ('environmental_agent', 'database.search_miljokrav_documents'),
    ('environmental_agent', 'database.list_miljokrav_documents'),
    ('environmental_agent', 'database.save_environmental_assessment'),
    
    -- Knowledge ingester (for loading data)
    ('knowledge_ingester', 'database.store_knowledge_document'),
    ('knowledge_ingester', 'database.search_knowledge_documents'),
    ('knowledge_ingester', 'database.list_knowledge_documents'),
    ('knowledge_ingester', 'database.store_miljokrav_document'),
    ('knowledge_ingester', 'database.search_miljokrav_documents'),
    ('knowledge_ingester', 'database.list_miljokrav_documents')

ON CONFLICT (agent_id, allowed_method) DO UPDATE SET
    is_active = true;
