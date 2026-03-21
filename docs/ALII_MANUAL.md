# Alii — Sovereign AI System Manual

**Version:** 2.0 | **Owner:** Pierre Cabell | **Cluster:** Akron, OH

---

## Quick Start

```
alii          # from MacBook or Precision terminal → drops into this TUI
alii --chat   # text-only REPL (alii_core.py)
alii --help   # CLI help
```

From MacBook: the `alii` command SSHes to Precision via Tailscale and attaches to a persistent tmux session. Everything runs on Precision — the TUI just appears in your terminal.

---

## Navigation

| Key | Action |
|-----|--------|
| `1` | Chat / AI panel |
| `2` | Agents panel |
| `3` | Cluster panel |
| `4` | Social / MixPost panel |
| `5` | Systems panel (disk, docker, ollama, ray, logs) |
| `6` | Config panel |
| `7` | This help manual |
| `R` | Force cluster refresh |
| `Q` | Quit |

---

## Chat Commands (Panel 1)

| Command | What it does |
|---------|-------------|
| `/shell <cmd>` | Run any shell command on Precision |
| `/status` | Show live cluster status |
| `/memory` | Show recent conversation memory |
| `/agents` | List all available agents |
| `/clear` | Clear chat window |
| `/escalate <msg>` | Route to Claude API (uses tokens — use sparingly!) |

**Regular messages** route automatically via Ollama/LiteLLM — zero Claude tokens.

### Model Routing (automatic)

| Prompt type | Model | Speed |
|-------------|-------|-------|
| Short question (< 60 chars) | dolphin-phi:2.7b (fast) | ~1s |
| Default | qwen2.5:7b (smart) | ~3s |
| Deep analysis | mistral-nemo:12b (smart-plus) | ~5s |
| Code task | qwen2.5-coder:7b | ~3s |
| `/escalate` only | Claude Sonnet | varies |

---

## Cluster Architecture

### Nodes

| Node | IP | Role | Key Services |
|------|----|------|-------------|
| **Precision** | 100.75.36.73 | Head node | Ollama, LiteLLM, Alfred, Docker, Ray head |
| **XPS** | 100.91.78.55 | Worker | Ray worker, overflow inference |
| **NUC** | 100.126.57.22 | Worker | Ray worker, n8n workflows |
| **Jetson** | 100.87.137.61 | Edge GPU | Camera service, TinyLlama, sensor data |
| **MacBook** | 100.111.127.89 | Interface | SSH/tmux client only |

### Networking
All nodes connected via **Tailscale mesh VPN**. No open ports to internet.

### Key Services (Precision)

| Service | Port | Purpose |
|---------|------|---------|
| Ollama | 11434 | Local LLM inference |
| LiteLLM proxy | 4000 | Unified model router |
| Alfred | 7000 | Agent orchestrator |
| OpenClaw | 18789 | TypeScript gateway |
| Open-WebUI | 3000 | Browser UI for Ollama |
| n8n | 5678 | Workflow automation |
| MixPost | 9101 | Social media management |
| Qdrant | 6333 | Vector memory database |
| MinIO | 9000 | Object storage |
| SearXNG | 8888 | Private search engine |

---

## Ollama Models

| Alias | Model | Best For |
|-------|-------|----------|
| `fast` | dolphin-phi:2.7b | Quick answers, 28 tok/s |
| `smart` | qwen2.5:7b | Default reasoning |
| `smart-plus` | mistral-nemo:12b | Deep analysis |
| `code` | qwen2.5-coder:7b | Code tasks |
| `heavy` | qwen2.5:32b | Complex long-form |
| `jetson` | tinyllama | Edge/offline use |

Pull a new model: `/shell ollama pull <model>`

---

## Agents

Agents live in `/home/avalii/moltbot/agents/`. Most run continuously as systemd services.

