#!/usr/bin/env python
"""Claude MCP Server using FastMCP (Recommended)"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fastmcp import FastMCP
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env'))

# Initialize FastMCP server
mcp = FastMCP("claude-consultant")

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@mcp.tool
def consult_claude(query: str, context: str = "", task_type: str = "general") -> str:
    """Consult Claude Sonnet 4 for analysis"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": f"Task type: {task_type}\n\nContext: {context}\n\nQuery: {query}"
            }]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error consulting Claude: {str(e)}"

@mcp.tool
def claude_status() -> str:
    """Check Claude integration status"""
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return f"Claude integration {'enabled' if api_key_set else 'disabled'}"

@mcp.tool
def claude_cost_estimate(query_length: int, expected_response_length: int = 1000) -> str:
    """Estimate cost for a Claude consultation"""
    input_tokens = query_length / 4  # Rough estimate
    output_tokens = expected_response_length / 4
    
    # Claude Sonnet 4 pricing: $3/$15 per million tokens
    input_cost = (input_tokens / 1_000_000) * 3
    output_cost = (output_tokens / 1_000_000) * 15
    total_cost = input_cost + output_cost
    
    return f"Estimated cost: ${total_cost:.4f} ({input_tokens:.0f} in + {output_tokens:.0f} out tokens)"

# Run the server
if __name__ == "__main__":
    mcp.run()