#!/usr/bin/env python3
"""
Минимальный MCP сервер для тестирования подключения.
Использует чистый MCP SDK без FastMCP.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


async def main():
    """Запуск минимального MCP сервера."""
    server = Server("test-server")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Возвращает список доступных инструментов."""
        return [
            Tool(
                name="hello",
                description="Returns a hello message",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name to greet"
                        }
                    },
                    "required": ["name"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Обработка вызова инструмента."""
        if name == "hello":
            user_name = arguments.get("name", "World")
            return [TextContent(type="text", text=f"Hello, {user_name}!")]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # Запуск сервера
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
