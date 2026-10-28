# 仓库协作指南

本文件供 Codex 等编码助手在本仓库开发时使用，依据 `CLAUDE.md` 整理。修改约定时请同时检查两份文件，避免内容冲突；实现细节以当前源码和项目配置为准。

## 项目与改动原则

nanobot（PyPI 包名 `nanobot-ai`）是一个刻意保持小巧、易读的个人 AI 助手：核心是 LLM 工具调用循环，连接 Telegram、WhatsApp、定时任务和周期心跳。

- 优先做最小、直接的修改，避免为简单需求引入新抽象或框架。
- Python 要求 **3.11+**；WhatsApp 的 TypeScript 桥接服务要求 **Node.js 20+**（以 `bridge/package.json` 为准）。
- 根目录的 `AGENTS.md` 是开发指南；`workspace/AGENTS.md` 是 nanobot 运行时提示词的模板。修改开发约定时不要误改运行时模板。

## 与用户沟通和解释 Python

用户正在从 Java 转向 Python，仍在学习 Python。**使用中文回复**。

当用户的问题或正在讨论的代码涉及 Java 开发者可能不熟悉的 Python 特性时，即使用户没有专门提问，也应：

1. 用通俗语言解释该语法的作用，给一个短小、可运行的例子。
2. 给出最接近的 Java 写法或概念。
3. 说明类比的边界，避免把两种语言的机制说成完全相同。

常见类比：

| Python | 可参考的 Java 概念 |
| --- | --- |
| `@dataclass` | `record` / Lombok `@Data` |
| `@property` | getter |
| `ABC`、`@abstractmethod` | 抽象类 / 接口 |
| `asyncio.Queue` | `BlockingQueue`，但等待通过协程挂起，不等于阻塞线程 |
| `field(default_factory=list)` | 为每个实例单独执行 `new ArrayList<>()` |

也要留意装饰器、`async` / `await`、`with`、推导式、`*args` / `**kwargs` 和鸭子类型。例如，Python 装饰器在对象定义时执行，可以包装或替换对象；Java 注解本身是元数据，需要其他机制读取后才产生效果。

## 常用开发命令

在仓库根目录执行：

```bash
pip install -e ".[dev]"                     # 可编辑安装及 pytest、pytest-asyncio、ruff
pytest                                      # 测试目录为 tests，asyncio_mode=auto
pytest tests/test_tool_validation.py         # 工具参数校验测试
pytest tests/test_tool_validation.py::test_validate_params_missing_required
ruff check nanobot                          # 检查 Python 代码
./test_docker.sh                             # 构建镜像并检查 onboard/status
```

Ruff 目标版本为 Python 3.11，行长配置为 100；启用 `E,F,I,N,W`，忽略 `E501`。沿用现有类型标注和异步代码风格。

WhatsApp 桥接服务在 `bridge/` 下执行：

```bash
npm install
npm run build
npm start
```

根据改动选择相应检查：Python 行为修改运行相关 pytest 和 Ruff；桥接服务修改运行 TypeScript 构建；Docker 修改使用镜像冒烟测试。只修改文档时核对内容和路径即可。最终报告中区分已执行检查和未执行检查。

以下是运行命令，用于用户要求初始化或实际运行服务时：

```bash
nanobot onboard                             # 创建配置和工作区模板
nanobot agent -m "hello"                     # 单次对话；省略 -m 进入交互模式
nanobot gateway                             # 启动 agent、渠道、定时任务和心跳
nanobot status
nanobot channels login                      # 构建并运行 WhatsApp bridge，展示登录二维码
```

## 代码入口与关键行为

- `nanobot/cli/commands.py`：Typer CLI 入口，`gateway` 负责组装各服务。
- `nanobot/bus/`：消息对象和 `MessageBus`。入站、出站各使用一个 `asyncio.Queue`；渠道提交 `InboundMessage`，agent 返回 `OutboundMessage`，`ChannelManager._dispatch_outbound` 按 `msg.channel` 路由。会话键为 `"{channel}:{chat_id}"`。
- `nanobot/agent/loop.py`：构建上下文 → 调用 `provider.chat()` 并提供工具 schema → 执行工具并追加结果 → 循环，直到没有工具调用或达到 `max_iterations`。会话只保存用户文本和最终助手文本，工具调用不会持久化到历史。`process_direct()` 绕过消息总线，用于 CLI、cron 和 heartbeat。
- `nanobot/agent/context.py`：组装系统提示词、历史和当前消息。系统提示词包含固定身份、工作区引导文件、记忆和技能。引导文件为 `AGENTS.md`、`SOUL.md`、`USER.md`、`TOOLS.md`、`IDENTITY.md`；记忆来自 `memory/MEMORY.md` 和当天的 `memory/YYYY-MM-DD.md`。
- `nanobot/agent/subagent.py`、`nanobot/agent/tools/spawn.py`：项目内的 `spawn` 工具启动后台 `asyncio.Task`，子任务使用独立工具注册表，不含 `message` / `spawn`。完成后发布 `channel="system"`、`chat_id="<origin_channel>:<origin_chat_id>"` 的入站消息；主循环解析来源，在原会话继续处理并回复。结果回传依赖 `AgentLoop.run()` 消费总线，因此适用于 gateway 模式，CLI 的 `nanobot agent` 模式不会消费这些结果。
- `nanobot/session/manager.py`：会话历史的加载和保存。
- `nanobot/channels/`：Telegram、WhatsApp 及渠道管理。Telegram 语音转录使用 `nanobot/providers/transcription.py` 中的 Groq Whisper。

