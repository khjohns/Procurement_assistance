# ADR-001: Transition from `fastmcp` to Custom FastAPI RPC Gateway

## Status: Accepted

## Context:
The project initially aimed to use the `fastmcp` library for building a central MCP Gateway to route and authorize tool calls from AI agents. This was intended to provide a robust and protocol-compliant way to build an MCP server integrated with FastAPI. However, repeated attempts to implement the gateway using `fastmcp` consistently resulted in instability, `404 Not Found` errors, empty responses, and significant debugging challenges. The library proved to be too rigid and opaque for effective troubleshooting, consuming disproportionate development time.

## Decision:
To ensure stability, control, and efficient development, the decision was made to abandon the `fastmcp` library and implement a custom RPC Gateway using pure FastAPI. This gateway would manually handle JSON-RPC parsing, method routing, and authorization (ACL) logic.

## Consequences:

*   **Positive:**
    *   **Immediate Stability:** The custom FastAPI gateway demonstrated immediate reliability and predictable behavior.
    *   **Full Control:** Developers gained complete control over the request-response flow, enabling straightforward debugging and customization.
    *   **Pragmatic Solution:** Prioritized a working, understandable solution over a theoretically elegant but practically unworkable library.
    *   **Enhanced Security:** Manual implementation of ACL allowed for precise control over agent authorization.

*   **Negative:**
    *   **Increased Manual Effort:** Requires manual implementation of JSON-RPC protocol handling, routing, and ACL, which `fastmcp` was designed to abstract.
    *   **Potential for Boilerplate:** More code might be needed for features that `fastmcp` would have provided out-of-the-box.

*   **Risks:**
    *   **Maintenance Burden:** The custom implementation might require more maintenance compared to a well-supported library (if `fastmcp` were stable).
    *   **Feature Parity:** May need to manually implement advanced MCP features if they become necessary in the future.

## Alternatives Considered:

1.  **Continue Debugging `fastmcp`:**
    *   **Reason for Rejection:** Excessive time was already spent without a breakthrough. The library's opacity made effective debugging impossible, hindering overall project progress.
2.  **Separate HTTP and MCP Servers:**
    *   **Reason for Rejection:** While offering full separation, it would introduce additional operational complexity (managing two separate services) without resolving the core instability issues encountered with `fastmcp` itself.
3.  **Direct Database Access from Agents:**
    *   **Reason for Rejection:** This was the initial architecture that the gateway was designed to replace. It poses significant security risks (SQL injection, lack of centralized access control), makes auditing difficult, and hinders scalability.

## References:
*   `docs/archived/FastMCP Gateway - Løsningsoversikt.md`
*   `docs/archived/Feilsøkingssammendrag Implementering av MCP Gateway med FastMCP.md`
*   `docs/archived/gateway_implementation_notes.md`
*   `docs/archived/GEMINI_RPCGATEWAY.md`