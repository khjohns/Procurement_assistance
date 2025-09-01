# src/services/llm_gateway.py
import os
import yaml
from pathlib import Path
from google import genai
from google.genai import types
from typing import Literal, Dict, Any, Optional, Type, Union, List, Tuple
import structlog
import asyncio
import json
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError
from enum import Enum

logger = structlog.get_logger()

Purpose = Literal["fast_evaluation", "complex_reasoning", "cost_efficient", "deep_thinking", "default"]

class ConcurrencyMode(Enum):
    """Different modes for handling concurrent requests."""
    SEQUENTIAL = "sequential"  # One at a time
    PARALLEL = "parallel"      # All at once (limited by semaphore)
    BATCH = "batch"           # Use Gemini Batch API (24hr turnaround)

@dataclass
class ParallelRequest:
    """Container for a parallel request."""
    id: str
    prompt: str
    purpose: Purpose = "default"
    response_schema: Optional[Union[Type[BaseModel], Dict[str, Any]]] = None
    kwargs: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}

@dataclass
class ParallelResponse:
    """Container for a parallel response."""
    id: str
    success: bool
    result: Any = None
    error: str = None
    metrics: Dict[str, Any] = None

@dataclass
class LLMUsageMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    
    def record_call(self, success: bool, input_tokens: int = 0, output_tokens: int = 0, cost: float = 0.0):
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_tokens_input += input_tokens
        self.total_tokens_output += output_tokens
        self.total_cost_usd += cost

class LLMStructuredResponseError(Exception):
    """Custom exception for handling structured response validation errors."""
    def __init__(self, message: str, validation_error: ValidationError, faulty_json: str):
        super().__init__(message)
        self.validation_error = validation_error
        self.faulty_json = faulty_json

