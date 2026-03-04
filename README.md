# Alii-God

> The autonomous Python brain of the Alii system.

Alii-God is the intelligence layer. It houses the full stack of autonomous Python agents that drive Alii's decision-making, memory, revenue generation, cluster orchestration, and self-optimization. While Alii-Core handles communication channels, Alii-God handles *thought*.

---

## What It Does

Alii-God runs a persistent ensemble of specialized agents across a distributed multi-machine cluster. Each agent owns a domain: one manages accounts and credentials, another scans for revenue opportunities, another monitors security, another bridges iMessage, another optimizes cluster resources. They share memory, coordinate through a unified router, and operate autonomously with minimal human input.

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

- **Runtime**: Python 3.13
- **LLM Serving**: Ollama (local), vLLM, LiteLLM router
- **Memory**: SQLite + Qdrant vector store
- **Storage**: MinIO object store
- **Cluster**: Ray distributed computing
- **Workflows**: n8n automation
- **Networking**: Tailscale mesh VPN
- **Containers**: Docker + Kubernetes (microk8s)
- **Monitoring**: Grafana + custom dashboards

---

## Cluster Nodes

```
Node          Role                    OS
----          ----                    --
Precision     Primary (GPU + storage)  Ubuntu Linux
XPS           Secondary compute        Ubuntu Linux
NUC           Tertiary / gateway       Ubuntu Linux
MacBook       Dev + iMessage bridge    macOS
```

---

## Memory Architecture

Alii-God uses a three-layer memory system:

- **Episodic** - timestamped event logs, interaction history
- **Semantic** - Qdrant vector embeddings for concept retrieval
- **Working** - in-flight task state and short-term context

All layers sync across cluster nodes via `memory_bridge.py`.

---

## Getting Started

```bash
# Clone and enter
git clone git@github.com:pierrecabell-commits/Alii-God.git
cd Alii-God

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Launch Alii
./alii_launcher.sh
```

---

## Security Model

All sensitive data is gitignored by design:
- API keys and tokens live in `.env` only
- Credentials stored in encrypted Fernet vault (`accounts/vault.json`)
- Private keys, WireGuard configs, and cluster credentials never committed
- Pre-commit hooks scan for accidental secret exposure

---

## Part of the Alii System

| Repo | Role |
|---|---|
| **Alii-God** *(this repo)* | Python autonomous agent brain + cluster |
| **Alii-Core** | TypeScript gateway + multi-channel messaging |
| **Alii-Public** | Public agent store *(coming soon)* |

---

*Built by Pierre Cabell. Alii is a self-evolving autonomous AI system designed to think, earn, and grow without outside permission.*
