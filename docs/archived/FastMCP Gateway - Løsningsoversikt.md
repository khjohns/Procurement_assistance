# FastMCP Gateway - Løsningsoversikt

## Problemet

Koden brukte feil syntaks: `@mcp.app.get()` som ikke eksisterer i FastMCP.

## Løsningen

FastMCP tilbyr `mcp.http_app()` for å få en ASGI-kompatibel app som kan monteres i FastAPI.

## Implementeringsalternativer

### 1. **Kombinert FastAPI + FastMCP (Anbefalt for Gateway)**

```python
# Opprett FastAPI og FastMCP separat
app = FastAPI()
mcp = FastMCP("MCP Gateway")

# Definer HTTP endpoints på FastAPI
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Definer MCP tools på FastMCP
@mcp.tool()
async def route_to_service(...):
    # Tool implementation

# Monter MCP på FastAPI
mcp_app = mcp.http_app(path='/mcp')
app.mount("/mcp", mcp_app)

# Kjør FastAPI
uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Fordeler:**

- Standard HTTP endpoints på rot (`/health`, `/services`)
- MCP protokoll på `/mcp`
- Full fleksibilitet

### 2. **Ren FastMCP Server**

```python
mcp = FastMCP("MCP Gateway")

# Alt er MCP tools
@mcp.tool()
async def health_check():
    return {"status": "healthy"}

# Kjør direkte
mcp.run(host="0.0.0.0", port=8000)
```

**Fordeler:**

- Enklere kode
- Alt håndteres gjennom MCP-protokollen

**Ulemper:**

- Ingen standard HTTP endpoints
- Krever MCP-klient for all kommunikasjon

### 3. **Separate Servere**

Kjør HTTP API og MCP på forskjellige porter hvis du trenger full separasjon.

## Endepunkter i Løsning 1

- `GET /health` - Standard HTTP health check
- `GET /services` - Liste over downstream services
- `POST /mcp` - MCP protokoll endpoint
  - `initialize` - Start MCP session
  - `tools/list` - List tilgjengelige verktøy
  - `tools/call` - Kall et verktøy

## Testing

```bash
# HTTP endpoints
curl http://localhost:8000/health
curl http://localhost:8000/services

# MCP protokoll
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'
```

## Viktige Punkter

1. **FastMCP eksponerer IKKE `.app` direkte** - bruk `mcp.http_app()` i stedet
2. **Montering krever path parameter** - `mcp.http_app(path='/mcp')`
3. **Lifespan management** - Kombiner lifespans hvis begge apps har det
4. **FastMCP.run()** - Bruker uvicorn internt, støtter samme parametere

## Neste Steg

1. Implementer autentisering/autorisasjon
2. Legg til service discovery mekanisme
3. Implementer caching for downstream services
4. Legg til monitoring og metrics

## Kode
**gateway.py - Korrekt implementering basert på FastMCP dokumentasjon**
```python
# gateway.py - Korrekt implementering basert på FastMCP dokumentasjon

from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager

# Configure logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration

DOWNSTREAM_SERVICES = {
"service1": "http://localhost:8001",
"service2": "http://localhost:8002",
}

# Create the main FastAPI app

app = FastAPI(title="MCP Gateway", version="1.0.0")

# Create the FastMCP instance

mcp = FastMCP("MCP Gateway")

# Standard HTTP endpoints på hovedappen

@app.get("/health")
async def health_check():
"""Standard health check endpoint"""
return {
"status": "healthy",
"service": "mcp-gateway",
"version": "1.0.0"
}

@app.get("/services")
async def list_services():
"""List available downstream services"""
return {
"services": list(DOWNSTREAM_SERVICES.keys()),
"endpoints": DOWNSTREAM_SERVICES
}

# MCP Tools - registered using fastmcp decorators

@mcp.tool()
async def route_to_service(service: str, tool_name: str, arguments: dict) -> dict:

"""Route a tool call to a downstream MCP service

Args:
    service: Name of the downstream service
    tool_name: Name of the tool to call
    arguments: Arguments to pass to the tool
"""
if service not in DOWNSTREAM_SERVICES:
    return {
        "error": f"Service '{service}' not found",
        "available_services": list(DOWNSTREAM_SERVICES.keys())
    }

service_url = DOWNSTREAM_SERVICES[service]

try:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{service_url}/mcp/tools/{tool_name}",
            json={"arguments": arguments},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

