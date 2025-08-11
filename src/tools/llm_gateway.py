# src/tools/llm_gateway.py - Enhanced version
import os
import google.generativeai as genai
from typing import Literal, Dict, Any, Optional
import structlog
import asyncio
import json
from dataclasses import dataclass


logger = structlog.get_logger()

# Expanded purposes based on Gemini 2.5 capabilities
Purpose = Literal[
    "fast_evaluation",      # Quick decisions, simple tasks
    "complex_reasoning",    # Complex problems, coding, analysis  
    "cost_efficient",       # High-volume, low-cost operations
    "deep_thinking",        # Experimental: Most complex reasoning
    "default"
]

@dataclass
class LLMUsageMetrics:
    """Track LLM usage for monitoring and cost control."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    
    def record_call(self, success: bool, input_tokens: int = 0, output_tokens: int = 0):
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_tokens_input += input_tokens
        self.total_tokens_output += output_tokens

class LLMGateway:
    """
    Universal gateway for interacting with language models.
    Selects the right model based on purpose and manages its own 
    configuration from environment variables.
    
    Features:
    - Automatic model selection based on purpose
    - Built-in retry logic with exponential backoff
    - Usage tracking and metrics
    - Support for latest Gemini 2.5 capabilities
    """
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY_NOT_FOUND", 
                        help="Please set GEMINI_API_KEY in your .env file.")
            raise ValueError("API key for LLM (GEMINI_API_KEY) is not set.")
        
        genai.configure(api_key=api_key)
        
        # Updated model map with latest Gemini 2.5 stable models + new Flash-Lite
        self.model_map = {
            "complex_reasoning": "gemini-2.5-pro",        # Most powerful for complex tasks
            "fast_evaluation":   "gemini-2.5-flash",     # Balanced speed and performance  
            "cost_efficient":    "gemini-2.5-flash-lite", # Fastest, most cost-effective
            "deep_thinking":     "gemini-2.5-pro",       # Will use Deep Think mode when available
            "default":           "gemini-2.5-flash"      # Reliable default
        }
        
        # Configuration for different purposes
        self.purpose_config = {
            "fast_evaluation": {
                "temperature": 0.1,
                "max_retries": 2,
                "timeout": 10.0,
                "thinking_budget": 8192  # Limited thinking for speed
            },
            "complex_reasoning": {
                "temperature": 0.3,
                "max_retries": 3, 
                "timeout": 60.0,
                "thinking_budget": 32768  # Full thinking budget
            },
            "cost_efficient": {
                "temperature": 0.2,
                "max_retries": 2,
                "timeout": 15.0,
                "thinking_budget": 4096  # Minimal thinking for cost
            },
            "deep_thinking": {
                "temperature": 0.1,
                "max_retries": 1,  # Expensive, fewer retries
                "timeout": 120.0,
                "thinking_budget": 32768  # Maximum thinking
            },
            "default": {
                "temperature": 0.3,
                "max_retries": 3,
                "timeout": 30.0,
                "thinking_budget": 16384
            }
        }
        
        # Usage tracking
        self.metrics = LLMUsageMetrics()
        
        logger.info("LLMGateway initialized with Gemini 2.5 models", 
                   models=self.model_map,
                   purposes=list(self.purpose_config.keys()))
    
    async def generate(self, 
                       prompt: str, 
                       purpose: Purpose = "default",
                       temperature: Optional[float] = None,
                       response_mime_type: str = "application/json",
                       data: Optional[Dict[str, Any]] = None,
                       model_override: Optional[str] = None,
                       thinking_budget: Optional[int] = None) -> str:
        """
        Generate response using appropriate model for the given purpose.
        
        Args:
            prompt: The prompt to send to the LLM
            purpose: Purpose-based model selection
            temperature: Override default temperature for purpose
            response_mime_type: Expected response format
            data: Additional context data to include
            model_override: Override automatic model selection
            thinking_budget: Override thinking budget (for 2.5 models)
        """
        
        # Get configuration for purpose
        config = self.purpose_config.get(purpose, self.purpose_config["default"])
        model_name = model_override or self.model_map.get(purpose, self.model_map["default"])
        
        # Use purpose-specific defaults, allow overrides
        final_temperature = temperature if temperature is not None else config["temperature"]
        final_thinking_budget = thinking_budget if thinking_budget is not None else config.get("thinking_budget")
        
        # Build full prompt with data if provided
        full_prompt = prompt
        if data:
            full_prompt = f"{prompt}\n\nDATA:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        
        logger.debug("LLM call initiated", 
                    model=model_name, 
                    purpose=purpose,
                    temperature=final_temperature,
                    thinking_budget=final_thinking_budget,
                    prompt_length=len(full_prompt))
        
        # Build generation config
        generation_config = genai.GenerationConfig(
            temperature=final_temperature,
            response_mime_type=response_mime_type,
        )
        
        # Add thinking budget for 2.5 models
        if "2.5" in model_name and final_thinking_budget:
            generation_config.thinking_budget = final_thinking_budget
        
        model = genai.GenerativeModel(
            model_name,
            generation_config=generation_config
        )
        
        # Retry logic with exponential backoff
        max_retries = config["max_retries"]
        timeout = config["timeout"]
        
        for attempt in range(max_retries + 1):
            try:
                # Execute with timeout
                response = await asyncio.wait_for(
                    model.generate_content_async(full_prompt),
                    timeout=timeout
                )
                
                # Track successful call
                self.metrics.record_call(
                    success=True,
                    input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0),
                    output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0)
                )
                
                logger.debug("LLM call successful", 
                           model=model_name,
                           attempt=attempt + 1,
                           input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0),
                           output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0))
                
                return response.text
                
            except asyncio.TimeoutError:
                logger.warning("LLM call timeout", 
                             model=model_name, 
                             attempt=attempt + 1,
                             timeout=timeout)
                if attempt == max_retries:
                    self.metrics.record_call(success=False)
                    return self._create_error_response("Request timeout", "TIMEOUT")
                    
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning("LLM call failed", 
                             model=model_name,
                             attempt=attempt + 1, 
                             error=str(e),
                             retry_in=wait_time if attempt < max_retries else None)
                
                if attempt == max_retries:
                    self.metrics.record_call(success=False)
                    return self._create_error_response(str(e), "GENERATION_FAILED")
                
                await asyncio.sleep(wait_time)
        
        # Should never reach here, but safety net
        self.metrics.record_call(success=False)
        return self._create_error_response("Max retries exceeded", "MAX_RETRIES")
    
    def _create_error_response(self, error_message: str, error_code: str) -> str:
        """Creates standardized error response in JSON format."""
        return json.dumps({
            "error": "LLM generation failed",
            "error_code": error_code,
            "details": error_message.replace('"', "'", 1), # Corrected: only replace the first occurrence of " to ' if it's part of the error message itself
            "model_info": {
                "available_models": list(self.model_map.values()),
                "retry_suggested": True
            }
        }, ensure_ascii=False)
    
    async def generate_structured(self, 
                                prompt: str,
                                response_schema: Dict[str, Any],
                                purpose: Purpose = "default",
                                **kwargs) -> Dict[str, Any]:
        """
        Generate structured response with automatic JSON parsing and validation.
        
        Args:
            prompt: The prompt to send
            response_schema: JSON schema for expected response format
            purpose: Purpose-based model selection
            **kwargs: Additional arguments passed to generate()
        """
        
        # Enhance prompt with schema information
        enhanced_prompt = f"{prompt}\n\nIMPORTANT: Respond with a valid JSON object that matches this schema:\n{json.dumps(response_schema, indent=2)}\n\nYour response must be valid JSON and nothing else."
        
        response = await self.generate(
            prompt=enhanced_prompt,
            purpose=purpose,
            response_mime_type="application/json",
            **kwargs
        )
        
        try:
            parsed = json.loads(response)
            logger.debug("Structured response parsed successfully", schema_keys=list(response_schema.get("properties", {}).keys()))
            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse structured response", response=response[:500], error=str(e))
            # Return error in expected format
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": response[:1000],  # Truncated for logging
                "parse_error": str(e)
            }
    
    async def generate_with_thinking(self,
                                   prompt: str,
                                   thinking_budget: int = 16384,
                                   purpose: Purpose = "complex_reasoning",
                                   **kwargs) -> Dict[str, str]:
        """
        Generate response with explicit thinking capabilities (Gemini 2.5 feature).
        
        Returns both the thinking process and final response.
        """
        
        response = await self.generate(
            prompt=prompt,
            purpose=purpose,
            thinking_budget=thinking_budget,
            response_mime_type="text/plain",  # To capture thinking + response
            **kwargs
        )
        
        # Parse thinking from response if available
        # Note: This may need adjustment based on actual Gemini 2.5 response format
        if "THINKING:" in response and "RESPONSE:" in response:
            parts = response.split("RESPONSE:", 1)
            thinking = parts[0].replace("THINKING:", "").strip()
            final_response = parts[1].strip()
            
            return {
                "thinking": thinking,
                "response": final_response
            }
        else:
            return {
                "thinking": "No explicit thinking process captured",
                "response": response
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current usage metrics."""
        success_rate = 0.0
        if self.metrics.total_calls > 0:
            success_rate = self.metrics.successful_calls / self.metrics.total_calls
        
        return {
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "success_rate": round(success_rate, 3),
            "total_input_tokens": self.metrics.total_tokens_input,
            "total_output_tokens": self.metrics.total_tokens_output,
            "estimated_cost_usd": self._estimate_cost()
        }
    
    def _estimate_cost(self) -> float:
        """
        Rough cost estimation based on token usage.
        Note: Update these rates based on current Gemini 2.5 pricing.
        """
        # Approximate rates (August 2025) - verify with current pricing
        input_cost_per_1k = 0.000125  # $0.125 per 1M tokens for 2.5 Flash
        output_cost_per_1k = 0.000375  # $0.375 per 1M tokens for 2.5 Flash
        
        input_cost = (self.metrics.total_tokens_input / 1000) * input_cost_per_1k
        output_cost = (self.metrics.total_tokens_output / 1000) * output_cost_per_1k
        
        return round(input_cost + output_cost, 6)
    
    async def health_check(self) -> Dict[str, Any]:
        """Test LLM connectivity and performance."""
        test_prompt = "Respond with exactly: {'status': 'healthy', 'timestamp': '<current_timestamp>'}"
        
        try:
            start_time = asyncio.get_event_loop().time()
            response = await self.generate(
                prompt=test_prompt,
                purpose="fast_evaluation",
                temperature=0.0
            )
            end_time = asyncio.get_event_loop().time()
            
            # Try to parse response
            parsed = json.loads(response)
            
            return {
                "status": "healthy",
                "model": self.model_map["fast_evaluation"],
                "response_time_ms": round((end_time - start_time) * 1000, 2),
                "api_status": "connected",
                "test_response": parsed
            }
            
        except Exception as e:
            logger.error("LLM health check failed", error=str(e))
            return {
                "status": "unhealthy", 
                "error": str(e),
                "model": self.model_map["fast_evaluation"],
                "api_status": "disconnected"
            }

# Convenience factory functions for common use cases
class LLMGatewayFactory:
    """Factory for creating pre-configured LLM gateway instances."""
    
    @staticmethod
    def create_for_triage() -> LLMGateway:
        """Create gateway optimized for triage operations."""
        gateway = LLMGateway()
        # Could add triage-specific configuration here
        return gateway
    
    @staticmethod  
    def create_for_orchestration() -> LLMGateway:
        """Create gateway optimized for orchestration reasoning."""
        gateway = LLMGateway()
        # Could add orchestration-specific configuration here
        return gateway
    
    @staticmethod
    def create_for_rag() -> LLMGateway:
        """Create gateway optimized for RAG operations."""
        gateway = LLMGateway()
        # Could add RAG-specific configuration here
        return gateway

# Backward compatibility alias (for gradual migration)
GeminiGateway = LLMGateway
