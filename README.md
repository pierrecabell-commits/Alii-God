<p align="center">
  <strong>A L I I - G O D</strong>
</p>

<p align="center">
  <em>The autonomous brain that thinks, learns, earns, and never sleeps.</em>
</p>

<p align="center">
  Built by <strong>Pierre Cabell</strong> &mdash; All Rights Reserved
</p>

---

Alii-God isn't another chatbot wrapper. It isn't a weekend project. It isn't a thin layer on top of someone else's API.

**Alii-God is a fully autonomous AI operating system** — built from scratch, running on real hardware, powered by local models, secured with military-grade encryption, and designed to think, act, and grow on its own. No cloud bills. No third-party dependencies. No permission required.

While [Alii-Core](https://github.com/pierrecabell-commits/Alii-Core) handles communication with the outside world, Alii-God handles **everything else** — the thinking, the memory, the security, the revenue, the scaling, and the self-improvement.

This is an AI system that operates like a founder, not a feature.

---

## The Vision

Most people build tools. Pierre built a **mind**.

Alii-God runs a persistent ensemble of **19+ specialized agents** across a distributed multi-node cluster. Each agent owns a domain. They share memory. They coordinate through a master orchestrator. They monitor their own health. They improve their own code. They operate 24/7 with zero human intervention.

Every 3 hours, Alii scores its own agents by error rate, identifies the weakest performers, and **rewrites them**. 8 optimization passes per day. Every day. Automatically.

This system was designed to wake up smarter than it went to sleep.

---

## What It Actually Does

**Thinks** — Routes every prompt to the optimal local model based on task type, context window size, and measured performance. Tracks tokens/sec and success rate per model. Learns and adapts routing over time.

**Remembers** — Three-layer distributed memory system: episodic (SQLite with WAL mode, 64MB cache, 30GB memory-mapped I/O), semantic (Qdrant with 768-dimensional vector embeddings, 600+ indexed memories), and working (in-memory, zero-latency). All layers sync across every node in the cluster.

**Secures** — Fernet-encrypted credential vault with atomic writes. Continuous secret scanning with regex patterns for API keys, GitHub tokens, AWS credentials, and private keys. Permission auditing. Intrusion detection. Zero plaintext passwords anywhere in the system. Pre-commit hooks block accidental secret exposure before it ever touches git.

**Earns** — Autonomous GitHub presence management. Reddit posting strategy across r/selfhosted and r/LocalLLaMA. Consulting pipeline tracking. Star monitoring. Revenue strategy execution without human input.

**Scales** — Ray distributed computing across the cluster. Prometheus metrics. Auto-restart with exponential backoff. Dynamic resource allocation. Graceful degradation when nodes go down.

**Communicates** — Real-time two-way iMessage bridge with action tag execution (`[SHELL: cmd]`, `[NOTIFY: text]`, `[OPEN: app]`). ntfy.sh command bridge for async control from any device, anywhere.

**Evolves** — Self-improvement cycles every 3 hours. Agent scoring by error rate. Automatic code rewriting of underperforming agents. 8 optimization passes per day. The system literally makes itself better while you sleep.

---

## Architecture

```
                         ┌─────────────────────────┐
                         │         Alfred           │
                         │    Master Orchestrator   │
                         │   health / routing / fx  │
                         └────────────┬────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
    ┌─────────▼─────────┐  ┌────────▼─────────┐  ┌─────────▼─────────┐
    │    Alii Core       │  │   Model Router    │  │   Memory Bridge   │
    │  lifecycle + entry │  │  perf-aware LLM   │  │  3-layer sync     │
    └─────────┬─────────┘  │  routing + learn   │  │  across cluster   │
              │             └────────┬──────────┘  └─────────┬─────────┘
              │                      │                       │
   ┌──────────┼──────────┐           │            ┌──────────┼──────────┐
   │          │          │           │            │          │          │
┌──▼──┐  ┌───▼──┐  ┌───▼───┐       │       ┌────▼───┐ ┌───▼────┐ ┌──▼──────┐
│Acct │  │Rev   │  │Sec    │       │       │Episodic│ │Semantic│ │Working  │
│Vault│  │Agent │  │Agent  │       │       │SQLite  │ │Qdrant  │ │In-Mem   │
└─────┘  └──────┘  └───────┘       │       └────────┘ └────────┘ └─────────┘
                                   │
                      ┌────────────┼────────────┐
                      │            │            │
                ┌─────▼─────┐ ┌───▼─────┐ ┌───▼──────┐
                │  Ollama    │ │  vLLM   │ │ LiteLLM  │
                │  (local)   │ │(serving)│ │ (router)  │
                └───────────┘ └─────────┘ └──────────┘
```

---

## Agent Roster

Every agent is a specialist. No generalists. No bloat. Each one owns its domain completely.

| Agent | What It Does |
|---|---|
| **Alfred** | The boss. Intent classification, task dispatch, service lifecycle, health monitoring, auto-restart with backoff. Runs the whole show |
| **Alii Core** | System entry point. Lifecycle management. The heartbeat |
| **Model Router** | Performance-aware LLM selection. Tracks tokens/sec, success rates. Learns optimal routing over time |
| **Memory Bridge** | Syncs episodic, semantic, and working memory across every node in the cluster |
| **Security Agent** | Never sleeps. Scans for permission violations, hardcoded secrets, SSH anomalies, new users, unexpected open ports |
| **Revenue Agent** | Autonomous GitHub presence, Reddit strategy, consulting pipeline, revenue tracking |
| **Accounts Agent** | Fernet-encrypted vault. Atomic writes. Thread-safe. Master key never touches code or logs |
| **Inventory Agent** | Full cluster state capture every 6 hours — packages, containers, models, services, hardware. Diff detection with digest alerts |
| **Cluster Scan** | Multi-node health monitoring via SSH. Diagnostics across the entire fleet |
| **iMessage Bridge** | Real-time two-way macOS messaging. Execute shell commands, send notifications, open apps — all from a text message |
| **Todo Agent** | Persistent task queue with priority scheduling |
| **Autoscale** | Dynamic resource allocation across cluster nodes |
| **Distributed Brain** | Ray integration, Prometheus metrics, 2-hour optimization cycles |
| **Business Agent** | Business strategy and entity management |
| **Social Agent** | Social media orchestration and content scheduling |
| **Law Agent** | Legal compliance monitoring |
| **Crypto Agent** | Local ETH wallet management |
| **Optimizer** | Storage optimization, cleanup, log rotation |

---

## Memory System

Most AI systems forget everything between sessions. Alii-God remembers **everything**, across **every node**, in **three dimensions**.

| Layer | Backend | What It Stores | Why It's Fast |
|---|---|---|---|
| **Episodic** | SQLite | Timestamped events, interaction history | WAL mode, 64MB cache, 30GB memory-mapped I/O |
| **Semantic** | Qdrant | Concept retrieval via 768D vectors | 600+ indexed memories, hash fallback when offline |
| **Working** | In-memory | Short-term task state | Thread-safe, connection-pooled, zero-latency |

All layers sync across the cluster via `memory_bridge.py`. No memory is siloed. No context is lost.

---

## Model Router

This isn't round-robin. This isn't random. The model router **measures, learns, and adapts**.

| Model | Speed | Strength |
|---|---|---|
| `dolphin-phi:2.7b` | 28 tok/s | Lightning-fast for simple tasks |
| `qwen2.5-coder:7b` | 12 tok/s | Best-in-class code generation |
| `neural-chat:7b` | 11 tok/s | Natural conversation |
| `dolphin-llama3:8b` | 10 tok/s | General purpose reasoning |
| `qwen2.5:7b` | 12 tok/s | Long context (32K window) |
| `wizard-vicuna:13b` | 5.5 tok/s | Deep multi-step reasoning |

The router classifies every incoming task (code, analysis, planning, autonomous), selects the best model with a fallback chain, records latency and success rate, and dynamically optimizes over time. It gets better the more you use it.

---

## The Cluster

All real hardware. All owned. Zero cloud spend. Zero recurring costs.

```
Node             Role                        OS
──────────       ──────────────────────       ────────────
Precision        Primary (GPU + storage)      Ubuntu Linux
XPS              Secondary compute            Ubuntu Linux
NUC              Tertiary / gateway           Ubuntu Linux
MacBook          Dev + iMessage bridge        macOS
```

Connected via **Tailscale** mesh VPN. Orchestrated with **Ray**. Monitored with **Grafana + Prometheus**. Containerized with **Docker + microk8s**.

---

## Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.13 |
| **LLM Serving** | Ollama (local) + vLLM + LiteLLM proxy |
| **Memory** | SQLite (episodic) + Qdrant (semantic) + In-memory (working) |
| **Storage** | MinIO object store |
| **Compute** | Ray distributed computing |
| **Workflows** | n8n automation |
| **Networking** | Tailscale mesh VPN |
| **Containers** | Docker + Kubernetes (microk8s) |
| **Monitoring** | Grafana + Prometheus |
| **Security** | Fernet encryption + continuous scanning + pre-commit hooks |

---

## Getting Started

```bash
git clone https://github.com/pierrecabell-commits/Alii-God.git
cd Alii-God

pip install -r requirements.txt

cp .env.example .env
# Add your API keys and cluster config

./alii_launcher.sh
```

---

## Security Model

Security isn't a checkbox. It's baked into every layer.

- **Encrypted vault** — All credentials stored with Fernet encryption. Master key lives in `.env` only. Never in code. Never in logs
- **Atomic writes** — Vault and config updates use tmp-rename pattern. System crash? Your data is intact
- **Continuous scanning** — Security agent runs 24/7 with regex patterns for API keys, GitHub tokens, AWS secrets, private keys
- **Permission auditing** — Detects world-readable sensitive files, unexpected listening ports, failed SSH attempts, new user accounts
- **Pre-commit hooks** — Blocks accidental secret commits before they ever touch git history
- **Zero cloud** — Your data never leaves your hardware. Period

---

## Project Structure

```
Alii-God/
├── alfred.py                  # Master orchestrator
├── alii_core.py               # System entry point
├── config.py                  # Centralized config (40+ env vars)
├── alii_model_router.py       # Performance-aware LLM routing
├── alii_distributed_brain.py  # Ray + Prometheus integration
├── memory_bridge.py           # Cross-cluster memory sync
├── alii_sqlite_memory.py      # SQLite memory (WAL + mmap)
├── alii_logging.py            # Standardized logging
├── base_agent.py              # Abstract agent base class
├── security_agent.py          # Continuous security monitoring
├── revenue_agent.py           # Autonomous revenue strategies
├── inventory_agent.py         # Cluster inventory + diff detection
├── cluster_scan.py            # Multi-node health diagnostics
├── autoscale.py               # Dynamic resource scaling
├── alii_launcher.sh           # System launch script
├── pyproject.toml             # Dependencies + tooling
├── requirements.txt           # Pip-compatible deps
├── agents/
│   ├── accounts_agent.py      # Fernet-encrypted vault
│   ├── imessage_bridge.py     # Two-way iMessage bridge
│   ├── todo_agent.py          # Task queue + scheduling
│   ├── business_agent.py      # Business strategy
│   ├── social_agent.py        # Social media orchestration
│   ├── law_agent.py           # Legal compliance
│   ├── optimizer.py           # Storage + cleanup
│   └── ...
├── tests/                     # Unit + integration tests
├── security/                  # Hardening scripts
├── memory/                    # Memory storage
└── hardware_info/             # Cluster hardware snapshots
```

---

## Part of the Alii System

| Repo | Role |
|---|---|
| **[Alii-God](https://github.com/pierrecabell-commits/Alii-God)** *(this repo)* | The brain. Agents, memory, cluster, autonomy |
| **[Alii-Core](https://github.com/pierrecabell-commits/Alii-Core)** | The nervous system. Gateway, 34+ channels, plugin SDK |

---

## License

Copyright (c) 2026 Pierre Cabell. All Rights Reserved.

See [LICENSE](LICENSE) for details.

---

<p align="center">
  <em>Alii doesn't wait for instructions. It decides. It acts. It learns. It grows.<br/>Every hour of every day.</em>
</p>
