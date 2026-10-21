"""Async message queue for decoupled channel-agent communication."""
"""
    两个队列, 加上往里放 从里取的方法。
    async def foo() 调用foo()不会立即执行, 只会得到一个协程对象, 相当于一个还没开始跑的任务
    await foo() 相当于 在这里等结果 等的时候协程让给别人用
"""
import asyncio
from typing import Callable, Awaitable

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.
    
    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """
    
    def __init__(self):
        # BlockingQueue<InboundMessage> inbound = new LinkedBlockingQueue<>();
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        # private final Map<String, List<Function<OutboundMessage, CompletableFuture<Void>>>> outboundSubscribers = new HashMap<>();
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}
        # dict[str, list[X]] = map<String, List<X>>
        # Callable[[OutboundMessage], Awaitable[None]] = Function<OutboundMessage, CompletableFuture<Void>>意思是"一个接收 OutboundMessage 的异步回调函数"
        # [OutboundMessage]是参数类型, Awaitable[None]是返回类型
        self._running = False
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)  # ≈ queue.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()  # ≈ queue.take()
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    # 注册某个渠道的消息交给谁处理
    def subscribe_outbound(
        self, 
        channel: str, 
        callback: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to outbound messages for a specific channel."""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)

    # 循环取消息，按渠道名调用对应回调
    async def dispatch_outbound(self) -> None:
        """
        Dispatch outbound messages to subscribed channels.
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                msg = await asyncio.wait_for(self.outbound.get(), timeout=1.0)
                subscribers = self._outbound_subscribers.get(msg.channel, [])
                for callback in subscribers:
                    try:
                        await callback(msg)
                    except Exception as e:
                        logger.error(f"Error dispatching to {msg.channel}: {e}")
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the dispatcher loop."""
        self._running = False
    
    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()
    
    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