### 扩展工具

工具位于 `nanobot/agent/tools/`，继承 `Tool`，实现 `name`、`description`、JSON Schema 格式的 `parameters` 和返回字符串的异步 `execute()`。

新增工具要在 `AgentLoop._register_default_tools()` 注册；若子任务也需要，则在 `SubagentManager` 的工具注册处另行注册。`ToolRegistry.execute()` 先调用 `Tool.validate_params()` 校验参数，并将执行异常转换为错误字符串。`message` 和 `spawn` 工具的渠道、聊天上下文在每轮处理前通过 `set_context()` 设置。

### 技能加载与打包

`nanobot/agent/skills.py` 加载内置 `nanobot/skills/` 和工作区 `skills/`，工作区同名技能优先。

- 技能以带 YAML frontmatter 的 `SKILL.md` 描述。
- frontmatter 是简单的逐行 `key: value` 解析；`metadata` 必须保持为**单行 JSON 字符串**，例如 `metadata: {"nanobot": {"requires": {"bins": [], "env": []}, "always": true}}`。
- 满足依赖且标为 `always` 的技能直接加入提示词；其他技能只提供 XML 摘要，由 agent 按需用 `read_file` 加载。
- 内置技能的非 Python 文件需要匹配 `pyproject.toml` 的 Hatch 打包规则；目前包含 `*.md` 和 `*.sh`，新增其他类型时同步检查打包配置。

### 模型与配置

`nanobot/providers/litellm_provider.py` 的 `LiteLLMProvider` 封装 `litellm.acompletion`。`Config.get_api_key()` 的密钥优先级为 OpenRouter → Anthropic → OpenAI → Gemini → Zhipu → Groq → vLLM。

Provider 根据 `sk-or-` 密钥前缀或 base URL 判断 OpenRouter；其他非空 `api_base` 会被视作 vLLM。模型名称会按逻辑补充 `openrouter/`、`hosted_vllm/`、`zai/`、`gemini/` 等前缀。修改提供商选择时需同时检查密钥、base URL 和模型前缀。LLM 调用异常被转换为响应内容，不会直接抛出。

配置模型位于 `nanobot/config/schema.py`，使用 snake_case；JSON 配置使用 camelCase，由 `loader.py` 递归转换。新增配置字段通常只需扩展 schema。环境变量配置采用 `NANOBOT_` 前缀和 `__` 嵌套分隔符；不要未经验证就假定环境变量一定覆盖 JSON 中的显式值。

### Gateway 与 WhatsApp

`gateway` 连接消息总线、provider、agent、`CronService`、`HeartbeatService` 和 `ChannelManager`。Cron 通过 `process_direct()` 在 `cron:<id>` 会话执行，可将结果投递到渠道。Heartbeat 默认每 30 分钟检查 `HEARTBEAT.md`，没有可执行内容时跳过。

WhatsApp Python 渠道通过 WebSocket 连接 Node.js / Baileys bridge，默认地址为 `ws://localhost:3001`。`bridge/` 被强制打包到 wheel 的 `nanobot/bridge`；`_get_bridge_dir()` 同时支持安装包路径和仓库源码路径，并将 bridge 复制到 `~/.nanobot/bridge` 构建运行。

## 运行时数据位置

仓库中的 `workspace/` 存放模板，实际工作区默认在 `~/.nanobot/workspace/`。

| 路径 | 用途 |
| --- | --- |
| `~/.nanobot/config.json` | 配置 |
| `~/.nanobot/workspace/` | 引导文件、记忆、自定义技能 |
| `~/.nanobot/sessions/*.jsonl` | 会话历史，首行为元数据 |
| `~/.nanobot/cron/jobs.json` | 定时任务 |
| `~/.nanobot/bridge/` | 已复制、构建的 WhatsApp bridge |
| `~/.nanobot/whatsapp-auth/` | WhatsApp 登录状态 |
