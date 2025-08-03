from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class JsonRpcRequest:
    """Represents a JSON-RPC 2.0 Request."""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params
        }
        if self.id is not None:
            d["id"] = self.id
        return d

@dataclass
class JsonRpcResponse:
    """Represents a JSON-RPC 2.0 Response."""
    id: Optional[int]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JsonRpcResponse':
        return cls(
            result=data.get("result"),
            error=data.get("error"),
            id=data.get("id")
        )

    def is_error(self) -> bool:
        return self.error is not None
