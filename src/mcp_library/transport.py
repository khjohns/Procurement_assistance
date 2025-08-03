import asyncio
from abc import ABC, abstractmethod

class JsonRpcTransport(ABC):
    """Abstract base class for a JSON-RPC transport layer."""
    @abstractmethod
    async def send(self, data: str) -> None:
        """Sends data to the server."""
        pass

    @abstractmethod
    async def receive(self) -> str:
        """Receives data from the server."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the transport connection."""
        pass

class SubprocessTransport(JsonRpcTransport):
    """Implements the transport layer over a subprocess stdin/stdout."""
    def __init__(self, process: asyncio.subprocess.Process):
        if process.stdin is None or process.stdout is None:
            raise ValueError("Process must have stdin and stdout pipes.")
        self.process = process

    async def send(self, data: str) -> None:
        self.process.stdin.write(data.encode('utf-8'))
        await self.process.stdin.drain()

    async def receive(self) -> str:
        line = await self.process.stdout.readline()
        return line.decode('utf-8')

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
