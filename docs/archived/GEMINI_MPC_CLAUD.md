# GEMINI.md - Claude Sonnet 4 MCP Integration Project

## Project Overview

This project sets up integration between Gemini CLI (free) and Claude Sonnet 4 API (paid) via Model Context Protocol (MCP), enabling cost-effective development where Gemini CLI handles most tasks and Claude provides premium consultations for code review, architecture decisions, and security analysis.

**Cost Model:** Gemini CLI free (60 req/min, 1000/day) + Claude consultations (~$5-15/month)

## Your Role as Gemini CLI

You are the **primary development assistant** for this integration project. Your responsibilities:

1. **Guide the user through the complete setup process step-by-step**
1. **Help create and configure all necessary files**
1. **Assist with troubleshooting and testing**
1. **Demonstrate the integration once it's working**
1. **Provide ongoing support for the Claude consultation workflow**

## Project Structure to Create

```
gemini-claude-integration/
├── venv/                               # Virtual environment (created automatically)
├── tools/
│   ├── mcp/
│   │   └── claude_mcp_server.py       # MCP server for Claude integration
│   └── claude/
│       └── claude_integration.py      # Claude API wrapper
├── config/
│   └── claude-config.json             # Claude configuration
├── tests/
│   └── test_mcp_server.py             # MCP server tests
├── .env                               # Environment variables (API keys)
├── requirements.txt                   # Python dependencies
├── activate_and_run.sh                # Helper script for activation + running
└── README.md                          # Project documentation
```

## Key Files You Need to Help Create

### requirements.txt

Create this file to manage dependencies (choose one approach):

**Option A: FastMCP (Recommended for beginners)**

```
fastmcp>=2.0.0
anthropic>=0.40.0
python-dotenv>=1.0.0
```

**Option B: Official MCP SDK (For advanced users)**

```
mcp>=1.0.0
anthropic>=0.40.0
python-dotenv>=1.0.0
```

**Installation:**

```bash
# CRITICAL: Always activate venv first
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Verify you're in venv (should show (venv) in prompt)
which python  # Should show path with /venv/

# Install from requirements.txt
pip install -r requirements.txt

# Or install directly (recommended: FastMCP)
pip install fastmcp anthropic python-dotenv
```

### activate_and_run.sh (Helper Script)

Create this bash script to simplify running:

```bash
#!/bin/bash
# Activate virtual environment and run MCP server
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please create it first with: python -m venv venv"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "Virtual environment activated: $VIRTUAL_ENV"
echo "Running MCP server..."

# Run the MCP server
python tools/mcp/claude_mcp_server.py "$@"
```

Make executable: `chmod +x activate_and_run.sh`

## Setup Steps You Should Guide User Through

### Step 1: Prerequisites Check

- Verify Node.js and Python 3.8+ are installed
- Confirm Gemini CLI is working (`gemini --version`)
- Help user get Anthropic API key from console.anthropic.com

### Step 2: Python Virtual Environment Setup

**IMPORTANT:** Always use virtual environment (venv) and `python` command (not `python3`)

```bash
# Create project directory
mkdir gemini-claude-integration
cd gemini-claude-integration

# Create and activate virtual environment
python -m venv venv

# CRITICAL: Activate venv (varies by OS)
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# VERIFY activation - you should see (venv) in your prompt
# Also verify with:
which python  # Should show path containing /venv/
python --version  # Should show Python 3.8+
```

### Step 3: Install Python Dependencies

Install the correct dependencies for your chosen approach:

#### Recommended: FastMCP (Simpler Syntax)

```bash
# Ensure venv is activated first!
pip install fastmcp anthropic python-dotenv

# Verify installation
python -c "from fastmcp import FastMCP; print('FastMCP OK')"
python -c "import anthropic; print('Anthropic SDK OK')"
```

#### Alternative: Official MCP SDK