except httpx.RequestError as e:
    logger.error(f"Request to {service} failed: {e}")
    return {"error": f"Failed to connect to service '{service}': {str(e)}"}

except httpx.HTTPStatusError as e:
    logger.error(f"HTTP error from {service}: {e}")
    return {"error": f"Service '{service}' returned error: {e.response.status_code}"}

@mcp.tool()
async def list_downstream_tools(service: str) -> dict:

"""
List available tools from a downstream service

Args:
    service: Name of the downstream service to query
"""

if service not in DOWNSTREAM_SERVICES:
    return {
        "error": f"Service '{service}' not found",
        "available_services": list(DOWNSTREAM_SERVICES.keys())
    }

service_url = DOWNSTREAM_SERVICES[service]

try:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{service_url}/mcp/tools",
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()

except Exception as e:
    logger.error(f"Failed to list tools from {service}: {e}")
    return {"error": f"Failed to get tools from '{service}': {str(e)}"}

@mcp.tool()
async def ping_service(service: str) -> dict:

"""
Ping a downstream service to check if it’s available

Args:
    service: Name of the service to ping
"""

if service not in DOWNSTREAM_SERVICES:
    return {"error": f"Service '{service}' not configured"}

service_url = DOWNSTREAM_SERVICES[service]

try:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{service_url}/health",
            timeout=5.0
        )
        return {
            "service": service,
            "status": "up" if response.status_code == 200 else "down",
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000
        }
except Exception as e:
    return {
        "service": service,
        "status": "down",
        "error": str(e)
    }

# MCP Resources
@mcp.resource("gateway://config")
async def get_gateway_config() -> str:
"""Get gateway configuration"""
return f"""
Gateway Configuration:

- Services: {len(DOWNSTREAM_SERVICES)}
- Endpoints: {list(DOWNSTREAM_SERVICES.keys())}
"""

# Get the MCP HTTP app
mcp_app = mcp.http_app(path='/mcp')

# Mount the MCP app on the main FastAPI app
app.mount("/mcp", mcp_app)
```

**main.py - Korrekt måte å kjøre kombinert FastAPI + FastMCP server**
```python
# main.py - Korrekt måte å kjøre kombinert FastAPI + FastMCP server

import uvicorn
from tools.mcp_gateway.gateway import app

if __name__ == "__main__":
# Kjør FastAPI appen som har MCP montert på /mcp
uvicorn.run(
app,  # Bruk FastAPI app, ikke mcp
host="0.0.0.0",
port=8000,
log_level="info"
)
```

**gateway_with_lifespan.py - Hvis du trenger lifespan management**
```python
# gateway_with_lifespan.py - Hvis du trenger lifespan management

from fastapi import FastAPI
from fastmcp import FastMCP
from contextlib import asynccontextmanager
import httpx
import logging
from typing import Dict, Any

# Configure logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration

DOWNSTREAM_SERVICES = {
"service1": "http://localhost:8001",
"service2": "http://localhost:8002",
}

# Create MCP server

mcp = FastMCP("MCP Gateway")

# Register MCP tools

@mcp.tool()
async def route_to_service(service: str, tool_name: str, arguments: dict) -> dict:
"""Route a tool call to a downstream MCP service"""
if service not in DOWNSTREAM_SERVICES:
return {
"error": f"Service '{service}' not found",
"available_services": list(DOWNSTREAM_SERVICES.keys())
}

service_url = DOWNSTREAM_SERVICES[service]

try:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{service_url}/mcp/tools/{tool_name}",
            json={"arguments": arguments},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
except Exception as e:
    logger.error(f"Error routing to {service}: {e}")
    return {"error": str(e)}

# Get MCP HTTP app

mcp_app = mcp.http_app(path='/mcp')

# Define your app’s lifespan

@asynccontextmanager
async def app_lifespan(app: FastAPI):
# Startup
logger.info("Starting up gateway…")
# Initialize any resources (database, cache, etc.)

yield

# Shutdown
logger.info("Shutting down gateway...")
# Clean up resources

# Combine lifespans if MCP has its own

@asynccontextmanager
async def combined_lifespan(app: FastAPI):
# Run both lifespans
async with app_lifespan(app):
# MCP app lifespan (if it has one)
if hasattr(mcp_app, 'lifespan'):
async with mcp_app.lifespan(app):
yield
else:
yield

# Create FastAPI app with combined lifespan

