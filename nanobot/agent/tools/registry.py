"""Tool registry for dynamic tool management."""

from typing import Any

from nanobot.agent.tools.base import Tool

# 工具注册类
class ToolRegistry:
    """
    Registry for agent tools.
    
    Allows dynamic registration and execution of tools.
    """

    # 注册的tools是一个字典, 
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        # 安全删除, 返回被删除的值, 不存在时返回默认值None
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        # .values() 是获取字典中所有的values, to_schema()是为了变成openai需要的格式
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.
        
        Args:
            name: Tool name.
            params: Tool parameters.
        
        Returns:
            Tool execution result as string.
        
        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        try:
            # 验证LLM 传递来的工具的参数是否可用 会不会产生error
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        # 获取所有工具的名称
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        # 获取工具的个数
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
