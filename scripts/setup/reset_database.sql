-- complete_database_reset.sql (Corrected English Refactoring)
-- Complete reset and setup of the database for the Procurement Assistant.

-- ========================================
-- STEP 1: CLEAN UP (DROP EVERYTHING)
-- ========================================

DROP FUNCTION IF EXISTS create_procurement(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_triage_result(jsonb) CASCADE;
DROP FUNCTION IF EXISTS set_procurement_status(jsonb) CASCADE;
DROP FUNCTION IF EXISTS save_protocol(jsonb) CASCADE;
DROP FUNCTION IF EXISTS log_execution(jsonb) CASCADE;

DROP TABLE IF EXISTS gateway_acl_config CASCADE;
DROP TABLE IF EXISTS gateway_service_catalog CASCADE;
DROP TABLE IF EXISTS protocols CASCADE;
DROP TABLE IF EXISTS triage_results CASCADE;
DROP TABLE IF EXISTS procurements CASCADE;
DROP TABLE IF EXISTS executions CASCADE;

-- ========================================
-- STEP 2: CREATE APPLICATION TABLES
-- ========================================

CREATE TABLE procurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    value INTEGER NOT NULL,
    description TEXT,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procurement_id UUID NOT NULL,
    goal_description TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP DEFAULT NOW(),
    status TEXT CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED', 'REQUIRES_HUMAN')),
    iterations INTEGER DEFAULT 0,
    final_state JSONB,
    execution_history JSONB,
    agent_id TEXT,
    error_details TEXT
);

-- ========================================
-- STEP 3: CREATE GATEWAY TABLES
-- ========================================

CREATE TABLE gateway_service_catalog (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL CHECK (service_type IN ('postgres_rpc', 'http_endpoint', 'specialist_agent')),
    function_key VARCHAR(100) NOT NULL,
    sql_function_name VARCHAR(255) NOT NULL,
    function_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_name, function_key)
);

CREATE TABLE gateway_acl_config (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    allowed_method VARCHAR(200) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, allowed_method)
);

-- ========================================
-- STEP 4: CREATE FUNCTIONS (Syntax Corrected)
-- ========================================