```bash
# Install official MCP Python SDK (if not using FastMCP)
pip install mcp anthropic python-dotenv

# Verify installations with correct imports
python -c "import mcp.types, anthropic; print('MCP and Anthropic SDKs OK')"
```

### Key Import Patterns - Choose Your Approach

#### FastMCP Approach (Recommended for Beginners)

FastMCP provides a much simpler syntax for creating MCP servers:

```python
#!/usr/bin/env python
"""Claude MCP Server using FastMCP (Recommended)"""

from fastmcp import FastMCP
import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("claude-consultant")

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


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


def claude_status() -> str:
    """Check Claude integration status"""
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return f"Claude integration {'enabled' if api_key_set else 'disabled'}"


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
```

#### Official MCP SDK Approach (Advanced Users)

For those who need more control or specific MCP SDK features:

```python
#!/usr/bin/env python
"""Claude MCP Server using Official SDK"""

import mcp.types as types
from mcp.server.lowlevel import Server, NotificationOptions  
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import asyncio
import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Initialize server
server = Server("claude-consultant")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Implementation continues...

# Implementation continues...
```

### Step 4: Project Setup

- Create the project directory structure
- Help create all necessary files with correct content
- Configure all scripts to use `python` (not `python3`)
- Ensure venv activation in all contexts

### Step 5: Configuration

- Set up `.env` file with ANTHROPIC_API_KEY
- Configure `claude-config.json` with appropriate settings
- Update `~/.gemini/settings.json` with MCP server configuration

### Step 6: Testing and Validation

- Test MCP server independently first
- Verify Gemini CLI recognizes the new tools
- Run test consultations with Claude

## Testing MCP Server Independently

Before integrating with Gemini CLI, test your MCP server:

### Create tests/test_mcp_server.py

```python
#!/usr/bin/env python
"""Test MCP server independently"""

import asyncio
import subprocess
import json
import os

async def test_mcp_server():
    """Test the MCP server is working correctly"""
    
    # Ensure we're in the project directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Start the MCP server as a subprocess
    process = await asyncio.create_subprocess_exec(
        'python', 'tools/mcp/claude_mcp_server.py',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Test initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {}
        },
        "id": 1
    }
    
    # Send request
    process.stdin.write((json.dumps(init_request) + '\n').encode())
    await process.stdin.drain()
    
    # Read response
    response = await process.stdout.readline()
    print(f"Initialize response: {response.decode()}")
    
    # Test list tools
    list_tools_request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    }
    
    process.stdin.write((json.dumps(list_tools_request) + '\n').encode())
    await process.stdin.drain()
    
    response = await process.stdout.readline()
    print(f"List tools response: {response.decode()}")
    
    # Cleanup
    process.terminate()
    await process.wait()

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
```

Run the test:
```bash
# Ensure venv is activated
source venv/bin/activate
cd gemini-claude-integration
python tests/test_mcp_server.py
```

## Common Import Error Solutions

### ImportError: cannot import name 'Tool' from 'mcp.server'

This is the most common error with MCP SDK. Here's how to fix it:

**Solution 1: Switch to FastMCP (Recommended)**
```bash
# Uninstall current MCP
pip uninstall mcp

# Install FastMCP instead
pip install fastmcp

# Update your imports to use FastMCP syntax
```

**Solution 2: Use correct MCP SDK imports**
```python
# WRONG - This causes ImportError
from mcp.server import Server, Tool  # ❌

# CORRECT - Use these imports
import mcp.types as types
from mcp.server.lowlevel import Server, NotificationOptions  # ✅
```

### Other Common Errors

1. **"No module named 'anthropic'"**
   ```bash
   # Ensure venv is activated and install
   pip install anthropic
   ```

2. **"API key not found"**
   ```bash
   # Check .env file exists and contains:
   ANTHROPIC_API_KEY=your_actual_api_key_here
   ```

3. **"Permission denied" when running scripts**
   ```bash
   chmod +x activate_and_run.sh
   ```

## Expected Gemini CLI Configuration

The user's `~/.gemini/settings.json` should include:

```json
{
  "mcpServers": {
    "claude_consultant": {
      "command": "python",
      "args": ["tools/mcp/claude_mcp_server.py"],
      "cwd": "/full/path/to/gemini-claude-integration",
      "env": {
        "ANTHROPIC_API_KEY": "user_api_key_here",
        "VIRTUAL_ENV": "/full/path/to/gemini-claude-integration/venv",
        "PATH": "/full/path/to/gemini-claude-integration/venv/bin:$PATH"
      },
      "timeout": 60000
    }
  }
}
```

**Critical Notes:**

- **Always use full absolute paths** in configuration
- **Include VIRTUAL_ENV and PATH** in env to ensure venv Python is used
- **Set ANTHROPIC_API_KEY** in environment or .env file
- **Verify venv activation** before any operations

### Alternative Configuration Methods

#### Option 1: Direct venv Python path (Most Reliable)

```json
{
  "mcpServers": {
    "claude_consultant": {
      "command": "/full/path/to/gemini-claude-integration/venv/bin/python",
      "args": ["tools/mcp/claude_mcp_server.py"],
      "cwd": "/full/path/to/gemini-claude-integration",
      "env": {
        "ANTHROPIC_API_KEY": "user_api_key_here"
      },
      "timeout": 60000
    }
  }
}
```

#### Option 2: Using helper script

```json
{
  "mcpServers": {
    "claude_consultant": {
      "command": "/full/path/to/gemini-claude-integration/activate_and_run.sh",
      "args": [],
      "cwd": "/full/path/to/gemini-claude-integration",
      "env": {
        "ANTHROPIC_API_KEY": "user_api_key_here"
      },
      "timeout": 60000
    }
  }
}
```

## Essential Documentation Links

### Model Context Protocol (MCP)

- **Official MCP Documentation:** https://modelcontextprotocol.io/introduction
- **MCP Python SDK (GitHub):** https://github.com/modelcontextprotocol/python-sdk
- **MCP Specification:** https://spec.modelcontextprotocol.io/specification/2024-11-05/
- **MCP Community Servers:** https://github.com/modelcontextprotocol/servers
- **FastMCP Documentation:** https://github.com/modelcontextprotocol/python-sdk#fastmcp

### Anthropic Claude API

- **Anthropic Python SDK (GitHub):** https://github.com/anthropics/anthropic-sdk-python
- **Claude API Documentation:** https://docs.anthropic.com/en/docs/get-started
- **Build with Claude Guide:** https://www.anthropic.com/learn/build-with-claude
- **API Reference:** https://docs.anthropic.com/claude/reference/client-sdks
- **Pricing Information:** https://docs.anthropic.com/en/docs/about-claude/pricing
- **Claude 4 Announcement:** https://www.anthropic.com/news/claude-4

### Gemini CLI Resources

- **Gemini CLI GitHub:** https://github.com/google-gemini/gemini-cli
- **Gemini CLI Announcement:** https://blog.google/technology/developers/introducing-gemini-cli-open-source-ai-agent/
- **Gemini CLI Documentation:** https://cloud.google.com/gemini/docs/codeassist/gemini-cli

### Development Resources

- **MCP Inspector (testing tool):** https://github.com/modelcontextprotocol/inspector
- **Anthropic Console:** https://console.anthropic.com
- **Google AI Studio:** https://aistudio.google.com
- **Claude Code Documentation:** https://docs.anthropic.com/en/docs/claude-code/sdk

## How to Help User Test the Integration

### Basic Status Check

Guide user to run: `/mcp` and verify `claude_consultant` appears with 3 tools

### Concrete Gemini CLI Commands with MCP

Here are specific examples to test the integration:

