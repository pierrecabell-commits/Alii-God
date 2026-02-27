# Alii — Autonomous Local AI System

Alii is a self-healing, multi-model AI assistant and autonomous agent platform designed to run entirely on local hardware. It combines intelligent model routing, persistent memory, a web UI, and a master orchestrator (Alfred) into a cohesive system that operates continuously without cloud dependencies.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Alfred (Port 7000)                    │
│              Master Orchestration System                  │
│   Process lifecycle · Health checks · Task dispatch       │
└──────────┬────────────────────────┬─────────────────────┘
           │                        │
    ┌──────▼──────┐         ┌───────▼───────┐
    │  Alii UI    │         │  Distributed  │
    │ (Chainlit)  │         │  Brain        │
    │  Port 8001  │         │  Port 5000    │
    └──────┬──────┘         └───────┬───────┘
           │                        │
    ┌──────▼────────────────────────▼───────┐
    │           Model Router                 │
    │   Task classification → Ollama LLM    │
    └──────────────────┬────────────────────┘
                       │
    ┌──────────────────▼────────────────────┐
    │          Ollama (local LLMs)           │
    │  dolphin-phi · qwen2.5 · neural-chat  │
    └───────────────────────────────────────┘
                       │
    ┌──────────────────▼────────────────────┐
    │        SQLite Memory Store             │
    │   memories · system_state · upgrades  │
    └───────────────────────────────────────┘
```

## Features

- **Alfred Orchestrator** — Master control plane that starts, monitors, and auto-restarts all subsystems. HTTP API on port 7000 (`/health`, `/status`, `/task`, `/control/{service}`).
- **Intelligent Model Router** — Classifies every task (code, analysis, planning, quick reply) and selects the optimal local LLM based on performance history.
- **Multi-Model Support** — Runs multiple Ollama models simultaneously: dolphin-phi (fastest), qwen2.5, qwen2.5-coder, neural-chat, dolphin-llama3, wizard-vicuna-uncensored.
- **Chainlit Web UI** — Real-time streaming chat interface with performance metrics (tokens/sec).
- **Distributed Brain** — Long-running daemon with health/status endpoints, Prometheus metrics, and 2-hour optimization checkpoints.
- **SQLite Memory** — Persistent, WAL-optimised memory store for conversations, system events, and capability upgrades.
- **Watchdog** — Cron-driven self-healing script that detects port failures and invokes Claude Code for autonomous repair.
- **Systemd Integration** — All components run as user systemd services with automatic restart.

---

## Quickstart

### Prerequisites

- Ubuntu/Debian Linux
- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- At least one Ollama model pulled (e.g. `ollama pull dolphin-phi`)

### Install

```bash
git clone https://github.com/your-username/alii.git
cd alii
pip install --user aiohttp chainlit psutil prometheus-client flask
```

### Pull recommended models

```bash
ollama pull dolphin-phi
ollama pull qwen2.5
ollama pull qwen2.5-coder
ollama pull neural-chat
```

### Start Alfred (manages everything)

```bash
# Via systemd (recommended)
systemctl --user enable alfred.service
systemctl --user start alfred.service

# Or directly
python3 alfred.py
```

### Check status

```bash
curl http://localhost:7000/health
curl http://localhost:7000/status
```

### Open the UI

Navigate to `http://localhost:8001` in your browser.

---

## Directory Structure

```
moltbot/
├── alfred.py                  # Master orchestrator
├── alii_ui.py                 # Chainlit web interface
├── alii_model_router.py       # Intelligent model selection
├── alii_distributed_brain.py  # System daemon + metrics
├── alii_sqlite_memory.py      # SQLite memory layer
├── alii_self_modification.py  # Capability self-upgrade system
├── moltbot.py                 # Core interactive CLI agent
├── persistence_module.py      # Multi-format state management
├── watchdog.sh                # Port-monitoring self-healer
├── agents/                    # Specialised agent modules
├── memory/                    # SQLite DB and state files
├── logs/                      # Runtime logs (gitignored)
└── .config/systemd/user/      # Systemd service units
    ├── alfred.service
    ├── alii-ui.service
    ├── alii-brain.service
    └── alii-watchdog.service
```

---

## API Reference

### Alfred Control API (port 7000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Overall system health |
| GET | `/status` | Per-service status and uptime |
| GET | `/services` | List of managed services |
| POST | `/task` | Submit a task `{"prompt": "..."}` |
| POST | `/control/{service}` | Control a service `{"action": "start\|stop\|restart\|status"}` |

---

## Roadmap

- [ ] Agent framework with specialised agents (media, money, research)
- [ ] Distributed inference across multiple machines via Ray
- [ ] Long-term episodic memory with vector search
- [ ] Voice interface integration
- [ ] Automated capability discovery and self-upgrade pipeline
- [ ] Dashboard UI for Alfred orchestration metrics

---

## License

MIT

## Crypto Donations

**ETH / USDC / MATIC:** `0x1C9Bf65eA4ec76EFC6E12Ab56B3594376324E3d2`

Send USDC on Polygon network for near-zero gas fees (~$0.01).

[View wallet on Etherscan](https://etherscan.io/address/0x1C9Bf65eA4ec76EFC6E12Ab56B3594376324E3d2)

*Also accepting: ETH (mainnet), USDC (Polygon/Ethereum), MATIC*
