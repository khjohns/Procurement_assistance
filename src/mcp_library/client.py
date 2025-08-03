import asyncio
import json
import structlog
from typing import Dict, Any, Optional, List, Callable

from src.mcp_library.core import JsonRpcRequest, JsonRpcResponse
from src.mcp_library.transport import JsonRpcTransport

logger = structlog.get_logger()

class JsonRpcClient:
    """A generic JSON-RPC 2.0 client."""
    def __init__(self, transport: JsonRpcTransport):
        self.transport = transport
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._notification_handlers: Dict[str, List[Callable]] = {}

    async def start(self):
        """Starts the client's response reader task."""
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self):
        """Stops the client and cleans up resources."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        await self.transport.close()

    async def _read_loop(self):
        """Continuously reads and processes messages from the transport."""
        while True:
            try:
                line = await self.transport.receive()
                if not line:
                    logger.info("Transport connection closed.")
                    break
                
                try:
                    data = json.loads(line)
                    if "method" in data and "id" not in data:
                        await self._handle_notification(data)
                    elif "id" in data:
                        self._handle_response(data)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON", line=line.strip())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in read loop", error=str(e), exc_info=True)
                break

    def _handle_response(self, data: Dict[str, Any]):
        response = JsonRpcResponse.from_dict(data)
        future = self._pending_requests.pop(response.id, None)
        if future and not future.done():
            if response.is_error():
                future.set_exception(Exception(f"RPC Error {response.error.get('code')}: {response.error.get('message')}"))
            else:
                future.set_result(response.result)

    async def _handle_notification(self, data: Dict[str, Any]):
        method = data.get("method", "")
        params = data.get("params", {})
        if method in self._notification_handlers:
            for handler in self._notification_handlers[method]:
                try:
                    # Support both sync and async handlers
                    if asyncio.iscoroutinefunction(handler):
                        await handler(params)
                    else:
                        handler(params)
                except Exception as e:
                    logger.error("Notification handler failed", method=method, error=str(e))

    def on_notification(self, method: str, handler: Callable):
        """Registers a handler for a specific notification method."""
        self._notification_handlers.setdefault(method, []).append(handler)

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Sends a request and waits for a response."""
        self._request_id += 1
        req = JsonRpcRequest(method=method, params=params or {}, id=self._request_id)
        
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[req.id] = future
        
        try:
            await self.transport.send(json.dumps(req.to_dict()) + "\n")
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req.id, None)
            logger.error("Request timed out", method=method, request_id=req.id)
            raise

    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Sends a notification without waiting for a response."""
        notif = JsonRpcRequest(method=method, params=params or {})
        await self.transport.send(json.dumps(notif.to_dict()) + "\n")