class LLMGateway:
    def __init__(self, config_path: str = "config/llm_config.yaml"):
        """
        Initialize the LLM Gateway with configuration from YAML file.
        
        Args:
            config_path: Path to the configuration YAML file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize client
        self._init_client()
        
        # Set up model mapping
        self.model_map = self.config['models']['purpose_mapping']
        self.thinking_models = set(self.config['models']['thinking_models']['supported'])
        
        # Purpose configurations
        self.purpose_config = self.config['purpose_configs']
        
        # Display configuration
        self.display_config = self.config['display']
        self.logging_config = self.config['logging']
        
        # Thinking display configuration
        thinking_config = self.config['models']['thinking_models']['default_config']
        self.max_thought_display_length = thinking_config.get('max_thought_display_length', 0)
        self.include_thoughts_default = thinking_config.get('include_thoughts', False)
        self.display_thoughts_console = thinking_config.get('display_thoughts_in_console', True)
        
        # Concurrency control
        concurrency_config = self.config['concurrency']
        self.max_concurrent_requests = concurrency_config.get('max_concurrent_requests', 10)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Rate limiting
        self.rate_limit_per_minute = concurrency_config.get('rate_limit_per_minute', 60)
        self.request_times: List[float] = []
        self.rate_limit_lock = asyncio.Lock()
        
        # Batch configuration
        self.batch_config = concurrency_config.get('batch', {})
        
        # Safety settings
        self.safety_settings = self._create_safety_settings()
        
        # Cost tracking
        self.cost_config = self.config.get('costs', {})
        self.pricing = self.cost_config.get('pricing', {})
        
        # Metrics
        self.metrics = LLMUsageMetrics()
        
        # Advanced configuration
        self.advanced_config = self.config.get('advanced', {})
        
        logger.info(
            "LLMGateway initialized",
            models=list(self.model_map.keys()),
            max_concurrent=self.max_concurrent_requests,
            rate_limit=self.rate_limit_per_minute
        )
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load and parse the YAML configuration file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.warning(f"Config file not found at {config_path}, using defaults")
                return self._get_default_config()
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Override with environment variables where applicable
            config = self._apply_env_overrides(config)
            
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if config file is not available."""
        return {
            'api': {
                'provider': 'google',
                'version': 'beta',
                'api_key_source': 'env',
                'api_key_env_var': 'GEMINI_API_KEY'
            },
            'models': {
                'purpose_mapping': {
                    'fast_evaluation': 'gemini-2.5-flash',
                    'complex_reasoning': 'gemini-2.5-pro',
                    'cost_efficient': 'gemini-2.5-flash-lite',
                    'deep_thinking': 'gemini-2.5-pro',
                    'default': 'gemini-2.5-flash'
                },
                'thinking_models': {
                    'supported': ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite'],
                    'default_config': {
                        'include_thoughts': False,
                        'display_thoughts_in_console': True,
                        'max_thought_display_length': 0
                    }
                }
            },
            'purpose_configs': {
                'fast_evaluation': {
                    'temperature': 0.1,
                    'max_output_tokens': 8192,
                    'thinking_budget': 8192,
                    'max_retries': 2,
                    'timeout_seconds': 120
                },
                'complex_reasoning': {
                    'temperature': 0.3,
                    'max_output_tokens': 8192,
                    'thinking_budget': 32768,
                    'max_retries': 3,
                    'timeout_seconds': 200
                },
                'cost_efficient': {
                    'temperature': 0.2,
                    'max_output_tokens': 4096,
                    'thinking_budget': 4096,
                    'max_retries': 2,
                    'timeout_seconds': 15
                },
                'deep_thinking': {
                    'temperature': 0.1,
                    'max_output_tokens': 8192,
                    'thinking_budget': 32768,
                    'max_retries': 3,
                    'timeout_seconds': 200
                },
                'default': {
                    'temperature': 0.3,
                    'max_output_tokens': 8192,
                    'thinking_budget': 16384,
                    'max_retries': 3,
                    'timeout_seconds': 120
                }
            },
            'concurrency': {
                'max_concurrent_requests': 10,
                'rate_limit_per_minute': 60,
                'default_mode': 'parallel',
                'batch': {
                    'enabled': True,
                    'max_wait_hours': 24,
                    'status_check_interval': 30,
                    'job_name_prefix': 'llm_gateway_batch'
                }
            },
            'safety': {
                'default_settings': [
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
                ]
            },
            'logging': {
                'enabled': True,
                'level': 'INFO',
                'log_token_usage': True,
                'log_estimated_costs': True,
                'log_thoughts': True,
                'thoughts_preview_length': 500,
                'log_performance_metrics': True,
                'log_rate_limit_events': True
            },
            'display': {
                'console': {
                    'use_colors': True,
                    'show_separators': True,
                    'separator_width': 80,
                    'separator_char': '=',
                    'use_emoji': True,
                    'emoji_thinking': '🤔',
                    'emoji_success': '✅',
                    'emoji_error': '❌',
                    'emoji_warning': '⚠️'
                },
                'progress': {
                    'show_progress': True,
                    'update_frequency': 1,
                    'style': 'percentage'
                }
            },
            'costs': {
                'track_costs': True,
                'pricing': {
                    'gemini-2.5-flash': {
                        'input_per_million': 0.075,
                        'output_per_million': 0.30
                    },
                    'gemini-2.5-pro': {
                        'input_per_million': 1.25,
                        'output_per_million': 5.00
                    },
                    'default': {
                        'input_per_million': 0.125,
                        'output_per_million': 0.375
                    }
                },
                'alerts': {
                    'enabled': True,
                    'threshold_usd': 10.0
                }
            }
        }
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Override max concurrent if env var is set
        if os.getenv('LLM_MAX_CONCURRENT'):
            config['concurrency']['max_concurrent_requests'] = int(os.getenv('LLM_MAX_CONCURRENT'))
        
        # Override rate limit if env var is set
        if os.getenv('LLM_RATE_LIMIT'):
            config['concurrency']['rate_limit_per_minute'] = int(os.getenv('LLM_RATE_LIMIT'))
        
        # Override max thought length if env var is set
        if os.getenv('LLM_MAX_THOUGHT_LENGTH'):
            config['models']['thinking_models']['default_config']['max_thought_display_length'] = int(os.getenv('LLM_MAX_THOUGHT_LENGTH'))
        
        return config
    
    def _init_client(self):
        """Initialize the Google GenAI client."""
        api_config = self.config['api']
        
        # Get API key
        if api_config['api_key_source'] == 'env':
            api_key = os.getenv(api_config.get('api_key_env_var', 'GEMINI_API_KEY'))
            if not api_key:
                raise ValueError(f"API key not found in environment variable {api_config.get('api_key_env_var', 'GEMINI_API_KEY')}")
        else:
            api_key = api_config.get('api_key')
            if not api_key:
                raise ValueError("API key not configured")
        
        # Check for Vertex AI configuration
        vertex_config = api_config.get('vertex_ai', {})
        if vertex_config.get('enabled'):
            self.client = genai.Client(
                vertexai=True,
                project=vertex_config.get('project_id'),
                location=vertex_config.get('location', 'us-central1'),
                http_options=types.HttpOptions(api_version=api_config.get('version', 'beta'))
            )
        else:
            self.client = genai.Client(api_key=api_key)
    
    def _create_safety_settings(self) -> List[types.SafetySetting]:
        """Create safety settings from configuration."""
        safety_config = self.config.get('safety', {}).get('default_settings', [])
        safety_settings = []
        
        for setting in safety_config:
            safety_settings.append(
                types.SafetySetting(
                    category=setting['category'],
                    threshold=setting['threshold']
                )
            )
        
        return safety_settings
    
    def _format_console_output(self, text: str, output_type: str = "info") -> str:
        """Format text for console output based on display configuration."""
        if not self.display_config['console']['use_colors']:
            return text
        
        console_config = self.display_config['console']
        
        if output_type == "thinking" and console_config['use_emoji']:
            return f"{console_config['emoji_thinking']} {text}"
        elif output_type == "success" and console_config['use_emoji']:
            return f"{console_config['emoji_success']} {text}"
        elif output_type == "error" and console_config['use_emoji']:
            return f"{console_config['emoji_error']} {text}"
        elif output_type == "separator":
            sep_char = console_config['separator_char']
            width = console_config['separator_width']
            return sep_char * width
        
        return text
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on token usage."""
        if not self.cost_config.get('track_costs', True):
            return 0.0
        
        # Get pricing for the model
        model_pricing = self.pricing.get(model, self.pricing.get('default', {}))
        
        input_cost = (input_tokens / 1_000_000) * model_pricing.get('input_per_million', 0.125)
        output_cost = (output_tokens / 1_000_000) * model_pricing.get('output_per_million', 0.375)
        
        total_cost = input_cost + output_cost
        
        # Check for cost alerts
        alerts_config = self.cost_config.get('alerts', {})
        if alerts_config.get('enabled') and self.metrics.total_cost_usd > alerts_config.get('threshold_usd', 10.0):
            logger.warning(
                "cost_threshold_exceeded",
                total_cost_usd=self.metrics.total_cost_usd,
                threshold=alerts_config.get('threshold_usd')
            )
        
        return round(total_cost, 6)
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting to stay within API limits."""
        async with self.rate_limit_lock:
            now = asyncio.get_event_loop().time()
            # Remove timestamps older than 1 minute
            self.request_times = [t for t in self.request_times if now - t < 60]
            
            if len(self.request_times) >= self.rate_limit_per_minute:
                # Calculate wait time until the oldest request expires
                oldest_time = self.request_times[0]
                wait_time = 60 - (now - oldest_time) + 0.1  # Add 100ms buffer
                if wait_time > 0:
                    if self.logging_config.get('log_rate_limit_events'):
                        logger.info(
                            "rate_limit_reached",
                            current_requests=len(self.request_times),
                            wait_seconds=wait_time
                        )
                    await asyncio.sleep(wait_time)
                    # Clean up after waiting
                    now = asyncio.get_event_loop().time()
                    self.request_times = [t for t in self.request_times if now - t < 60]
            
            # Record this request
            self.request_times.append(now)
    
    async def generate(self, prompt: str, purpose: Purpose = "default", **kwargs) -> str:
        """Generate text response using Google GenAI SDK."""
        config = self.purpose_config.get(purpose, self.purpose_config["default"])
        model_name = kwargs.get("model_override") or self.model_map.get(purpose, self.model_map["default"])
        
        # Build config parameters
        config_params = {
            "temperature": kwargs.get("temperature", config["temperature"]),
            "max_output_tokens": kwargs.get("max_output_tokens", config["max_output_tokens"]),
            "safety_settings": self.safety_settings
        }
        
        # Add thinking_config if model supports it
        include_thoughts = kwargs.get("include_thoughts", self.include_thoughts_default)
        if model_name in self.thinking_models and config.get("thinking_budget") is not None:
            thinking_budget = kwargs.get("thinking_budget", config["thinking_budget"])
            config_params["thinking_config"] = types.ThinkingConfig(
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts
            )
        
        # Create config object
        generate_config = types.GenerateContentConfig(**config_params)
        
        for attempt in range(config["max_retries"] + 1):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()
                
                # Make the API call
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=generate_config
                    ),
                    timeout=config["timeout_seconds"]
                )
                
                # Handle response
                if not response or not response.text:
                    raise ValueError("LLM response is empty or was blocked.")
                
                # Process thoughts if available
                if include_thoughts and self.display_thoughts_console:
                    self._process_and_display_thoughts(response, model_name)
                
                # Record metrics
                usage = getattr(response, 'usage_metadata', None)
                if usage:
                    input_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)
                    cost = self._calculate_cost(model_name, input_tokens, output_tokens)
                    
                    self.metrics.record_call(True, input_tokens, output_tokens, cost)
                    
                    if self.logging_config.get('log_token_usage'):
                        thoughts_tokens = getattr(usage, 'thoughts_token_count', 0) if hasattr(usage, 'thoughts_token_count') else 0
                        logger.info(
                            "llm_token_usage",
                            model=model_name,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            thoughts_tokens=thoughts_tokens,
                            estimated_cost_usd=cost
                        )
                else:
                    self.metrics.record_call(True)
                
                return response.text
                
            except asyncio.TimeoutError:
                logger.warning(
                    "llm_call_timeout",
                    model=model_name,
                    attempt=attempt + 1,
                    timeout=config["timeout_seconds"]
                )
                if attempt == config["max_retries"]:
                    self.metrics.record_call(False)
                    return json.dumps({"error": "Request timeout", "details": f"Timeout after {config['timeout_seconds']} seconds"})
                    
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "llm_call_failed",
                    model=model_name,
                    attempt=attempt + 1,
                    error=str(e),
                    retry_in=wait_time if attempt < config["max_retries"] else None
                )
                if attempt == config["max_retries"]:
                    self.metrics.record_call(False)
                    return json.dumps({"error": "Max retries exceeded", "details": str(e)})
                await asyncio.sleep(wait_time)
        
        return json.dumps({"error": "Max retries exceeded"})
    
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Union[Type[BaseModel], Dict[str, Any]],
        purpose: Purpose = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generates a structured response using JSON mode.
        """
        pydantic_model: Optional[Type[BaseModel]] = None
        
        # Determine the schema to use
        if isinstance(response_schema, dict):
            schema_for_generation = response_schema
        elif issubclass(response_schema, BaseModel):
            schema_for_generation = response_schema.model_json_schema()
            pydantic_model = response_schema
        else:
            raise TypeError(f"response_schema must be a Pydantic model class or a JSON schema dict, got {type(response_schema)}")
        
        # Get configuration
        config = self.purpose_config.get(purpose, self.purpose_config["default"])
        model_name = kwargs.get("model_override") or self.model_map.get(purpose, self.model_map["default"])
        
        # Build config parameters
        config_params = {
            "temperature": kwargs.get("temperature", config["temperature"]),
            "max_output_tokens": kwargs.get("max_output_tokens", config["max_output_tokens"]),
            "response_schema": schema_for_generation,
            "response_mime_type": "application/json",
            "safety_settings": self.safety_settings
        }
        
        # Add thinking_config if model supports it
        include_thoughts = kwargs.get("include_thoughts", self.include_thoughts_default)
        if model_name in self.thinking_models and config.get("thinking_budget") is not None:
            thinking_budget = kwargs.get("thinking_budget", config["thinking_budget"])
            config_params["thinking_config"] = types.ThinkingConfig(
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts
            )
        
        # Create config object
        generate_config = types.GenerateContentConfig(**config_params)
        
        # Enhanced prompt for structured response
        enhanced_prompt = f"{prompt}\n\nIMPORTANT: Your response must be a valid JSON object that matches the requested schema."
        
        for attempt in range(config["max_retries"] + 1):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()
                
                # Generate response
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model_name,
                        contents=enhanced_prompt,
                        config=generate_config
                    ),
                    timeout=config["timeout_seconds"]
                )
                
                if not response or not response.text:
                    raise ValueError("LLM response is empty or was blocked.")
                
                # Process thoughts if available
                if include_thoughts and self.display_thoughts_console:
                    self._process_and_display_thoughts(response, model_name, is_structured=True)
                
                raw_response = response.text
                
                # Parse JSON response
                try:
                    parsed_json = json.loads(raw_response)
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse LLM response as JSON", response=raw_response[:500])
                    if attempt == config["max_retries"]:
                        raise LLMStructuredResponseError(
                            "Failed to parse LLM response as JSON.",
                            ValidationError.from_exception_data("JSONDecodeError", []),
                            raw_response
                        )
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                # Validate with Pydantic if model provided
                if pydantic_model:
                    try:
                        validated_data = pydantic_model(**parsed_json)
                        logger.debug("Structured response parsed and validated successfully")
                        
                        # Display result if configured
                        if self.display_config['console']['show_separators']:
                            print("\n" + self._format_console_output("", "separator"))
                            print(self._format_console_output("LLM STRUCTURED RESPONSE:", "success"))
                            print(self._format_console_output("", "separator").replace("=", "-"))
                            print(json.dumps(validated_data.model_dump(), ensure_ascii=False, indent=2))
                            print(self._format_console_output("", "separator") + "\n")
                        
                        # Record metrics
                        usage = getattr(response, 'usage_metadata', None)
                        if usage:
                            input_tokens = getattr(usage, 'prompt_token_count', 0)
                            output_tokens = getattr(usage, 'candidates_token_count', 0)
                            cost = self._calculate_cost(model_name, input_tokens, output_tokens)
                            self.metrics.record_call(True, input_tokens, output_tokens, cost)
                        else:
                            self.metrics.record_call(True)
                        
                        return validated_data.model_dump()
                    except ValidationError as e:
                        logger.warning(
                            "Pydantic validation failed",
                            schema=pydantic_model.__name__,
                            attempt=attempt + 1
                        )
                        if attempt == config["max_retries"]:
                            raise LLMStructuredResponseError(
                                "Pydantic validation failed.",
                                e,
                                raw_response
                            )
                        await asyncio.sleep(2 ** attempt)
                        continue
                else:
                    # Record metrics
                    usage = getattr(response, 'usage_metadata', None)
                    if usage:
                        input_tokens = getattr(usage, 'prompt_token_count', 0)
                        output_tokens = getattr(usage, 'candidates_token_count', 0)
                        cost = self._calculate_cost(model_name, input_tokens, output_tokens)
                        self.metrics.record_call(True, input_tokens, output_tokens, cost)
                    else:
                        self.metrics.record_call(True)
                    
                    return parsed_json
                    
            except asyncio.TimeoutError:
                logger.warning(
                    "structured_llm_call_timeout",
                    model=model_name,
                    attempt=attempt + 1,
                    timeout=config["timeout_seconds"]
                )
                if attempt == config["max_retries"]:
                    self.metrics.record_call(False)
                    raise LLMStructuredResponseError(
                        "Request timeout",
                        ValidationError.from_exception_data("TimeoutError", []),
                        ""
                    )
                    
            except LLMStructuredResponseError:
                raise  # Re-raise structured errors
                
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "structured_llm_call_failed",
                    model=model_name,
                    attempt=attempt + 1,
                    error=str(e),
                    retry_in=wait_time if attempt < config["max_retries"] else None
                )
                if attempt == config["max_retries"]:
                    self.metrics.record_call(False)
                    raise
                await asyncio.sleep(wait_time)
        
        self.metrics.record_call(False)
        raise LLMStructuredResponseError(
            "Max retries exceeded",
            ValidationError.from_exception_data("MaxRetriesError", []),
            ""
        )
    
    def _process_and_display_thoughts(self, response, model_name: str, is_structured: bool = False):
        """Process and display thinking process if available."""
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    thoughts_summary = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'thought') and part.thought and hasattr(part, 'text'):
                            thoughts_summary.append(part.text)
                    
                    if thoughts_summary:
                        # Log thoughts
                        if self.logging_config.get('log_thoughts'):
                            preview_length = self.logging_config.get('thoughts_preview_length', 500)
                            logger.info(
                                "llm_thinking_process" if not is_structured else "llm_structured_thinking",
                                model=model_name,
                                thoughts_count=len(thoughts_summary),
                                thoughts_preview=thoughts_summary[0][:preview_length] if thoughts_summary else None
                            )
                        
                        # Display thoughts in console
                        if self.display_config['console']['show_separators']:
                            print("\n" + self._format_console_output("", "separator"))
                            title = "LLM THINKING PROCESS:" if not is_structured else "LLM STRUCTURED RESPONSE THINKING:"
                            print(self._format_console_output(title, "thinking"))
                            print(self._format_console_output("", "separator").replace("=", "-"))
                            
                            for idx, thought in enumerate(thoughts_summary, 1):
                                # Apply length limit if configured
                                display_thought = thought
                                if self.max_thought_display_length > 0 and len(thought) > self.max_thought_display_length:
                                    display_thought = thought[:self.max_thought_display_length] + f"\n... [truncated {len(thought) - self.max_thought_display_length} chars]"
                                
                                print(f"Thought {idx}:\n{display_thought}")
                                if idx < len(thoughts_summary):
                                    print("-" * 40)
                            
                            print(self._format_console_output("", "separator") + "\n")
    
    async def generate_parallel(
        self,
        requests: List[ParallelRequest],
        mode: ConcurrencyMode = None,
        progress_callback: Optional[callable] = None
    ) -> List[ParallelResponse]:
        """Process multiple requests with specified concurrency mode."""
        if mode is None:
            mode_str = self.config['concurrency'].get('default_mode', 'parallel')
            mode = ConcurrencyMode(mode_str)
        
        log = logger.bind(
            mode=mode.value,
            total_requests=len(requests)
        )
        log.info("starting_parallel_processing")
        
        if mode == ConcurrencyMode.BATCH:
            return await self._process_batch_mode(requests)
        elif mode == ConcurrencyMode.SEQUENTIAL:
            return await self._process_sequential(requests, progress_callback)
        else:  # PARALLEL
            return await self._process_parallel(requests, progress_callback)
    
    async def _process_sequential(
        self,
        requests: List[ParallelRequest],
        progress_callback: Optional[callable] = None
    ) -> List[ParallelResponse]:
        """Process requests one at a time."""
        responses = []
        total = len(requests)
        
        for idx, request in enumerate(requests, 1):
            response = await self._process_single_request(request)
            responses.append(response)
            
            if progress_callback:
                progress_callback(idx, total)
            
            if self.logging_config.get('log_performance_metrics'):
                logger.info(
                    "sequential_progress",
                    completed=idx,
                    total=total,
                    request_id=request.id
                )
        
        return responses
    
    async def _process_parallel(
        self,
        requests: List[ParallelRequest],
        progress_callback: Optional[callable] = None
    ) -> List[ParallelResponse]:
        """Process requests in parallel with semaphore control."""
        async def process_with_semaphore(request: ParallelRequest) -> ParallelResponse:
            async with self.semaphore:
                return await self._process_single_request(request)
        
        # Create all tasks
        tasks = [
            asyncio.create_task(process_with_semaphore(req))
            for req in requests
        ]
        
        # Wait for all tasks with progress updates
        responses = []
        completed = 0
        total = len(tasks)
        
        for task in asyncio.as_completed(tasks):
            response = await task
            responses.append(response)
            completed += 1
            
            if progress_callback:
                progress_callback(completed, total)
            
            if self.logging_config.get('log_performance_metrics'):
                logger.info(
                    "parallel_progress",
                    completed=completed,
                    total=total,
                    request_id=response.id
                )
        
        return responses
    
    async def _process_single_request(self, request: ParallelRequest) -> ParallelResponse:
        """Process a single request and return ParallelResponse."""
        try:
            if request.response_schema:
                result = await self.generate_structured(
                    prompt=request.prompt,
                    response_schema=request.response_schema,
                    purpose=request.purpose,
                    **request.kwargs
                )
            else:
                result = await self.generate(
                    prompt=request.prompt,
                    purpose=request.purpose,
                    **request.kwargs
                )
            
            return ParallelResponse(
                id=request.id,
                success=True,
                result=result,
                metrics={
                    "tokens_used": self.metrics.total_tokens_input + self.metrics.total_tokens_output,
                    "estimated_cost": self.metrics.total_cost_usd
                }
            )
        except Exception as e:
            logger.error(
                "parallel_request_failed",
                request_id=request.id,
                error=str(e)
            )
            return ParallelResponse(
                id=request.id,
                success=False,
                error=str(e)
            )
    
    async def _process_batch_mode(self, requests: List[ParallelRequest]) -> List[ParallelResponse]:
        """Process requests using Gemini Batch API for cost savings (50% off)."""
        if not self.batch_config.get('enabled', True):
            logger.warning("Batch mode is disabled in configuration, falling back to parallel mode")
            return await self._process_parallel(requests)
        
        log = logger.bind(batch_size=len(requests))
        log.info("preparing_batch_job")
        
        # Convert requests to batch format
        batch_requests = []
        for req in requests:
            batch_req = {
                "key": req.id,
                "request": {
                    "contents": [{"parts": [{"text": req.prompt}]}]
                }
            }
            
            # Add generation config if needed
            if req.kwargs:
                gen_config = {}
                if "temperature" in req.kwargs:
                    gen_config["temperature"] = req.kwargs["temperature"]
                if "max_output_tokens" in req.kwargs:
                    gen_config["max_output_tokens"] = req.kwargs["max_output_tokens"]
                if gen_config:
                    batch_req["request"]["generation_config"] = gen_config
            
            batch_requests.append(batch_req)
        
        try:
            # Submit batch job
            model_name = self.model_map.get(requests[0].purpose, self.model_map["default"])
            job_name = f"{self.batch_config.get('job_name_prefix', 'batch')}_{asyncio.get_event_loop().time()}"
            
            batch_job = self.client.batches.create(
                model=model_name,
                src=batch_requests,  # Inline requests
                config={'display_name': job_name}
            )
            
            log.info("batch_job_created", job_name=batch_job.name)
            
            # Wait for completion
            completed_states = {
                'JOB_STATE_SUCCEEDED',
                'JOB_STATE_FAILED',
                'JOB_STATE_CANCELLED',
                'JOB_STATE_PAUSED'
            }
            
            max_wait_hours = self.batch_config.get('max_wait_hours', 24)
            check_interval = self.batch_config.get('status_check_interval', 30)
            max_checks = (max_wait_hours * 3600) // check_interval
            
            for check_num in range(max_checks):
                await asyncio.sleep(check_interval)
                job = self.client.batches.get(name=batch_job.name)
                
                if job.state in completed_states:
                    break
                
                log.debug(
                    "batch_job_status",
                    job_state=job.state,
                    check_number=check_num + 1
                )
            
            # Process results
            if job.state == 'JOB_STATE_SUCCEEDED':
                results = job.inline_response if hasattr(job, 'inline_response') else []
                
                responses = []
                for req, result in zip(requests, results):
                    try:
                        response_text = result.response.candidates[0].content.parts[0].text
                        responses.append(ParallelResponse(
                            id=req.id,
                            success=True,
                            result=response_text
                        ))
                    except Exception as e:
                        responses.append(ParallelResponse(
                            id=req.id,
                            success=False,
                            error=f"Failed to parse batch result: {str(e)}"
                        ))
                
                return responses
            else:
                error_msg = f"Batch job failed with state: {job.state}"
                log.error("batch_job_failed", job_state=job.state)
                return [
                    ParallelResponse(id=req.id, success=False, error=error_msg)
                    for req in requests
                ]
                
        except Exception as e:
            log.error("batch_processing_error", error=str(e))
            return [
                ParallelResponse(id=req.id, success=False, error=str(e))
                for req in requests
            ]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get usage metrics for the gateway."""
        success_rate = (
            (self.metrics.successful_calls / self.metrics.total_calls)
            if self.metrics.total_calls > 0
            else 0
        )
        
        return {
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "success_rate": round(success_rate, 3),
            "total_input_tokens": self.metrics.total_tokens_input,
            "total_output_tokens": self.metrics.total_tokens_output,
            "estimated_cost_usd": round(self.metrics.total_cost_usd, 6)
        }