| Agent | What it does |
|-------|-------------|
| `todo_agent` | Tracks manual action items for Pierre |
| `account_agent` | Manages 10+ platform accounts |
| `social_agent` | Content publishing with privacy filters |
| `ntfy_status` | Cluster health → ntfy every 1hr, todos every 5hr |
| `security_agent` | Network scan + intrusion detection |
| `money_agent` | Revenue tracking + crypto monitoring |
| `hardware_agent` | Thermal management, fan control |
| `camera_agent` | RTSP camera monitoring |
| `imessage_bridge` | macOS iMessage integration |
| `mac_controller` | Remote macOS control |

### Restart an agent service:
`/shell sudo systemctl restart alii-ntfy-status`

### View agent logs:
`/shell tail -50 /home/avalii/moltbot/logs/ntfy_status.log`

---

## Todo System

Alii automatically creates todos for anything requiring Pierre's physical action.

Check todos: click **[2] Agents** → "View Todos" button, or:
`/shell cat /home/avalii/moltbot/data/owner_todos.json | python3 -m json.tool | head -60`

Todos also arrive via ntfy every 5 hours.

Categories: `security` · `account` · `config` · `action`
Priorities: `critical` · `high` · `medium` · `low`

---

## Social Media (MixPost)

**Web UI:** http://100.75.36.73:9101 (access from any Tailscale device)

MixPost handles scheduling and publishing to:
Twitter/X · LinkedIn · Facebook · Instagram · Reddit · TikTok · Pinterest

The `social_agent` integrates with MixPost for autonomous content publishing.
Privacy filter is hardcoded — never publishes personal data.

---

## Vault & Credentials

All credentials in the encrypted vault — never hardcoded anywhere.

- Agents access vault **read-only**
- Vault write requires Pierre's explicit command
- If vault needs initialization: ntfy alert sent to Pierre, system waits

Never commit `.env` to git (it's gitignored).

---

## Memory System

Three layers:
1. **Episodic** — SQLite at `memory/alii_core.db` (conversation history)
2. **Semantic** — Qdrant vector store at port 6333 (concept retrieval)
3. **Working** — JSON in `memory/` (in-flight task state)

View recent memory: `/memory` in Chat panel

---

## ntfy Notifications

Subscribe: https://ntfy.sh/alii-precision

| Notification | When |
|-------------|------|
| Cluster health | Every 1 hour |
| Todo digest | Every 5 hours |
| Critical temp alert | Immediately (> 75°C) |
| Service crash | Immediately |

---

## GitHub Repositories

| Repo | Path | Remote |
|------|------|--------|
| Alii-God (moltbot) | `/home/avalii/moltbot/` | Alii-God |
| Alii-Core | `/home/avalii/alii/` | Alii-Core |
| Alii-Public | `/home/avalii/alii_public/` | Alii-Authentic-Intelligence-Public |

Push all: `/shell cd /home/avalii/moltbot && git push origin main`

---

## Overhaul Tasks (Hardware)

Run from Chat panel: `/shell python3 /home/avalii/moltbot/scripts/alii_overhaul_tasks.py`

Discovers:
- Jetson camera (`/dev/video*`)
- New storage drives (`/dev/sdd`)
- Git repo status

Results appear as ntfy notifications and todos.

---

## Troubleshooting

**TUI won't start:** `cd /home/avalii/moltbot && source venv/bin/activate && python3 alii_tui.py`

**LiteLLM down:** `sudo systemctl restart alii-router`

**Ollama down:** `sudo systemctl restart ollama`

**All services down:** `sudo systemctl restart alfred` (Alfred restarts managed services)

**Can't reach Precision from MacBook:** Check Tailscale: `tailscale status`

**Chat not responding:** LiteLLM or Ollama may be overloaded. Try `/shell` commands directly.

---

## File Locations

| Item | Path |
|------|------|
| Main TUI | `/home/avalii/moltbot/alii_tui.py` |
| Config | `/home/avalii/moltbot/.env` |
| Agent logs | `/home/avalii/moltbot/logs/` |
| Data/state | `/home/avalii/moltbot/data/` |
| Memory DB | `/home/avalii/moltbot/memory/alii_core.db` |
| Vault | encrypted credential store, read-only for agents |
| MacBook cmd | `/usr/local/bin/alii` (Mac) |
| OpenClaw WS | `/home/avalii/.openclaw/workspace/` |