app = FastAPI(
title="MCP Gateway",
version="1.0.0",
lifespan=combined_lifespan
)

# Standard HTTP endpoints

@app.get("/health")
async def health_check():
return {"status": "healthy", "service": "mcp-gateway"}

@app.get("/services")
async def list_services():
return {"services": list(DOWNSTREAM_SERVICES.keys())}

# Mount MCP app

app.mount("/mcp", mcp_app)
```

**test_gateway.sh - Test at gateway fungerer korrekt**
```bash
#!/bin/bash

# test_gateway.sh - Test at gateway fungerer korrekt

#OBS: syntaks/tegn kan være feil.

echo "Testing MCP Gateway Endpoints"
echo "============================"

# Test standard HTTP health endpoint

echo -e "\n1. Testing HTTP health endpoint:"
curl -X GET http://localhost:8000/health

# Test services list endpoint

echo -e "\n\n2. Testing services list endpoint:"
curl -X GET http://localhost:8000/services

# Test MCP server info

echo -e "\n\n3. Testing MCP server info:"
curl -X POST http://localhost:8000/mcp   
-H "Content-Type: application/json"   
-d '{
"jsonrpc": "2.0",
"method": "initialize",
"params": {
"protocolVersion": "0.1.0",
"capabilities": {},
"clientInfo": {
"name": "test-client",
"version": "1.0.0"
}
},
"id": 1
}'

# List MCP tools

echo -e "\n\n4. Testing MCP tools list:"
curl -X POST http://localhost:8000/mcp   
-H "Content-Type: application/json"   
-d '{
"jsonrpc": "2.0",
"method": "tools/list",
"params": {},
"id": 2
}'

# Call a tool

echo -e "\n\n5. Testing MCP tool call (ping_service):"
curl -X POST http://localhost:8000/mcp   
-H "Content-Type: application/json"   
-d '{
"jsonrpc": "2.0",
"method": "tools/call",
"params": {
"name": "ping_service",
"arguments": {
"service": "service1"
}
},
"id": 3
}’
```

**test_gateway_client.py - Test MCP Gateway med Python**
```python
# test_gateway_client.py - Test MCP Gateway med Python

import asyncio
import httpx
import json

async def test_gateway():
"""Test MCP Gateway endpoints"""
base_url = "http://localhost:8000"

