# Alii-God

> The autonomous Python brain of the Alii system.

Alii-God is the intelligence layer. It houses the full stack of autonomous Python agents that drive decision-making, memory management, revenue generation, cluster orchestration, and self-optimization. While [Alii-Core](https://github.com/pierrecabell-commits/Alii-Core) handles communication channels, Alii-God handles *thought*.

---

## What It Does

Alii-God runs a persistent ensemble of specialized agents across a distributed multi-machine cluster. Each agent owns a domain: one manages accounts and credentials, another scans for revenue opportunities, another monitors security, another bridges iMessage, another optimizes cluster resources. They share memory, coordinate through a unified router, and operate autonomously with minimal human input.

---

## Architecture

```
                        +-----------------------+
                        |      Alfred           |
                        |  (Master Orchestrator)|
                        +----------+------------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     +--------v--------+  +-------v--------+  +-------v--------+
     |  AliiCore        |  |  ModelRouter    |  |  MemoryBridge  |
     |  (Entry Point)   |  |  (LLM Routing)  |  |  (Memory Sync) |
     +---------+--------+  +-------+--------+  +-------+--------+
               |                    |                    |
    +----------+----------+        |           +--------+--------+
    |          |          |        |           |        |        |
+---v---+ +---v---+ +---v---+    |     +-----v--+ +--v----+ +-v------+
|Account| |Revenue| |Security|   |     |Episodic| |Semantic| |Working |
|Agent  | |Agent  | |Agent   |   |     |SQLite  | |Qdrant  | |In-Mem  |
+-------+ +-------+ +--------+  |     +--------+ +--------+ +--------+
                                 |
                    +------------+------------+
                    |            |            |
              +-----v----+ +----v-----+ +----v-----+
              |  Ollama   | |  vLLM    | | LiteLLM  |
              |  (Local)  | | (Serving)| | (Router) |
              +-----------+ +----------+ +----------+
```

---

## Agent Roster

| Agent | File | Role |
|---|---|---|
| **AlfredAgent** | `alfred.py` | Primary orchestrator and task dispatcher |
| **AliiCore** | `alii_core.py` | Unified system entry point and lifecycle manager |
| **AccountAgent** | `agents/account_agent.py` | Secure account and credential management |
| **AccountsAgent** | `agents/accounts_agent.py` | Multi-account registry with Fernet vault |
| **TodoAgent** | `agents/todo_agent.py` | Persistent task queue and priority scheduling |
| **iMessageBridge** | `agents/imessage_bridge.py` | macOS iMessage read/write bridge |
| **SecurityAgent** | `security_agent.py` | System hardening, intrusion detection, access control |
| **RevenueAgent** | `revenue_agent.py` | Autonomous revenue strategy execution |
| **InventoryAgent** | `inventory_agent.py` | Cluster hardware and software inventory |
| **MemoryBridge** | `memory_bridge.py` | Cross-agent memory sync and retrieval |
| **ModelRouter** | `alii_model_router.py` | LLM routing across local and cloud models |
| **ClusterScan** | `cluster_scan.py` | Multi-node health monitoring and diagnostics |
| **Autoscale** | `autoscale.py` | Dynamic resource allocation across the cluster |

---

## Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.13 |
| **LLM Serving** | Ollama (local), vLLM, LiteLLM router |
| **Memory** | SQLite (episodic + working) + Qdrant (semantic vectors) |
| **Storage** | MinIO object store |
| **Cluster** | Ray distributed computing |
| **Workflows** | n8n automation |
| **Networking** | Tailscale mesh VPN |
| **Containers** | Docker + Kubernetes (microk8s) |
| **Monitoring** | Grafana + Prometheus + custom dashboards |

---

## Cluster Nodes

```
Node          Role                     OS
----          ----                     --
Precision     Primary (GPU + storage)  Ubuntu Linux
XPS           Secondary compute        Ubuntu Linux
NUC           Tertiary / gateway       Ubuntu Linux
MacBook       Dev + iMessage bridge    macOS
```

---

## Memory Architecture

Alii-God uses a three-layer memory system:

| Layer | Backend | Purpose |
|---|---|---|
| **Episodic** | SQLite | Timestamped event logs, interaction history |
| **Semantic** | Qdrant | Vector embeddings for concept retrieval |
| **Working** | In-memory | In-flight task state and short-term context |

All layers sync across cluster nodes via `memory_bridge.py`.

---

## Getting Started

```bash
# Clone and enter
git clone https://github.com/pierrecabell-commits/Alii-God.git
cd Alii-God

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and cluster config

# Launch Alii
./alii_launcher.sh
```

---

## Security Model

All sensitive data is protected by design:

- API keys and tokens live in `.env` only (never committed)
- Credentials stored in encrypted Fernet vault (`accounts/vault.json`)
- Private keys, WireGuard configs, and cluster credentials never committed
- Pre-commit hooks scan for accidental secret exposure
- Security agent runs continuous intrusion detection and system hardening

---

## Project Structure

```
Alii-God/
├── alfred.py                  # Master orchestrator
├── alii_core.py               # Unified entry point
├── alii_model_router.py       # LLM model selection and routing
├── alii_distributed_brain.py  # Distributed compute layer
├── memory_bridge.py           # Cross-agent memory sync
├── memory_system.py           # JSON-based memory layer
├── alii_sqlite_memory.py      # SQLite memory backend
├── security_agent.py          # Security hardening and monitoring
├── revenue_agent.py           # Revenue strategy execution
├── inventory_agent.py         # Hardware/software inventory
├── cluster_scan.py            # Cluster health monitoring
├── autoscale.py               # Dynamic resource scaling
├── alii_launcher.sh           # System launch script
├── litellm_config.yaml        # LiteLLM proxy configuration
├── agents/
│   ├── account_agent.py       # Account credential management
│   ├── accounts_agent.py      # Multi-account Fernet vault
│   ├── todo_agent.py          # Task queue and scheduling
│   ├── imessage_bridge.py     # iMessage read/write bridge
│   ├── optimizer.py           # Storage optimization
│   ├── business_agent.py      # Business strategy
│   ├── social_agent.py        # Social media management
│   ├── law_agent.py           # Legal compliance
│   └── ...
├── security/                  # Security hardening scripts
├── docs/                      # Documentation
│   ├── business/              # Business plans and strategies
│   ├── legal/                 # Legal documents
│   ├── social/                # Social media assets
│   └── accounts/              # Account setup guides
├── memory/                    # Memory storage files
├── upgrades/                  # System upgrade configs
└── hardware_info/             # Cluster hardware snapshots
```

---

## Part of the Alii System

| Repo | Role |
|---|---|
| **[Alii-God](https://github.com/pierrecabell-commits/Alii-God)** *(this repo)* | Python autonomous agent brain + cluster |
| **[Alii-Core](https://github.com/pierrecabell-commits/Alii-Core)** | TypeScript gateway + multi-channel messaging |
| **Alii-Public** | Public agent store *(coming soon)* |

---

## License

Copyright (c) 2026 Pierre Cabell. All Rights Reserved.

See [LICENSE](LICENSE) for details.

---

*Built by Pierre Cabell. Alii is a self-evolving autonomous AI system designed to think, earn, and grow without outside permission.*
