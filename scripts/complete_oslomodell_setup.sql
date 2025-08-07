-- complete_oslomodell_setup.sql
-- Complete database setup for Oslomodell with RPC Gateway
-- Run this AFTER the main reset_database.sql

-- ========================================
-- STEP 0: ENSURE VECTOR EXTENSION
-- ========================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ========================================
-- STEP 1: CREATE KNOWLEDGE BASE TABLE
-- ========================================

DROP TABLE IF EXISTS oslomodell_knowledge CASCADE;

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
-- STEP 2: CREATE RPC FUNCTIONS
-- ========================================

-- Function to store knowledge document
CREATE OR REPLACE FUNCTION store_knowledge_document(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
v_doc_id UUID;
v_embedding_text TEXT;
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

-- Function to search knowledge documents with similarity
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

-- Function to get all knowledge documents (for debugging)
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
-- STEP 3: REGISTER IN GATEWAY CATALOG
-- ========================================

-- Register functions in service catalog
INSERT INTO gateway_service_catalog (service_name, service_type, function_key, sql_function_name, function_metadata)
VALUES
('database', 'postgres_rpc', 'store_knowledge_document', 'store_knowledge_document',
'{"description": "Stores a knowledge document with embedding",
"input_schema": {
"type": "object",
"properties": {
"documentId": {"type": "string"},
"content": {"type": "string"},
"embedding": {"type": "array", "items": {"type": "number"}},
"metadata": {"type": "object"}
},
"required": ["documentId", "content", "embedding"]
}
}'::jsonb),
('database', 'postgres_rpc', 'search_knowledge_documents', 'search_knowledge_documents',
'{"description": "Searches knowledge documents using vector similarity",
"input_schema": {
"type": "object",
"properties": {
"queryEmbedding": {"type": "array", "items": {"type": "number"}},
"threshold": {"type": "number", "minimum": 0, "maximum": 1},
"limit": {"type": "integer", "minimum": 1},
"metadataFilter": {"type": "object"}
},
"required": ["queryEmbedding"]
}
}'::jsonb),
('database', 'postgres_rpc', 'list_knowledge_documents', 'list_knowledge_documents',
'{"description": "Lists all knowledge documents",
"input_schema": {"type": "object", "properties": {}}
}'::jsonb)
ON CONFLICT (service_name, function_key) DO UPDATE SET
sql_function_name = EXCLUDED.sql_function_name,
function_metadata = EXCLUDED.function_metadata,
is_active = true;

-- ========================================
-- STEP 4: GRANT ACCESS TO AGENTS
-- ========================================

-- Grant access to all relevant agents
INSERT INTO gateway_acl_config (agent_id, allowed_method)
VALUES
-- Orchestrator needs everything
('reasoning_orchestrator', 'database.store_knowledge_document'),
('reasoning_orchestrator', 'database.search_knowledge_documents'),
('reasoning_orchestrator', 'database.list_knowledge_documents'),

-- Oslomodell agent needs search
('oslomodell_agent', 'database.search_knowledge_documents'),
('oslomodell_agent', 'database.list_knowledge_documents'),

-- Knowledge ingester needs store and search
('knowledge_ingester', 'database.store_knowledge_document'),
('knowledge_ingester', 'database.search_knowledge_documents'),
('knowledge_ingester', 'database.list_knowledge_documents')

ON CONFLICT (agent_id, allowed_method) DO UPDATE SET
is_active = true;

-- ========================================
-- STEP 5: VERIFY SETUP
-- ========================================

-- Verification query
DO $$
DECLARE
v_table_count int;
v_function_count int;
v_acl_count int;
BEGIN
-- Check table
SELECT COUNT(*) INTO v_table_count
FROM information_schema.tables
WHERE table_name = 'oslomodell_knowledge';

-- Check functions
SELECT COUNT(*) INTO v_function_count
FROM gateway_service_catalog 
WHERE function_key IN ('store_knowledge_document', 'search_knowledge_documents', 'list_knowledge_documents');

-- Check ACL
SELECT COUNT(*) INTO v_acl_count
FROM gateway_acl_config 
WHERE allowed_method LIKE 'database.%knowledge%';

RAISE NOTICE 'Setup verification:';
RAISE NOTICE '  - Tables created: %', v_table_count;
RAISE NOTICE '  - Functions registered: %', v_function_count;
RAISE NOTICE '  - ACL rules: %', v_acl_count;

IF v_table_count > 0 AND v_function_count >= 3 AND v_acl_count >= 6 THEN
    RAISE NOTICE '✅ Oslomodell database setup completed successfully!';
ELSE
    RAISE WARNING '⚠️ Setup may be incomplete, check the counts above';
END IF;

END $$;