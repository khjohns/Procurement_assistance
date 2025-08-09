# tests/unit/test_environmental_agent.py
"""
Unit tests for EnvironmentalAgent (refactored miljøkrav agent).
Tests the environmental requirements assessment functionality with Pydantic validation.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from pydantic import ValidationError

from src.specialists.environmental_agent_refactored import EnvironmentalAgent
from src.models.procurement_models_refactored import (
    ProcurementRequest, 
    ProcurementCategory,
    EnvironmentalRiskLevel,
    EnvironmentalAssessmentResult,
    TransportType
)

class TestEnvironmentalAgent:
    """Test suite for EnvironmentalAgent with validation."""
    
    @pytest.fixture
    def mock_llm_gateway(self):
        """Mock LLM gateway."""
        gateway = AsyncMock()
        return gateway
    
    @pytest.fixture
    def mock_embedding_gateway(self):
        """Mock embedding gateway."""
        gateway = AsyncMock()
        gateway.create_embedding.return_value = [0.1] * 1536  # Mock embedding vector
        return gateway
    
    @pytest.fixture
    def environmental_agent(self, mock_llm_gateway, mock_embedding_gateway):
        """Create EnvironmentalAgent instance with mocked dependencies."""
        agent = EnvironmentalAgent(mock_llm_gateway, mock_embedding_gateway)
        return agent
    
    @pytest.fixture
    def sample_construction_procurement(self):
        """Sample construction procurement for testing."""
        return ProcurementRequest(
            name="Totalentreprise ny barneskole",
            value=25_000_000,
            description="Bygging av ny barneskole med idrettshall og uteområder",
            category=ProcurementCategory.BYGGE,
            duration_months=18,
            includes_construction=True
        )
    
    @pytest.fixture
    def sample_small_procurement(self):
        """Sample small procurement for testing."""
        return ProcurementRequest(
            name="Innkjøp av kontorutstyr",
            value=50_000,
            description="Stoler og skrivepulter til kontorer",
            category=ProcurementCategory.VARE,
            duration_months=1,
            includes_construction=False
        )
    
    @pytest.mark.asyncio
    async def test_execute_validates_input(self, environmental_agent, mock_llm_gateway):
        """Test that execute validates input using Pydantic."""
        # Test with invalid input
        invalid_params = {
            "name": "Test",
            "value": "not_a_number",  # Invalid
            "category": "invalid_category"  # Invalid
        }
        
        with pytest.raises(ValueError) as exc_info:
            await environmental_agent.execute(invalid_params)
        assert "Invalid procurement data" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_validates_output(self, environmental_agent, mock_llm_gateway, mock_embedding_gateway):
        """Test that execute validates output using Pydantic."""
        # Mock RPC client
        mock_rpc_client = AsyncMock()
        mock_rpc_client.call.return_value = {"status": "success", "results": []}
        mock_rpc_client.__aenter__ = AsyncMock(return_value=mock_rpc_client)
        mock_rpc_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.specialists.environmental_agent_refactored.RPCGatewayClient', return_value=mock_rpc_client):
            # Mock LLM responses
            mock_llm_gateway.generate_structured.side_effect = [
                # Planning response
                {
                    "themes": ["Standard klima- og miljøkrav"],
                    "value_above_threshold": True,
                    "involves_mass_transport": False,
                    "involves_heavy_vehicles": False,
                    "exception_likely": False
                },
                # Assessment with valid enum value
                {
                    "procurement_id": "test-id",
                    "procurement_name": "Test",
                    "assessed_by": "environmental_agent",
                    "environmental_risk": "høy",  # Valid enum value
                    "climate_impact_assessed": True,
                    "transport_requirements": [],
                    "exceptions_recommended": [],
                    "minimum_biofuel_required": False,
                    "important_deadlines": {},
                    "documentation_requirements": ["Test requirement"],
                    "follow_up_points": [],
                    "market_dialogue_recommended": False,
                    "award_criteria_recommended": [],
                    "recommendations": [],
                    "confidence": 0.9
                }
            ]
            
            params = {
                "procurement": {
                    "name": "Test Procurement",
                    "value": 1000000,
                    "description": "Test",
                    "category": "vare",
                    "duration_months": 12,
                    "includes_construction": False
                }
            }
            
            result = await environmental_agent.execute(params)
            
            # Verify result is a valid dict that could be validated
            assert isinstance(result, dict)
            assert result["environmental_risk"] == "høy"
            assert result["confidence"] == 0.9
            
            # Verify the result can be validated as EnvironmentalAssessmentResult
            validated = EnvironmentalAssessmentResult.model_validate(result)
            assert validated.environmental_risk == EnvironmentalRiskLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_plan_retrieval_with_pydantic_object(self, environmental_agent, mock_llm_gateway, sample_construction_procurement):
        """Test retrieval planning with Pydantic ProcurementRequest object."""
        # Mock LLM response for planning
        mock_llm_gateway.generate_structured.return_value = {
            "themes": ["Standard klima- og miljøkrav", "Utslippsfri massetransport"],
            "value_above_threshold": True,
            "involves_mass_transport": True,
            "involves_heavy_vehicles": True,
            "exception_likely": False
        }
        
        # Pass Pydantic object directly
        result = await environmental_agent._plan_retrieval(sample_construction_procurement)
        
        assert result["value_above_threshold"] is True
        assert result["involves_mass_transport"] is True
        assert "Standard klima- og miljøkrav" in result["themes"]
        
        # Verify the prompt used Pydantic object fields correctly
        call_args = mock_llm_gateway.generate_structured.call_args
        prompt = call_args[1]['prompt']
        assert sample_construction_procurement.name in prompt
        assert str(sample_construction_procurement.value) in prompt
        assert sample_construction_procurement.category.value in prompt
    
    @pytest.mark.asyncio
    async def test_fetch_relevant_context_with_pydantic(self, environmental_agent, mock_embedding_gateway, sample_construction_procurement):
        """Test context fetching with Pydantic object."""
        # Mock RPC client and response
        mock_rpc_client = AsyncMock()
        mock_rpc_client.call.return_value = {
            "status": "success",
            "results": [
                {
                    "documentId": "miljokrav-001",
                    "content": "Standard klima- og miljøkrav gjelder for alle anskaffelser over 100 000 kr",
                    "similarity": 0.85
                }
            ]
        }
        mock_rpc_client.__aenter__ = AsyncMock(return_value=mock_rpc_client)
        mock_rpc_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.specialists.environmental_agent_refactored.RPCGatewayClient', return_value=mock_rpc_client):
            plan = {
                "themes": ["Standard klima- og miljøkrav"],
                "value_above_threshold": True
            }
            
            # Pass Pydantic object
            result = await environmental_agent._fetch_relevant_context(plan, sample_construction_procurement)
            
            assert len(result) == 1
            assert result[0]["documentId"] == "miljokrav-001"
            
            # Verify search query used Pydantic fields
            embedding_call_args = mock_embedding_gateway.create_embedding.call_args
            search_text = embedding_call_args[1]['text']
            assert sample_construction_procurement.category.value in search_text
            assert str(sample_construction_procurement.value) in search_text
    
    @pytest.mark.asyncio
    async def test_generate_assessment_with_pydantic(self, environmental_agent, mock_llm_gateway, sample_construction_procurement):
        """Test assessment generation with Pydantic object."""
        # Mock LLM response
        mock_assessment = {
            "procurement_id": sample_construction_procurement.id,
            "procurement_name": sample_construction_procurement.name,
            "assessed_by": "environmental_agent",
            "environmental_risk": "middels",
            "climate_impact_assessed": True,
            "transport_requirements": [
                {
                    "type": "massetransport",
                    "zero_emission_required": True,
                    "biofuel_alternative": True,
                    "deadline": "2030-01-01",
                    "incentive_applicable": True
                }
            ],
            "exceptions_recommended": [],
            "minimum_biofuel_required": False,
            "important_deadlines": {
                "massetransport": "2030-01-01",
                "kjøretøy_35tonn": "2027-01-01"
            },
            "documentation_requirements": [
                "Dokumenter vurderinger i kontraktsstrategien"
            ],
            "follow_up_points": [
                "Overvåk markedet for utslippsfrie løsninger"
            ],
            "market_dialogue_recommended": True,
            "award_criteria_recommended": [
                "Andel utslippsfrie maskiner"
            ],
            "recommendations": [
                "Gjennomfør markedsdialog tidlig"
            ],
            "confidence": 0.85
        }
        
        mock_llm_gateway.generate_structured.return_value = mock_assessment
        
        context = [
            {
                "documentId": "miljokrav-001",
                "content": "Standard klima- og miljøkrav for byggeprosjekter",
                "relevance_score": 0.85
            }
        ]
        
        # Pass Pydantic object
        result = await environmental_agent._generate_assessment(
            sample_construction_procurement, 
            context
        )
        
        assert result["environmental_risk"] == "middels"
        assert result["market_dialogue_recommended"] is True
        assert result["confidence"] == 0.85
        
        # Verify prompt used Pydantic fields
        call_args = mock_llm_gateway.generate_structured.call_args
        prompt = call_args[1]['prompt']
        assert sample_construction_procurement.id in prompt
        assert sample_construction_procurement.name in prompt
        assert str(sample_construction_procurement.value) in prompt
    
    @pytest.mark.asyncio
    async def test_execute_full_workflow_with_validation(self, environmental_agent, mock_llm_gateway, mock_embedding_gateway, sample_construction_procurement):
        """Test the complete execute workflow with full validation."""
        # Mock RPC client
        mock_rpc_client = AsyncMock()
        mock_rpc_client.call.return_value = {"status": "success", "results": []}
        mock_rpc_client.__aenter__ = AsyncMock(return_value=mock_rpc_client)
        mock_rpc_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.specialists.environmental_agent_refactored.RPCGatewayClient', return_value=mock_rpc_client):
            # Mock planning and assessment responses
            mock_llm_gateway.generate_structured.side_effect = [
                # Planning response
                {
                    "themes": ["Standard klima- og miljøkrav"],
                    "value_above_threshold": True,
                    "involves_mass_transport": True,
                    "involves_heavy_vehicles": False,
                    "exception_likely": False
                },
                # Assessment response
                {
                    "procurement_id": sample_construction_procurement.id,
                    "procurement_name": sample_construction_procurement.name,
                    "assessed_by": "environmental_agent",
                    "environmental_risk": "høy",
                    "climate_impact_assessed": True,
                    "transport_requirements": [],
                    "exceptions_recommended": [],
                    "minimum_biofuel_required": False,
                    "important_deadlines": {},
                    "documentation_requirements": ["Test"],
                    "follow_up_points": [],
                    "market_dialogue_recommended": True,
                    "award_criteria_recommended": [],
                    "recommendations": [],
                    "confidence": 0.80
                }
            ]
            
            # Execute with Pydantic object dict
            params = {"procurement": sample_construction_procurement.model_dump()}
            result = await environmental_agent.execute(params)
            
            assert result["environmental_risk"] == "høy"
            assert result["market_dialogue_recommended"] is True
            assert result["confidence"] == 0.80
            assert result["procurement_id"] == sample_construction_procurement.id
            
            # Verify result is valid according to schema
            validated = EnvironmentalAssessmentResult.model_validate(result)
            assert validated.environmental_risk == EnvironmentalRiskLevel.HIGH
            assert validated.confidence == 0.80
    
    @pytest.mark.asyncio
    async def test_default_assessment_on_validation_error(self, environmental_agent, mock_llm_gateway, mock_embedding_gateway, sample_construction_procurement):
        """Test that default assessment is used when validation fails."""
        # Mock RPC client
        mock_rpc_client = AsyncMock()
        mock_rpc_client.call.return_value = {"status": "success", "results": []}
        mock_rpc_client.__aenter__ = AsyncMock(return_value=mock_rpc_client)
        mock_rpc_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.specialists.environmental_agent_refactored.RPCGatewayClient', return_value=mock_rpc_client):
            # Mock planning and invalid assessment responses
            mock_llm_gateway.generate_structured.side_effect = [
                # Planning response
                {
                    "themes": [],
                    "value_above_threshold": True,
                    "involves_mass_transport": False,
                    "involves_heavy_vehicles": False,
                    "exception_likely": False
                },
                # Invalid assessment (missing required fields)
                {
                    "procurement_id": sample_construction_procurement.id,
                    # Missing many required fields
                    "environmental_risk": "invalid_value"  # Invalid enum
                }
            ]
            
            params = {"procurement": sample_construction_procurement.model_dump()}
            result = await environmental_agent.execute(params)
            
            # Should return default assessment
            assert result["confidence"] == 0.5  # Default confidence
            assert result["procurement_id"] == sample_construction_procurement.id
            assert result["procurement_name"] == sample_construction_procurement.name
            assert "documentation_requirements" in result
            assert len(result["documentation_requirements"]) > 0
    
    def test_create_default_assessment(self, environmental_agent, sample_construction_procurement):
        """Test creation of default assessment."""
        assessment = environmental_agent._create_default_assessment(sample_construction_procurement)
        
        assert isinstance(assessment, EnvironmentalAssessmentResult)
        assert assessment.procurement_id == sample_construction_procurement.id
        assert assessment.procurement_name == sample_construction_procurement.name
        assert assessment.environmental_risk == EnvironmentalRiskLevel.MEDIUM  # 25M > 5M
        assert assessment.confidence == 0.5
        assert assessment.market_dialogue_recommended is True  # 25M > 10M
        assert len(assessment.documentation_requirements) > 0
        assert len(assessment.follow_up_points) > 0
    
    def test_key_dates_configuration(self, environmental_agent):
        """Test that key dates are properly configured."""
        assert "heavy_vehicles" in environmental_agent.key_dates
        assert "mass_transport_incentives" in environmental_agent.key_dates
        
        heavy_vehicles_date = environmental_agent.key_dates["heavy_vehicles"]
        mass_transport_date = environmental_agent.key_dates["mass_transport_incentives"]
        
        assert heavy_vehicles_date.year == 2027
        assert heavy_vehicles_date.month == 1
        assert heavy_vehicles_date.day == 1
        
        assert mass_transport_date.year == 2030
        assert mass_transport_date.month == 1
        assert mass_transport_date.day == 1
    
    def test_valid_themes_configuration(self, environmental_agent):
        """Test that valid themes are properly configured."""
        expected_themes = [
            "Standard klima- og miljøkrav",
            "Utslippsfri massetransport", 
            "Kjøretøy over 3,5 tonn",
            "Unntak",
            "Oppfølging og sanksjonering",
            "Planlegging og markedsdialog"
        ]
        
        assert environmental_agent.valid_themes == expected_themes

if __name__ == "__main__":
    # Run tests directly for debugging
    pytest.main([__file__, "-v", "-s"])