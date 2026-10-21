# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

nanobot (`nanobot-ai` on PyPI) is a deliberately small (~4k LOC) personal AI assistant: an LLM tool-calling loop connected to chat channels (Telegram, WhatsApp), cron jobs, and a periodic heartbeat. Keeping the codebase small and readable is an explicit project goal, so prefer minimal changes over new abstractions.

## Explaining Python to the user

The user is moving from Java to Python and is still learning Python. Reply in Chinese. Whenever a question or the code under discussion involves a Python feature a Java developer may not know (decorators, `@dataclass`, `@property`, `async`/`await`, context managers `with`, comprehensions, `*args`/`**kwargs`, duck typing, etc.), even if the user didn't ask about it directly:

- Explain what it does in plain terms with a short runnable example.
- Give the closest Java counterpart, e.g. `@dataclass` ≈ Java `record` / Lombok `@Data`; `@property` ≈ a getter; `ABC` + `@abstractmethod` ≈ abstract class/interface; `asyncio.Queue` ≈ `BlockingQueue`; `field(default_factory=list)` ≈ initializing a field with `new ArrayList<>()`.
- Point out where the analogy breaks. For example, a Python decorator is a function that wraps or replaces the decorated object when it is defined, while a Java annotation is metadata that does nothing unless something reads it via reflection.

## Commands

```bash
pip install -e ".[dev]"                 # editable install + pytest, pytest-asyncio, ruff
pytest                                  # run tests (asyncio_mode=auto, testpaths=tests)
pytest tests/test_tool_validation.py::test_name   # single test
ruff check nanobot                      # lint (rules E,F,I,N,W; line-length 100, E501 ignored)

nanobot onboard                         # create ~/.nanobot/config.json and workspace templates
nanobot agent -m "hello"                # one-shot chat; omit -m for interactive mode
nanobot gateway                         # run agent + channels + cron + heartbeat
nanobot status

./test_docker.sh                        # build Docker image and smoke-test onboard/status
```

WhatsApp bridge (TypeScript, Node ≥20, in `bridge/`): `npm install && npm run build && npm start`. `nanobot channels login` copies the bridge to `~/.nanobot/bridge`, builds it there, and runs it to show the QR code.

## Architecture

**Message bus decoupling.** `bus/queue.py` `MessageBus` has an inbound and an outbound `asyncio.Queue`. Channels push `InboundMessage`s; `AgentLoop.run()` consumes them and publishes `OutboundMessage`s; `ChannelManager._dispatch_outbound` routes each outbound message to the channel whose `name` matches `msg.channel`. Sessions are keyed `"{channel}:{chat_id}"`.

**Agent loop** (`agent/loop.py`): for each message, build context → call `provider.chat()` with all tool schemas → execute tool calls and append results → repeat until the LLM returns no tool calls or `max_iterations` is hit. Only the final user/assistant text is saved to the session (tool calls are not persisted to history). `process_direct()` bypasses the bus and is what the CLI, cron, and heartbeat use.

**Subagents** (`agent/subagent.py`, `tools/spawn.py`): the `spawn` tool starts a background `asyncio.Task` with its own tool registry (no `message`/`spawn` tools). When finished it publishes an `InboundMessage` with `channel="system"` and `chat_id="<origin_channel>:<origin_chat_id>"`; `AgentLoop._process_system_message` parses that to run another turn in the original session and route the reply back. This only works when `AgentLoop.run()` is consuming the bus (gateway mode), not in `nanobot agent` CLI mode.

**Context building** (`agent/context.py`): system prompt = hardcoded identity + workspace bootstrap files (`AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`) + memory (`memory/MEMORY.md` and today's `memory/YYYY-MM-DD.md`) + skills. The `workspace/` directory in the repo holds templates for these files; the real workspace defaults to `~/.nanobot/workspace`.

**Skills** (`agent/skills.py`): each skill is a `SKILL.md` with YAML frontmatter; `metadata` is a single-line JSON string `{"nanobot": {"requires": {"bins": [...], "env": [...]}, "always": true}}`. Frontmatter parsing is naive line-based `key: value`, so keep metadata on one line. Skills marked `always` are inlined into the prompt; others appear only as an XML summary and the agent loads them with `read_file` (progressive loading). Workspace skills (`<workspace>/skills/`) override built-ins (`nanobot/skills/`). Non-Python skill files must match the hatch `include` globs in `pyproject.toml` (`*.md`, `*.sh`) to ship in the wheel.

**Tools** (`agent/tools/`): subclass `Tool` (name, description, JSON-schema `parameters`, async `execute` returning `str`) and register in `AgentLoop._register_default_tools` (and `SubagentManager` if subagents should have it). `ToolRegistry.execute` validates params against the schema via `Tool.validate_params` and converts exceptions into error strings rather than raising. `message` and `spawn` tools hold per-request channel/chat context set via `set_context()` before each turn.

**Providers** (`providers/litellm_provider.py`): one `LiteLLMProvider` wraps `litellm.acompletion`. Provider selection is implicit: `Config.get_api_key()` picks the first configured key in priority order (OpenRouter > Anthropic > OpenAI > Gemini > Zhipu > Groq > vLLM), and the provider detects OpenRouter (`sk-or-` key or base URL) / vLLM (any other `api_base`) and rewrites the model name with LiteLLM prefixes (`openrouter/`, `hosted_vllm/`, `zai/`, `gemini/`). LLM errors are returned as response content, not raised. `providers/transcription.py` uses Groq Whisper for Telegram voice messages.

**Config** (`config/`): Pydantic models in `schema.py` use snake_case; `~/.nanobot/config.json` uses camelCase, converted by `loader.py`. Adding a config field means adding it to the schema only. Env overrides use `NANOBOT_` prefix with `__` nesting.

**Gateway** (`cli/commands.py` `gateway`): wires bus, provider, `AgentLoop`, `CronService` (jobs in `~/.nanobot/cron/jobs.json`, run via `process_direct` with session `cron:<id>`, optionally delivered to a channel), `HeartbeatService` (every 30 min, prompts the agent to act on `HEARTBEAT.md`; skipped if the file has no actionable content), and `ChannelManager`.

**WhatsApp**: `channels/whatsapp.py` is a WebSocket client to the Node bridge (`bridge/`, Baileys) at `ws://localhost:3001` by default. The bridge is force-included in the wheel as `nanobot/bridge`, so `_get_bridge_dir` checks both the installed package path and the repo-root path.

## Runtime data locations

- `~/.nanobot/config.json` — config
- `~/.nanobot/workspace/` — agent workspace (bootstrap files, memory, custom skills)
- `~/.nanobot/sessions/*.jsonl` — conversation history (first line is metadata)
- `~/.nanobot/cron/jobs.json` — scheduled jobs
- `~/.nanobot/bridge/`, `~/.nanobot/whatsapp-auth/` — built bridge and WhatsApp auth state
