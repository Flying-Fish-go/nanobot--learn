"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# @dataclass是专门用来快速定义“主要用来存数据”的类, 帮我自动生成大量的模板代码 如__init__,  __repr__等

@dataclass
class InboundMessage:
    """Message received from a chat channel."""
    
    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    timestamp: datetime = field(default_factory=datetime.now) # 消息创建的时间, 默认是当前时间
    media: list[str] = field(default_factory=list)  # Media URLs// 附件列表。Telegram收到图片、语音、 文件会先下载到 ~/.nanobot/media/
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data 各渠道自己的附加数据, 结构不固定

    # 决定一条消息属于那段对话. 也就是读写哪一份聊天记录
    # @property是Python内置的装饰器, 作用是把一个方法变成可以像属性一样读取的东西 e.g. m.session_key
    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