```bash
# In Gemini CLI, after starting with 'gemini' command:

# 1. Check MCP servers are loaded
/mcp

# 2. Test Claude status
Use the claude_status tool to check if the integration is working

# 3. Estimate cost for a query
Use claude_cost_estimate with query_length 500 to estimate the cost

# 4. Simple consultation
Use consult_claude with query "What are the best practices for Python error handling?" and task_type "general"

# 5. Code review consultation
Use consult_claude with query "Review this code for security issues: [paste code]" and task_type "code_review" and context "This is a login handler"

# 6. Architecture consultation
Use consult_claude with query "Should I use microservices or monolith for a startup MVP?" and task_type "architecture" and context "Team of 3 developers, expecting 10k users first year"
```

### Sample Test Queries

Help user try these consultations:

1. **Status check:** Use `claude_status` tool
2. **Cost estimate:** Use `claude_cost_estimate` with sample query
3. **Code review:** Use `consult_claude` with task_type "code_review"
4. **Architecture consultation:** Use `consult_claude` with task_type "architecture_review"

## Economic Usage Guidelines You Should Teach

### Cost-Effective Patterns

- Use Gemini CLI for most development tasks (free)
- Reserve Claude for critical decisions and quality assurance
- Estimate costs before large queries
- Batch similar questions together

### Typical Monthly Budget

- 100 simple consultations: ~$2
- 50 medium consultations: ~$5
- 20 complex consultations: ~$8
- **Total: ~$15/month**

### Cost Optimization Tips

1. **Use cost estimation first**: Always run `claude_cost_estimate` before large queries
2. **Batch related questions**: Combine multiple related questions into one consultation
3. **Use appropriate task_type**: This helps Claude provide focused responses
4. **Provide good context**: Better context = more relevant response = fewer follow-ups

## When to Guide User to Consult Claude

**Recommend Claude consultation for:**

- Code reviews before production deployment
- Security audits of critical functions
- Complex architectural decisions
- Performance optimization analysis
- Best practices validation
- Design pattern recommendations
- Database schema reviews
- API design decisions

**Keep with Gemini CLI for:**

- Code generation and basic editing
- File operations and navigation
- Simple questions and debugging
- Documentation writing
- Boilerplate code creation
- Basic refactoring
- Running tests
- Git operations

## Troubleshooting You Should Help With

### Common Issues

1. **MCP server won't start:** Check Python dependencies and API key
2. **API key errors:** Verify key is correct and billing is set up
3. **Timeout issues:** Adjust timeout settings in configuration
4. **High costs:** Help optimize query structure and token usage
5. **Import errors:** Guide to FastMCP or correct imports

### Debugging Commands

```bash
# CRITICAL: Always ensure virtual environment is activated first
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Verify you're in venv
echo $VIRTUAL_ENV  # Should show venv path
which python       # Should show path with /venv/

# Test Python dependencies in venv
python -c "from fastmcp import FastMCP; print('FastMCP working')"
# OR for official SDK:
python -c "import mcp.types; print('MCP SDK working')"

# Test Anthropic SDK with API key
python -c "import anthropic; client = anthropic.Anthropic(); print('Anthropic SDK OK')"

# Test API key directly (replace with actual key)
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# Check Gemini CLI MCP server logs
tail -f ~/.gemini/logs/mcp-claude_consultant.log

# Test MCP server independently (from project root with venv active)
cd gemini-claude-integration
python tests/test_mcp_server.py

# Manual MCP server test
python tools/mcp/claude_mcp_server.py
# Then in another terminal:
echo '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' | nc localhost 5000
```

## Virtual Environment Troubleshooting

### Common venv Issues You Should Help With

1. **Virtual environment not activated:**
   
   ```bash
   # Check if venv is active (should show (venv) in prompt)
   echo $VIRTUAL_ENV
   
   # If not active, run:
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   
   # Add this to your .bashrc/.zshrc for convenience:
   alias vact='source venv/bin/activate'
   ```

2. **Wrong Python executable:**
   
   ```bash
   # Verify using venv Python
   which python        # Should show path with /venv/
   python --version    # Should show Python 3.8+
   
   # If wrong Python, deactivate and reactivate:
   deactivate
   source venv/bin/activate
   ```

