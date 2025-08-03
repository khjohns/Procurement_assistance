import os
import json
import time
import asyncio
from anthropic import Anthropic, RateLimitError, APIStatusError, APIConnectionError
from dotenv import load_dotenv

load_dotenv()

class ClaudeIntegration:
    def __init__(self, config_path='config/claude-config.json'):
        self.config_path = config_path
        self.config = self._load_config()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        self.client = Anthropic(api_key=self.api_key)
        self.last_call_time = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.token_costs = {
            "claude-3-opus-20240229": {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
            "claude-3-sonnet-20240229": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
            "claude-3-haiku-20240307": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
            "claude-sonnet-4-20250514": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}, # Assuming same as sonnet-3
        }

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Configuration file not found at {self.config_path}. Using default settings.")
            return {
                "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", 3000)),
                "rate_limit_delay": float(os.getenv("CLAUDE_RATE_LIMIT", 2.0)),
                "enable_cost_tracking": True
            }
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {self.config_path}. Using default settings.")
            return {
                "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", 3000)),
                "rate_limit_delay": float(os.getenv("CLAUDE_RATE_LIMIT", 2.0)),
                "enable_cost_tracking": True
            }

    async def _wait_for_rate_limit(self):
        elapsed = time.time() - self.last_call_time
        if elapsed < self.config["rate_limit_delay"]:
            await asyncio.sleep(self.config["rate_limit_delay"] - elapsed)
        self.last_call_time = time.time()

    def _calculate_cost(self, model, input_tokens, output_tokens):
        if not self.config.get("enable_cost_tracking", True):
            return 0.0

        costs = self.token_costs.get(model)
        if not costs:
            print(f"Warning: No cost information for model {model}. Cost tracking disabled for this call.")
            return 0.0

        input_cost = input_tokens * costs["input"]
        output_cost = output_tokens * costs["output"]
        return input_cost + output_cost

    async def consult(self, prompt: str, task_type: str = "general_consultation", system_message: str = None):
        await self._wait_for_rate_limit()

        messages = [{"role": "user", "content": prompt}]
        if system_message:
            messages.insert(0, {"role": "system", "content": system_message})

        model_to_use = self.config["model"]
        max_tokens_to_sample = self.config["max_tokens"]

        try:
            print(f"Consulting Claude with model: {model_to_use}, max_tokens: {max_tokens_to_sample}")
            response = await self.client.messages.create(
                model=model_to_use,
                max_tokens=max_tokens_to_sample,
                messages=messages
            )

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self._calculate_cost(model_to_use, input_tokens, output_tokens)

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost

            return {
                "status": "success",
                "response": response.content[0].text,
                "model": model_to_use,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost
                },
                "total_tracked_cost_usd": self.total_cost
            }
        except RateLimitError:
            return {"status": "error", "message": "Rate limit exceeded. Please wait and try again."}
        except APIStatusError as e:
            return {"status": "error", "message": f"Claude API error: {e.status_code} - {e.response}"}
        except APIConnectionError as e:
            return {"status": "error", "message": f"Connection error: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}

    def get_status(self):
        try:
            # Attempt a very small, cheap call to verify API key and connection
            # This is a lightweight check, not a full consultation
            # Note: Anthropic client doesn't have a direct 'ping' or 'status' endpoint.
            # A small message creation is the closest way to verify credentials.
            # We don't await this here as it's just for status reporting, not a full call.
            # The actual check will happen when `consult` is called.
            return {
                "status": "ready",
                "model": self.config["model"],
                "rate_limit_delay": self.config["rate_limit_delay"],
                "cost_tracking_enabled": self.config.get("enable_cost_tracking", True),
                "message": "Claude integration is configured and ready. API key loaded."
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Claude integration failed to initialize: {e}. Check ANTHROPIC_API_KEY and config."
            }

    def get_cost_estimate(self, prompt_tokens: int, completion_tokens: int):
        model_to_use = self.config["model"]
        estimated_cost = self._calculate_cost(model_to_use, prompt_tokens, completion_tokens)
        return {
            "model": model_to_use,
            "estimated_input_tokens": prompt_tokens,
            "estimated_output_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "message": f"Estimated cost for {prompt_tokens} input tokens and {completion_tokens} output tokens with {model_to_use} is ${estimated_cost:.6f} USD."
        }

    def get_total_tracked_cost(self):
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost
        }

if __name__ == "__main__":
    # Example usage for testing
    async def main():
        # Ensure ANTHROPIC_API_KEY is set in your .env file or environment
        # For testing, create a dummy config file if it doesn't exist
        if not os.path.exists('config/claude-config.json'):
            os.makedirs('config', exist_ok=True)
            with open('config/claude-config.json', 'w') as f:
                json.dump({
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "rate_limit_delay": 2.0,
                    "enable_cost_tracking": True
                }, f)

        claude = ClaudeIntegration()
        print("Claude Status:", claude.get_status())

        # Test consultation
        print("\n--- Testing Consultation ---")
        response = await claude.consult("What is the capital of France?", task_type="general_knowledge")
        print("Consultation Response:", response)

        # Test cost estimate
        print("\n--- Testing Cost Estimate ---")
        estimate = claude.get_cost_estimate(50, 100)
        print("Cost Estimate:", estimate)

        # Test total tracked cost
        print("\n--- Testing Total Tracked Cost ---")
        total_cost = claude.get_total_tracked_cost()
        print("Total Tracked Cost:", total_cost)

    asyncio.run(main())