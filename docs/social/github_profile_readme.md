# Alii AI

> Run AI on your terms. No cloud. No subscriptions. No surveillance.

---

## What is Alii?

**Alii** is an open-source autonomous AI agent platform that runs entirely on your hardware.
No cloud. No API fees. No surveillance.

Built on top of [Ollama](https://ollama.ai), Alii adds:

- **Alfred** — master orchestrator that manages all services, heals failures, routes tasks
- **Multi-model router** — automatically selects the fastest/best local LLM for your task
- **6 specialized agents** — law, business, media, money, security, social
- **Persistent SQLite memory** — Alii remembers everything across sessions
- **Chainlit web UI** — real-time streaming chat interface
- **Watchdog** — automatic recovery when anything breaks

---

## Quick Start

```bash
git clone https://github.com/your-username/alii
cd alii
pip install aiohttp chainlit psutil prometheus-client flask
ollama pull dolphin-phi
python3 alfred.py
```

Open `http://localhost:8001` — your private AI is running.

---

## Architecture

```
Alfred (port 7000) — Master Orchestrator
├── Alii UI (port 8001) — Chainlit Web Interface
├── Distributed Brain (port 5000) — Health + Metrics
├── Model Router — dolphin-phi · qwen2.5 · neural-chat
└── SQLite Memory — persistent across sessions
```

---

## Agents

| Agent | Capability |
|---|---|
| LawAgent | Ohio LLC formation, ToS, privacy policy, compliance |
| BusinessAgent | Business plan, financial model, Kickstarter campaign |
| MediaAgent | Release notes, changelog, platform posting |
| MoneyAgent | Revenue tracking, pricing, daily financial report |
| SecurityAgent | Port audit, SSH monitoring, threat reports |
| SocialAgent | Brand kit, content calendar, launch posts |

---

## Status

![Alfred](https://img.shields.io/badge/Alfred-running-brightgreen)
![License](https://img.shields.io/badge/license-AGPL--3.0-purple)
![Python](https://img.shields.io/badge/python-3.11+-blue)

---

## Support

- ⭐ Star this repo if Alii is useful to you
- 💬 Open an Issue for bugs or feature requests
- 💜 [GitHub Sponsors](https://github.com/your-username/alii/sponsors) — keep Alii free and maintained
