# Alii-God

A multi-agent orchestration system in Python: a master service manager (`alfred.py`)
that runs, monitors, and recovers a set of specialized agents — memory, revenue,
inventory, security, and infrastructure — across one or more machines.

Built by **Pierre Cabell**.

## What it does

- **Service orchestration** — `alfred.py` manages the lifecycle of every subsystem:
  startup ordering, health checks, automatic restarts, and graceful shutdown
  (asyncio + aiohttp health endpoints).
- **Persistent memory** — three-layer memory: episodic (SQLite, WAL mode),
  semantic (Qdrant vector store), and working (in-memory). Shared across nodes.
- **Model routing** — `alii_model_router.py` routes prompts to local models via
  LiteLLM, tracking latency and success rate per model.
- **Specialized agents** — revenue, inventory, security, and system-optimizer
  agents, each owning a domain, coordinated through the orchestrator.
- **Deployment** — systemd unit files for production runs, launcher scripts,
  and cluster tooling for multi-node setups.

## Repo layout

```
alfred.py               # Master orchestrator (services, health, recovery)
alii_core.py            # Core runtime
alii_model_router.py    # LLM routing via LiteLLM
memory_system.py        # SQLite-backed episodic memory
agents/                 # Specialized agents (todo, revenue, inventory, security)
tests/                  # Integration and verification tests
docs/                   # Design notes and reports
*.service               # systemd units for deployment
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys — never commit .env
python alfred.py
```

## Status

Active development. Tested on Linux with systemd. Local-model inference
assumes an OpenAI-compatible endpoint (see `litellm_config.yaml`).

## License

All Rights Reserved — Pierre Cabell, 2026. (Keep the existing LICENSE file as-is;
it covers your own original work here.)