CREATE OR REPLACE FUNCTION create_procurement(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_procurement_id UUID;
BEGIN
    INSERT INTO procurements (name, value, description)
    VALUES (params->>'name', (params->>'value')::INTEGER, params->>'description')
    RETURNING id INTO v_procurement_id;
    RETURN jsonb_build_object('status', 'success', 'procurementId', v_procurement_id);
EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('status', 'error', 'message', SQLERRM);
END;
$$;

CREATE OR REPLACE FUNCTION save_triage_result(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_result_id UUID;
BEGIN
    INSERT INTO triage_results (procurement_id, color, reasoning, confidence)
    VALUES ((params->>'procurementId')::UUID, params->>'color', params->>'reasoning', (params->>'confidence')::FLOAT)
    ON CONFLICT (procurement_id) DO UPDATE SET
        color = EXCLUDED.color, reasoning = EXCLUDED.reasoning, confidence = EXCLUDED.confidence, updated_at = NOW()
    RETURNING id INTO v_result_id;
    UPDATE procurements SET status = 'TRIAGED', updated_at = NOW() WHERE id = (params->>'procurementId')::UUID;
    RETURN jsonb_build_object('status', 'success', 'resultId', v_result_id);
EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('status', 'error', 'message', SQLERRM);
END;
$$;

CREATE OR REPLACE FUNCTION set_procurement_status(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    UPDATE procurements SET status = params->>'status', updated_at = NOW() WHERE id = (params->>'procurementId')::UUID;
    IF NOT FOUND THEN RETURN jsonb_build_object('status', 'error', 'message', 'Procurement not found'); END IF;
    RETURN jsonb_build_object('status', 'success', 'procurementId', params->>'procurementId', 'newStatus', params->>'status');
EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('status', 'error', 'message', SQLERRM);
END;
$$;

CREATE OR REPLACE FUNCTION save_protocol(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_protocol_id UUID;
BEGIN
    INSERT INTO protocols (procurement_id, content, confidence)
    VALUES ((params->>'procurementId')::UUID, params->>'protocolContent', (params->>'confidence')::FLOAT)
    RETURNING id INTO v_protocol_id;
    UPDATE procurements SET status = 'PROTOCOL_GENERATED', updated_at = NOW() WHERE id = (params->>'procurementId')::UUID;
    RETURN jsonb_build_object('status', 'success', 'protocolId', v_protocol_id);
EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('status', 'error', 'message', SQLERRM);
END;
$$;

CREATE OR REPLACE FUNCTION log_execution(params jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_execution_id UUID;
BEGIN
    INSERT INTO executions (procurement_id, goal_description, status, iterations, final_state, execution_history, agent_id, error_details)
    VALUES ((params->>'procurementId')::UUID, params->>'goalDescription', params->>'status', (params->>'iterations')::INTEGER, params->'finalState', params->'executionHistory', params->>'agentId', params->>'errorDetails')
    RETURNING id INTO v_execution_id;
    RETURN jsonb_build_object('status', 'success', 'executionId', v_execution_id);
EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('status', 'error', 'message', SQLERRM);
END;
$$;

-- ========================================
-- STEP 5: REGISTER FUNCTIONS IN GATEWAY (Syntax Corrected)
-- ========================================

INSERT INTO gateway_service_catalog (service_name, service_type, function_key, sql_function_name, function_metadata)
VALUES 
('database', 'postgres_rpc', 'create_procurement', 'create_procurement', '{ "description": "Creates a new procurement case.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "integer"}, "description": {"type": "string"}}, "required": ["name", "value", "description"]}}'::jsonb),
('database', 'postgres_rpc', 'save_triage_result', 'save_triage_result', '{ "description": "Saves the result from a triage assessment.", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string", "format": "uuid"}, "color": {"type": "string", "enum": ["GRØNN", "GUL", "RØD"]}, "reasoning": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["procurementId", "color", "reasoning", "confidence"]}}'::jsonb),
('database', 'postgres_rpc', 'set_procurement_status', 'set_procurement_status', '{ "description": "Updates the status of a procurement case.", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string", "format": "uuid"}, "status": {"type": "string"}}, "required": ["procurementId", "status"]}}'::jsonb),
('database', 'postgres_rpc', 'save_protocol', 'save_protocol', '{ "description": "Saves a generated procurement protocol.", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string", "format": "uuid"}, "protocolContent": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["procurementId", "protocolContent", "confidence"]}}'::jsonb),
('database', 'postgres_rpc', 'log_execution', 'log_execution', '{ "description": "Logs an orchestrator execution history.", "input_schema": {"type": "object", "properties": {"procurementId": {"type": "string"}, "goalDescription": {"type": "string"}, "status": {"type": "string"}, "iterations": {"type": "integer"}, "finalState": {"type": "object"}, "executionHistory": {"type": "array"}, "agentId": {"type": "string"}}}}'::jsonb),
('agent', 'specialist_agent', 'run_triage', 'TriageAgent.assess_procurement', '{ "description": "Classifies a procurement as GREEN, YELLOW, or RED based on risk and complexity.", "input_schema": {"type": "object", "properties": {"procurement": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "integer"}, "description": {"type": "string"}}, "required": ["name", "value"]}}, "required": ["procurement"]}, "output_schema": {"type": "object", "properties": {"color": {"type": "string"}, "reasoning": {"type": "string"}, "confidence": {"type": "number"}}}}'::jsonb);

-- ========================================
-- STEP 6: SET UP ACCESS CONTROL
-- ========================================

INSERT INTO gateway_acl_config (agent_id, allowed_method)
SELECT 'reasoning_orchestrator', 'database.' || function_key
FROM gateway_service_catalog
WHERE service_name = 'database' AND is_active = true;

INSERT INTO gateway_acl_config (agent_id, allowed_method)
VALUES ('reasoning_orchestrator', 'agent.run_triage');