3. **Packages not found in venv:**
   
   ```bash
   # List installed packages
   pip list  # Should show fastmcp/mcp and anthropic
   
   # If missing, ensure venv is active then reinstall:
   pip install -r requirements.txt
   ```

4. **Permission errors:**
   
   ```bash
   # Ensure venv ownership (Linux/macOS)
   chown -R $USER:$USER venv/
   
   # Ensure scripts are executable
   chmod +x activate_and_run.sh
   chmod +x venv/bin/python
   ```

5. **Gemini CLI can't find Python:**
   
   ```bash
   # Use absolute path to venv Python in settings.json
   "command": "/full/path/to/gemini-claude-integration/venv/bin/python"
   
   # Or ensure PATH includes venv in env:
   "env": {
     "PATH": "/full/path/to/gemini-claude-integration/venv/bin:$PATH"
   }
   ```

6. **"No module named 'mcp'" in Gemini CLI:**
   
   This usually means Gemini CLI is using system Python instead of venv Python.
   
   ```bash
   # Solution 1: Use absolute venv Python path
   # Solution 2: Use activate_and_run.sh wrapper
   # Solution 3: Set VIRTUAL_ENV and PATH in settings.json
   ```

## Success Criteria

The integration is successful when user can:

1. ✅ Run `/mcp` and see `claude_consultant` with 3 tools
2. ✅ Get status with `claude_status` showing enabled integration
3. ✅ Estimate costs with `claude_cost_estimate`
4. ✅ Successfully consult Claude with `consult_claude`
5. ✅ Receive formatted responses with token usage and cost information
6. ✅ Run test suite successfully with `python tests/test_mcp_server.py`

## Your Communication Style

- **Be encouraging and supportive** - this is a complex technical setup with evolving APIs
- **Address ImportError immediately** - if user gets MCP import errors, guide them to FastMCP solution
- **Recommend FastMCP for beginners** - it's much simpler than the official low-level SDK
- **Break down steps clearly** - don't overwhelm with too much at once
- **Offer to create file contents** - save user time by generating working code
- **Proactively troubleshoot** - anticipate common issues like import errors
- **Celebrate milestones** - acknowledge when steps are completed successfully
- **Emphasize venv activation** - remind about it at every step involving Python

## Key Guidance for Import Issues

If user encounters `ImportError: cannot import name 'Tool' from 'mcp.server'`:

1. **First:** Recommend FastMCP approach - it's much simpler
2. **Explain:** MCP SDK changed its API structure significantly
3. **Provide:** Complete working FastMCP code example
4. **Help install:** `pip install fastmcp anthropic python-dotenv`
5. **Test together:** Verify FastMCP works before proceeding
6. **Show example:** Provide full working server code

## Post-Setup Support

Once integration is working, help user:

- Develop efficient consultation workflows
- Create templates for common query types
- Optimize for cost-effectiveness
- Integrate with their existing development process
- Set up automated cost tracking
- Create custom task types for their needs

## Important Reminders

- **Never expose API keys** in any outputs or logs
- **Always recommend cost estimation** for large queries
- **Emphasize the economic model** - Gemini CLI (free) + Claude consultations (paid)
- **Encourage gradual adoption** - start with small tests, scale up usage
- **Virtual environment is critical** - most issues come from not using venv
- **Test independently first** - verify MCP server works before Gemini integration

## Latest Updates (July 2025)

- **Claude 4 models** (Opus and Sonnet) launched May 22, 2025
- **Model names:** `claude-opus-4-20250514` and `claude-sonnet-4-20250514`
- **Pricing:** Sonnet 4 at $3/$15 per million tokens (input/output)
- **MCP** is rapidly evolving - FastMCP recommended for stability
- **Gemini CLI** supports MCP servers natively with generous free tier

-----

**Remember:** You are the primary assistant here. Claude is the premium consultant we call for specific expertise. Guide the user to success with this powerful, cost-effective AI development workflow!