async with httpx.AsyncClient() as client:
    # 1. Test HTTP health endpoint
    print("1. Testing HTTP health endpoint:")
    response = await client.get(f"{base_url}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # 2. Test services list
    print("\n2. Testing services list:")
    response = await client.get(f"{base_url}/services")
    print(f"   Response: {response.json()}")
    
    # 3. Initialize MCP session
    print("\n3. Initializing MCP session:")
    response = await client.post(
        f"{base_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
    )
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    # 4. List MCP tools
    print("\n4. Listing MCP tools:")
    response = await client.post(
        f"{base_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
    )
    tools_response = response.json()
    print(f"   Available tools:")
    if "result" in tools_response and "tools" in tools_response["result"]:
        for tool in tools_response["result"]["tools"]:
            print(f"     - {tool['name']}: {tool.get('description', 'No description')}")
    
    # 5. Call ping_service tool
    print("\n5. Calling ping_service tool:")
    response = await client.post(
        f"{base_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ping_service",
                "arguments": {
                    "service": "service1"
                }
            },
            "id": 3
        }
    )
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    # 6. Test routing to downstream service
    print("\n6. Testing route_to_service tool:")
    response = await client.post(
        f"{base_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "route_to_service",
                "arguments": {
                    "service": "service1",
                    "tool_name": "example_tool",
                    "arguments": {"param": "value"}
                }
            },
            "id": 4
        }
    )
    print(f"   Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
asyncio.run(test_gateway())
```

# FastMCP

## Docs

- [null](https://gofastmcp.com/changelog.md)
- [Bearer Token Authentication](https://gofastmcp.com/clients/auth/bearer.md): Authenticate your FastMCP client with a Bearer token.
- [OAuth Authentication](https://gofastmcp.com/clients/auth/oauth.md): Authenticate your FastMCP client via OAuth 2.1.
- [The FastMCP Client](https://gofastmcp.com/clients/client.md): Programmatic client for interacting with MCP servers through a well-typed, Pythonic interface.
- [User Elicitation](https://gofastmcp.com/clients/elicitation.md): Handle server-initiated user input requests with structured schemas.
- [Server Logging](https://gofastmcp.com/clients/logging.md): Receive and handle log messages from MCP servers.
- [Message Handling](https://gofastmcp.com/clients/messages.md): Handle MCP messages, requests, and notifications with custom message handlers.
- [Progress Monitoring](https://gofastmcp.com/clients/progress.md): Handle progress notifications from long-running server operations.
- [Prompts](https://gofastmcp.com/clients/prompts.md): Use server-side prompt templates with automatic argument serialization.
- [Resource Operations](https://gofastmcp.com/clients/resources.md): Access static and templated resources from MCP servers.
- [Client Roots](https://gofastmcp.com/clients/roots.md): Provide local context and resource boundaries to MCP servers.
- [LLM Sampling](https://gofastmcp.com/clients/sampling.md): Handle server-initiated LLM sampling requests.
- [Tool Operations](https://gofastmcp.com/clients/tools.md): Discover and execute server-side tools with the FastMCP client.
- [Client Transports](https://gofastmcp.com/clients/transports.md): Configure how FastMCP Clients connect to and communicate with servers.
- [Community Showcase](https://gofastmcp.com/community/showcase.md): High-quality projects and examples from the FastMCP community
- [Running Your FastMCP Server](https://gofastmcp.com/deployment/running-server.md): Learn how to run and deploy your FastMCP server using various transport protocols like STDIO, Streamable HTTP, and SSE.
- [Installation](https://gofastmcp.com/getting-started/installation.md)
- [Quickstart](https://gofastmcp.com/getting-started/quickstart.md)
- [Welcome to FastMCP 2.0!](https://gofastmcp.com/getting-started/welcome.md): The fast, Pythonic way to build MCP servers and clients.
- [Anthropic API 🤝 FastMCP](https://gofastmcp.com/integrations/anthropic.md): Call FastMCP servers from the Anthropic API
- [ChatGPT 🤝 FastMCP](https://gofastmcp.com/integrations/chatgpt.md): Connect FastMCP servers to ChatGPT Deep Research
- [Claude Code 🤝 FastMCP](https://gofastmcp.com/integrations/claude-code.md): Install and use FastMCP servers in Claude Code
- [Claude Desktop 🤝 FastMCP](https://gofastmcp.com/integrations/claude-desktop.md): Call FastMCP servers from Claude Desktop
- [Cursor 🤝 FastMCP](https://gofastmcp.com/integrations/cursor.md): Install and use FastMCP servers in Cursor
- [Eunomia Authorization 🤝 FastMCP](https://gofastmcp.com/integrations/eunomia-authorization.md): Add policy-based authorization to your FastMCP servers
- [FastAPI 🤝 FastMCP](https://gofastmcp.com/integrations/fastapi.md): Integrate FastMCP with FastAPI applications
- [Gemini SDK 🤝 FastMCP](https://gofastmcp.com/integrations/gemini.md): Call FastMCP servers from the Google Gemini SDK
- [MCP JSON Configuration 🤝 FastMCP](https://gofastmcp.com/integrations/mcp-json-configuration.md): Generate standard MCP configuration files for any compatible client
- [OpenAI API 🤝 FastMCP](https://gofastmcp.com/integrations/openai.md): Call FastMCP servers from the OpenAI API
- [OpenAPI 🤝 FastMCP](https://gofastmcp.com/integrations/openapi.md): Generate MCP servers from any OpenAPI specification
- [Permit.io Authorization 🤝 FastMCP](https://gofastmcp.com/integrations/permit.md): Add fine-grained authorization to your FastMCP servers with Permit.io
- [Starlette / ASGI 🤝 FastMCP](https://gofastmcp.com/integrations/starlette.md): Integrate FastMCP servers into ASGI applications
- [FastMCP CLI](https://gofastmcp.com/patterns/cli.md): Learn how to use the FastMCP command-line interface
- [Contrib Modules](https://gofastmcp.com/patterns/contrib.md): Community-contributed modules extending FastMCP
- [Decorating Methods](https://gofastmcp.com/patterns/decorating-methods.md): Properly use instance methods, class methods, and static methods with FastMCP decorators.
- [HTTP Requests](https://gofastmcp.com/patterns/http-requests.md): Accessing and using HTTP requests in FastMCP servers
- [Testing MCP Servers](https://gofastmcp.com/patterns/testing.md): Learn how to test your FastMCP servers effectively
- [Tool Transformation](https://gofastmcp.com/patterns/tool-transformation.md): Create enhanced tool variants with modified schemas, argument mappings, and custom behavior.
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-cli-__init__.md)
- [claude](https://gofastmcp.com/python-sdk/fastmcp-cli-claude.md)
- [cli](https://gofastmcp.com/python-sdk/fastmcp-cli-cli.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-cli-install-__init__.md)
- [claude_code](https://gofastmcp.com/python-sdk/fastmcp-cli-install-claude_code.md)
- [claude_desktop](https://gofastmcp.com/python-sdk/fastmcp-cli-install-claude_desktop.md)
- [cursor](https://gofastmcp.com/python-sdk/fastmcp-cli-install-cursor.md)
- [mcp_json](https://gofastmcp.com/python-sdk/fastmcp-cli-install-mcp_json.md)
- [shared](https://gofastmcp.com/python-sdk/fastmcp-cli-install-shared.md)
- [run](https://gofastmcp.com/python-sdk/fastmcp-cli-run.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-client-__init__.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-client-auth-__init__.md)
- [bearer](https://gofastmcp.com/python-sdk/fastmcp-client-auth-bearer.md)
- [oauth](https://gofastmcp.com/python-sdk/fastmcp-client-auth-oauth.md)
- [client](https://gofastmcp.com/python-sdk/fastmcp-client-client.md)
- [elicitation](https://gofastmcp.com/python-sdk/fastmcp-client-elicitation.md)
- [logging](https://gofastmcp.com/python-sdk/fastmcp-client-logging.md)
- [messages](https://gofastmcp.com/python-sdk/fastmcp-client-messages.md)
- [oauth_callback](https://gofastmcp.com/python-sdk/fastmcp-client-oauth_callback.md)
- [progress](https://gofastmcp.com/python-sdk/fastmcp-client-progress.md)
- [roots](https://gofastmcp.com/python-sdk/fastmcp-client-roots.md)
- [sampling](https://gofastmcp.com/python-sdk/fastmcp-client-sampling.md)
- [transports](https://gofastmcp.com/python-sdk/fastmcp-client-transports.md)
- [exceptions](https://gofastmcp.com/python-sdk/fastmcp-exceptions.md)
- [mcp_config](https://gofastmcp.com/python-sdk/fastmcp-mcp_config.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-prompts-__init__.md)
- [prompt](https://gofastmcp.com/python-sdk/fastmcp-prompts-prompt.md)
- [prompt_manager](https://gofastmcp.com/python-sdk/fastmcp-prompts-prompt_manager.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-resources-__init__.md)
- [resource](https://gofastmcp.com/python-sdk/fastmcp-resources-resource.md)
- [resource_manager](https://gofastmcp.com/python-sdk/fastmcp-resources-resource_manager.md)
- [template](https://gofastmcp.com/python-sdk/fastmcp-resources-template.md)
- [types](https://gofastmcp.com/python-sdk/fastmcp-resources-types.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-server-__init__.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-server-auth-__init__.md)
- [auth](https://gofastmcp.com/python-sdk/fastmcp-server-auth-auth.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-server-auth-providers-__init__.md)
- [bearer](https://gofastmcp.com/python-sdk/fastmcp-server-auth-providers-bearer.md)
- [bearer_env](https://gofastmcp.com/python-sdk/fastmcp-server-auth-providers-bearer_env.md)
- [in_memory](https://gofastmcp.com/python-sdk/fastmcp-server-auth-providers-in_memory.md)
- [context](https://gofastmcp.com/python-sdk/fastmcp-server-context.md)
- [dependencies](https://gofastmcp.com/python-sdk/fastmcp-server-dependencies.md)
- [elicitation](https://gofastmcp.com/python-sdk/fastmcp-server-elicitation.md)
- [http](https://gofastmcp.com/python-sdk/fastmcp-server-http.md)
- [low_level](https://gofastmcp.com/python-sdk/fastmcp-server-low_level.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-__init__.md)
- [error_handling](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-error_handling.md)
- [logging](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-logging.md)
- [middleware](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-middleware.md)
- [rate_limiting](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-rate_limiting.md)
- [timing](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-timing.md)
- [openapi](https://gofastmcp.com/python-sdk/fastmcp-server-openapi.md)
- [proxy](https://gofastmcp.com/python-sdk/fastmcp-server-proxy.md)
- [server](https://gofastmcp.com/python-sdk/fastmcp-server-server.md)
- [settings](https://gofastmcp.com/python-sdk/fastmcp-settings.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-tools-__init__.md)
- [tool](https://gofastmcp.com/python-sdk/fastmcp-tools-tool.md)
- [tool_manager](https://gofastmcp.com/python-sdk/fastmcp-tools-tool_manager.md)
- [tool_transform](https://gofastmcp.com/python-sdk/fastmcp-tools-tool_transform.md)
- [__init__](https://gofastmcp.com/python-sdk/fastmcp-utilities-__init__.md)
- [cache](https://gofastmcp.com/python-sdk/fastmcp-utilities-cache.md)
- [cli](https://gofastmcp.com/python-sdk/fastmcp-utilities-cli.md)
- [components](https://gofastmcp.com/python-sdk/fastmcp-utilities-components.md)
- [exceptions](https://gofastmcp.com/python-sdk/fastmcp-utilities-exceptions.md)
- [http](https://gofastmcp.com/python-sdk/fastmcp-utilities-http.md)
- [inspect](https://gofastmcp.com/python-sdk/fastmcp-utilities-inspect.md)
- [json_schema](https://gofastmcp.com/python-sdk/fastmcp-utilities-json_schema.md)
- [json_schema_type](https://gofastmcp.com/python-sdk/fastmcp-utilities-json_schema_type.md)
- [logging](https://gofastmcp.com/python-sdk/fastmcp-utilities-logging.md)
- [mcp_config](https://gofastmcp.com/python-sdk/fastmcp-utilities-mcp_config.md)
- [openapi](https://gofastmcp.com/python-sdk/fastmcp-utilities-openapi.md)
- [tests](https://gofastmcp.com/python-sdk/fastmcp-utilities-tests.md)
- [types](https://gofastmcp.com/python-sdk/fastmcp-utilities-types.md)
- [Token Verification](https://gofastmcp.com/servers/auth/verifiers.md): Secure your FastMCP server's HTTP endpoints by validating JWT tokens.
- [Server Composition](https://gofastmcp.com/servers/composition.md): Combine multiple FastMCP servers into a single, larger application using mounting and importing.
- [MCP Context](https://gofastmcp.com/servers/context.md): Access MCP capabilities like logging, progress, and resources within your MCP objects.
- [User Elicitation](https://gofastmcp.com/servers/elicitation.md): Request structured input from users during tool execution through the MCP context.
- [Server Logging](https://gofastmcp.com/servers/logging.md): Send log messages back to MCP clients through the context.
- [MCP Middleware](https://gofastmcp.com/servers/middleware.md): Add cross-cutting functionality to your MCP server with middleware that can inspect, modify, and respond to all MCP requests and responses.
- [Progress Reporting](https://gofastmcp.com/servers/progress.md): Update clients on the progress of long-running operations through the MCP context.
- [Prompts](https://gofastmcp.com/servers/prompts.md): Create reusable, parameterized prompt templates for MCP clients.
- [Proxy Servers](https://gofastmcp.com/servers/proxy.md): Use FastMCP to act as an intermediary or change transport for other MCP servers.
- [Resources & Templates](https://gofastmcp.com/servers/resources.md): Expose data sources and dynamic content generators to your MCP client.
- [LLM Sampling](https://gofastmcp.com/servers/sampling.md): Request the client's LLM to generate text based on provided messages through the MCP context.
- [The FastMCP Server](https://gofastmcp.com/servers/server.md): The core FastMCP server class for building MCP applications with tools, resources, and prompts.
- [Tools](https://gofastmcp.com/servers/tools.md): Expose functions as executable capabilities for your MCP client.
- [How to Create an MCP Server in Python](https://gofastmcp.com/tutorials/create-mcp-server.md): A step-by-step guide to building a Model Context Protocol (MCP) server using Python and FastMCP, from basic tools to dynamic resources.
- [What is the Model Context Protocol (MCP)?](https://gofastmcp.com/tutorials/mcp.md): An introduction to the core concepts of the Model Context Protocol (MCP), explaining what it is, why it's useful, and how it works.
- [How to Connect an LLM to a REST API](https://gofastmcp.com/tutorials/rest-api.md): A step-by-step guide to making any REST API with an OpenAPI spec available to LLMs using FastMCP.
- [FastMCP Updates](https://gofastmcp.com/updates.md)