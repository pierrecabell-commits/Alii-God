# Alii AI — Launch Posts
*Privacy-filtered. Business identity only.*

---

## HackerNews — Show HN

**Title:** Show HN: Alii — self-hosted AI agent platform with multi-model routing and self-healing

**Body:**
Hey HN,

I've been building Alii for the past few months — a self-hosted AI agent platform
that runs entirely on local hardware using Ollama.

What makes it different from just running Ollama:

**Alfred** — a master orchestrator that manages all services. It starts them, monitors
health (HTTP + TCP probes), auto-restarts on crash, and exposes a control API on port 7000.
Essentially a mini-systemd for AI services.

**Multi-model router** — classifies every task (code, analysis, quick reply, planning)
and routes to the optimal local model. Learns from performance history. dolphin-phi for
speed, qwen2.5 for reasoning, qwen2.5-coder for code.

**6 specialized agents:**
- LawAgent: Ohio LLC formation, ToS/privacy policy drafting, IP strategy
- BusinessAgent: business plans, financial models, Kickstarter campaigns
- SecurityAgent: port auditing, crontab monitoring, threat reports
- MoneyAgent: revenue tracking, pricing recommendations
- MediaAgent: release notes from git log, changelog generation
- SocialAgent: brand kit, content calendar, launch posts (this one is meta)

**SQLite memory** — everything persists. Alfred remembers context across restarts.

**Watchdog** — cron job that detects service failures and invokes Claude Code for autonomous repair.

Everything runs as systemd user services. On my 12-core / 32GB machine, idle is ~25MB RAM.

Code: https://github.com/your-username/alii

Happy to answer questions about the architecture or any of the agents.

---

## First Twitter/X Thread

**Tweet 1:**
🔒 I built Alii — a self-hosted AI agent platform that runs on your hardware.
No OpenAI. No cloud. No API fees. Everything local.

Here's what it can do 🧵

**Tweet 2:**
The core is Alfred — a master orchestrator.
Alfred starts your AI services, watches their health, and restarts them when they crash.
It's like a tiny systemd just for AI.
Control API at localhost:7000.

**Tweet 3:**
On top of that: multi-model routing.
Alii classifies your task (code / analysis / quick reply) and picks the right local model.
Fastest model for simple questions. Smartest model for complex ones.
Learns from performance history.

**Tweet 4:**
Then 6 specialized agents:
⚖️ Law: draft your LLC, ToS, privacy policy
📊 Business: full business plan + financial model
🔒 Security: audit your ports, crontab, SSH keys
💰 Money: revenue tracking + pricing strategy
📣 Media: changelog from git log
📱 Social: content calendar + launch posts

**Tweet 5:**
All of this on your own hardware.
Your data never leaves your machine.
No subscription. No rate limits. No surveillance.

Built with: Python · Ollama · Chainlit · SQLite · Systemd

GitHub: https://github.com/your-username/alii
⭐ if this is useful to you

---

## Reddit r/selfhosted

**Title:** I built a self-hosted AI agent platform — Alfred orchestrates everything, 6 specialized agents, multi-model routing

**Body:**
Hey r/selfhosted,

I've been running Ollama for a while but wanted more than just a chat interface.
So I built Alii — a full agent platform that sits on top of Ollama.

**What it does:**

Alfred (the master orchestrator):
- Manages all services as subprocesses
- Health-checks every 30s via HTTP or TCP probes
- Auto-restarts crashed services
- HTTP control API (port 7000): /health, /status, /task, /control/{service}

Multi-model router:
- Classifies your task type from the prompt
- Routes to the right Ollama model (fast vs. smart vs. code-focused)
- Tracks performance history, learns over time

6 agents (the fun part):
- LawAgent: actually drafted my Ohio LLC Articles of Organization
- BusinessAgent: wrote a 3-year financial model and Kickstarter campaign
- SecurityAgent: found an unauthorized cron job doing `ssh user@IP "cat /tmp/.sys &"` on my machine
- MoneyAgent: revenue tracking and pricing recommendations
- MediaAgent: generates CHANGELOG.md from git log
- SocialAgent: brand kit, 30-day content calendar, launch posts

Everything runs as systemd user services. The watchdog cron detects port failures.

Hardware: running on a Precision workstation with 12 cores, 32GB RAM.
Tailscale for remote access.

Repo: https://github.com/your-username/alii
Still early — happy to answer questions about any of it.

---

## LinkedIn Announcement

**Post:**

Excited to share what I've been building for the last few months: Alii AI.

Alii is an open-source autonomous AI agent platform that runs entirely on your own hardware.

Why? Because the most sensitive work — legal research, financial modeling, security audits,
business strategy — shouldn't live on someone else's server.

What's live today:
→ Alfred: master orchestrator with self-healing (auto-restarts failed services)
→ Multi-model router: picks the optimal local LLM for each task type
→ 6 agents: law, business, security, finance, media, social
→ SQLite memory: persistent across sessions and restarts
→ Chainlit UI: streaming web interface
→ Watchdog: autonomous recovery system

The LawAgent drafted my LLC formation documents.
The BusinessAgent wrote a 3-year financial projection.
The SecurityAgent found an unauthorized cron job on my machine.

All running locally. All private. Zero API fees.

Open source: https://github.com/your-username/alii

If you're building AI infrastructure or care about data privacy, I'd love your feedback.

#AI #OpenSource #Privacy #SelfHosted #BuildInPublic #Alii
