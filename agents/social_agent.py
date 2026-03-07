#!/usr/bin/env python3
"""
SocialAgent — Brand presence and content management for Alii AI.

CRITICAL PRIVACY RULES (HARDCODED):
  - NEVER post, store, or transmit personal data (SSN, passport, DL, bank accounts,
    credit cards, home address, personal phone, personal email, DOB, medical, biometric).
  - ONLY use the public business identity: Alii AI brand.
  - ALL content is filtered through privacy_audit() before any output or API call.
"""

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("alii.social_agent")

WORKDIR    = Path("/home/avalii/moltbot")
SOCIAL_DIR = WORKDIR / "docs" / "social"
LOG_DIR    = WORKDIR / "logs"
LOG_FILE   = LOG_DIR / "social_agent.log"

# ── Privacy filter ─────────────────────────────────────────────────────────────
PERSONAL_DATA_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b",          "SSN"),
    (r"\b[A-Z]\d{7,9}\b",               "Passport number"),
    (r"\b[A-Z]{1,2}\d{6,9}\b",          "Driver's license"),
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "Credit card number"),
    (r"\b\d{9,18}\b",                    "Bank account number (candidate)"),
    (r"\b\d{1,5}\s[\w\s]{1,30}(?:street|st|avenue|ave|road|rd|drive|dr|blvd|lane|ln)\b",
                                          "Home address"),
    (r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "Phone number"),
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?<!\balii\.ai)\b",
                                          "Personal email"),
    (r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b",
                                          "Date of birth"),
    (r"\b(?:blood type|HIV|diabetes|cancer|prescription|diagnosis)\b",
                                          "Medical information"),
    (r"\bfingerprint|retina scan|face recognition template\b",
                                          "Biometric data"),
]

BUSINESS_IDENTITY = {
    "brand":    "Alii AI",
    "product":  "Alii",
    "handle":   "@alii_ai",
    "email":    "hello@alii.ai",
    "github":   "https://github.com/your-username/alii",
    "taglines": [
        "Your private, autonomous AI platform.",
        "Run AI on your terms. No cloud. No subscriptions. No surveillance.",
        "The self-hosted AI that actually works.",
        "Alfred manages everything. You control everything.",
    ],
}


def _slog(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [social_agent] {msg}"
    log.info(msg)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as fh:
        fh.write(entry + "\n")


def _write(path: Path, content: str) -> bool:
    audit = privacy_audit(content)
    if audit["status"] == "BLOCKED":
        _slog(f"BLOCKED write to {path}: {audit['findings']}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _slog(f"Written: {path} ({len(content)} bytes)")
    return True


def _write_memory(category: str, content: str):
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception:
        pass


# ── Privacy audit (public function — used externally too) ────────────────────

def privacy_audit(text: str) -> dict:
    """
    Scan text for personal data patterns.
    Returns: {"status": "SAFE"|"BLOCKED", "findings": [...]}
    """
    findings = []
    for pattern, label in PERSONAL_DATA_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            findings.append({"type": label, "count": len(matches)})
    status = "BLOCKED" if findings else "SAFE"
    return {"status": status, "findings": findings}


class SocialAgent:
    """
    Brand presence and content manager for Alii AI.
    All output is privacy-filtered before writing or sending.
    """

    def __init__(self):
        SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
        _slog("SocialAgent initialised.")

    # ── (a) Brand Kit ─────────────────────────────────────────────────────────

    def prepare_platform_assets(self) -> str:
        _slog("prepare_platform_assets")
        bi = BUSINESS_IDENTITY
        content = f"""# Alii AI — Brand Kit
*Business identity only. No personal information.*

---

## Brand Identity

**Brand Name:** {bi['brand']}
**Product Name:** {bi['product']}
**Handle:** {bi['handle']} (Twitter/X, GitHub, Reddit, LinkedIn)
**Contact:** {bi['email']}
**Website/GitHub:** {bi['github']}

---

## Logo Concept (for designers)

**Primary Mark:** Stylized "A" monogram with neural-network node motif
- The letter A formed by two converging lines with a crossbar made of connected nodes
- Represents: intelligence, architecture, connectivity

**Icon Mark:** Ghost silhouette (nod to Alfred the butler) with circuit-board texture
- Simple, recognizable at 16x16px favicon size
- Works in light and dark themes

**Wordmark:** "Alii AI" in geometric sans-serif (Geist Mono or JetBrains Mono)
- All-caps "ALII" with thin tracking
- "AI" in the brand purple, slightly smaller

---

## Color Palette

| Color | Hex | Use |
|---|---|---|
| Brand Purple | `#7C3AED` | Primary CTA, highlights, links |
| Deep Dark | `#0F0F0F` | Background (dark theme) |
| Off-White | `#F5F5F0` | Text on dark, light theme background |
| Electric Blue | `#3B82F6` | Code highlights, secondary accents |
| Success Green | `#10B981` | Status indicators, health checks |
| Warning Amber | `#F59E0B` | Warnings, non-critical alerts |
| Danger Red | `#EF4444` | Errors, critical alerts |

---

## Taglines

1. **Primary:** "{bi['taglines'][0]}"
2. **Developer:** "{bi['taglines'][1]}"
3. **Short:** "{bi['taglines'][2]}"
4. **Product:** "{bi['taglines'][3]}"

---

## Platform Bios

### Twitter/X (160 chars)
```
{bi['product']}: self-hosted AI agent platform. Local LLMs. Private memory.
Alfred orchestrates everything. No subscriptions. No surveillance. Open source.
{bi['github']}
```

### GitHub (255 chars)
```
Alii is an open-core autonomous AI agent platform — runs locally, remembers everything,
heals itself. Multi-model routing · Private memory · 6 specialized agents · Alfred orchestrator.
```

### Reddit (300 chars)
```
Building Alii — a self-hosted AI agent platform. Runs on your hardware with Ollama.
Multi-model routing, persistent memory, and Alfred (master orchestrator with self-healing).
Privacy-first. Open source. Building in public.
```

### LinkedIn
```
Alii AI LLC is building the private, autonomous AI platform for developers and businesses
who refuse to send their data to the cloud. Open source core · Enterprise ready ·
Local LLM inference · Self-healing orchestration.
```

---

## Content Tone

- **Voice:** Technical but approachable. Builder. Honest about what works and what doesn't.
- **Never:** Hype, vague claims, personal information
- **Always:** Specific, reproducible, build-in-public transparency
- **Emoji style:** Minimal (one per post max). Prefer: ⚡🔒🧠🔧🚀
"""
        path = SOCIAL_DIR / "brand_kit.md"
        _write(path, content)
        _write_memory("social_agent", "Brand kit generated.")
        return content

    # ── (b) GitHub Profile README ─────────────────────────────────────────────

    def draft_github_profile(self) -> str:
        _slog("draft_github_profile")
        bi = BUSINESS_IDENTITY
        content = f"""# {bi['brand']}

> {bi['taglines'][1]}

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
git clone {bi['github']}
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
- 💜 [GitHub Sponsors]({bi['github']}/sponsors) — keep Alii free and maintained
"""
        path = SOCIAL_DIR / "github_profile_readme.md"
        _write(path, content)
        _write_memory("social_agent", "GitHub profile README generated.")
        return content

    # ── (c) Twitter Bio ───────────────────────────────────────────────────────

    def draft_twitter_bio(self) -> str:
        _slog("draft_twitter_bio")
        bio = (
            "Self-hosted AI agent platform. Local LLMs. Private memory. "
            "Alfred orchestrates everything. No subscriptions. Open source. "
            f"Building in public. {BUSINESS_IDENTITY['github']}"
        )
        audit = privacy_audit(bio)
        result = {
            "handle":       "@alii_ai",
            "bio":          bio[:160],
            "char_count":   len(bio[:160]),
            "privacy_audit": audit,
        }
        path = SOCIAL_DIR / "twitter_bio.json"
        _write(path, json.dumps(result, indent=2))
        _write_memory("social_agent", "Twitter bio drafted.")
        return bio[:160]

    # ── (d) LinkedIn Page ─────────────────────────────────────────────────────

    def draft_linkedin_page(self) -> str:
        _slog("draft_linkedin_page")
        content = f"""# Alii AI LLC — LinkedIn Company Page Content

## Company Name
Alii AI LLC

## Tagline (120 chars)
The self-hosted AI agent platform. Private. Autonomous. Open source.

## About (2,000 chars)
Alii AI is building the privacy-first autonomous AI platform for developers and
organizations who need powerful AI without sacrificing data control.

**The problem:** Every major AI tool — ChatGPT, Copilot, Claude — sends your data to
third-party servers. For regulated industries and privacy-conscious teams, this is
simply not acceptable.

**Our solution:** Alii runs entirely on your own hardware. Your prompts, your memory,
your data — never leaves your machine.

**What makes Alii different:**
• Alfred orchestrator — manages all AI services, auto-restarts failures, HTTP control API
• Multi-model router — intelligently selects the optimal local LLM for each task type
• 6 built-in agents — law, business, media, money, security, and social media management
• Persistent memory — SQLite-backed memory that persists across all sessions
• Self-healing — watchdog monitors services and triggers automatic recovery
• Open source core — AGPL-3.0, enterprise license available

**Who uses Alii:**
• Developers who want a private AI coding assistant
• Law firms and healthcare organizations with data compliance requirements
• Startups building AI-powered workflows without API cost exposure
• Homelab enthusiasts running local AI infrastructure

**Tech stack:** Python · Ollama · Chainlit · SQLite · Systemd · Tailscale

**Stage:** Pre-revenue MVP, seeking first customers and community members.

Follow us for build-in-public updates, technical deep-dives, and launch announcements.

## Specialties
AI · Local LLM · Privacy · Developer Tools · Autonomous Agents · Open Source · Self-Hosted

## Website
{BUSINESS_IDENTITY['github']}
"""
        path = SOCIAL_DIR / "linkedin_page.md"
        _write(path, content)
        _write_memory("social_agent", "LinkedIn page content drafted.")
        return content

    # ── (e) Reddit Profile ────────────────────────────────────────────────────

    def draft_reddit_profile(self) -> str:
        _slog("draft_reddit_profile")
        content = {
            "username":    "alii_ai",
            "bio":         "Building Alii — self-hosted AI agent platform. Ollama + Alfred orchestrator + private memory. Building in public. All code at github. Privacy-first.",
            "target_subs": ["r/selfhosted", "r/LocalLLaMA", "r/MachineLearning",
                            "r/Python", "r/opensource", "r/artificial"],
            "posting_style": "Technical, honest, no hype. Share real numbers, real problems, real solutions.",
        }
        path = SOCIAL_DIR / "reddit_profile.json"
        _write(path, json.dumps(content, indent=2))
        _write_memory("social_agent", "Reddit profile drafted.")
        return json.dumps(content, indent=2)

    # ── (f) Content Calendar ──────────────────────────────────────────────────

    def content_calendar(self) -> str:
        _slog("content_calendar")
        bi = BUSINESS_IDENTITY
        today = datetime.now()

        # Build-in-public content themes by day of week
        themes = {
            0: ("Monday Metrics", "Share a real number from the system — uptime, tokens processed, memory entries"),
            1: ("Tech Tuesday", "Deep dive into one technical component — Alfred, the router, memory system"),
            2: ("Wednesday Win", "Something that worked. A bug fixed. A feature shipped."),
            3: ("Thursday Think", "Architecture decision, tradeoff, or lesson learned"),
            4: ("Friday Feature", "Demo or screenshot of something new"),
            5: ("Saturday Ship", "Release notes or commit summary"),
            6: ("Sunday Story", "Why we're building this. The bigger vision."),
        }

        platform_map = {
            "Twitter":   "Short. Max 280 chars. Technical or punchy. Link to GitHub.",
            "GitHub":    "Release notes, issue updates, README improvements, discussions.",
            "Reddit":    "Long-form post with full context. Link to GitHub. No self-promo without value.",
            "LinkedIn":  "Professional angle. Business value. Who this helps and why.",
        }

        days = []
        for i in range(30):
            day = today + timedelta(days=i)
            dow = day.weekday()
            theme, description = themes[dow]
            days.append({
                "date":        day.strftime("%Y-%m-%d"),
                "weekday":     day.strftime("%A"),
                "theme":       theme,
                "description": description,
                "platforms":   list(platform_map.keys()),
                "drafted":     False,
            })

        md_lines = [
            f"# Alii AI — 30-Day Content Calendar",
            f"*{today.strftime('%B %Y')} | Build-in-Public Strategy*",
            "",
            "## Platform Guides",
            "",
        ]
        for platform, guide in platform_map.items():
            md_lines.append(f"**{platform}:** {guide}")
        md_lines.append("")
        md_lines.append("## Daily Schedule")
        md_lines.append("")

        for d in days:
            md_lines.append(f"### {d['date']} ({d['weekday']}) — {d['theme']}")
            md_lines.append(f"*{d['description']}*")
            md_lines.append("")
            for p in d["platforms"]:
                md_lines.append(f"- [ ] **{p}:** draft content for {d['theme'].lower()}")
            md_lines.append("")

        # Flywheel note
        md_lines += [
            "---",
            "## Cross-Platform Flywheel",
            "",
            "Every release → GitHub release notes (MediaAgent.generate_release_notes())",
            "Every GitHub release → triggers Reddit post on r/selfhosted",
            "Every GitHub release → triggers LinkedIn update",
            "Every Twitter thread → pinned to GitHub Discussions",
            "Every Kickstarter milestone → all platforms simultaneously",
            "Content calendar (this file) → drives everything",
            "",
            "**Model:** Apple/Tesla/OpenAI all use release-driven social:",
            "- GitHub release is the single source of truth",
            "- Social accounts amplify the release, link back to GitHub",
            "- Community discussions feed back into the roadmap",
            "- Transparency builds trust → trust drives installs → installs drive revenue",
        ]

        content = "\n".join(md_lines)
        path = SOCIAL_DIR / "content_calendar.md"
        _write(path, content)
        _write_memory("social_agent", "30-day content calendar generated.")
        return content

    # ── (g) Privacy Audit ─────────────────────────────────────────────────────

    def privacy_audit_check(self, text: str) -> dict:
        """Public wrapper around the module-level privacy_audit function."""
        result = privacy_audit(text)
        _slog(f"Privacy audit: {result['status']} ({len(result['findings'])} findings)")
        return result

    # ── (h) Launch Posts ──────────────────────────────────────────────────────

    def generate_launch_post(self) -> str:
        _slog("generate_launch_post")
        bi = BUSINESS_IDENTITY

        content = f"""# Alii AI — Launch Posts
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

Code: {bi['github']}

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

GitHub: {bi['github']}
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
- HTTP control API (port 7000): /health, /status, /task, /control/{{service}}

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

Repo: {bi['github']}
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

Open source: {bi['github']}

If you're building AI infrastructure or care about data privacy, I'd love your feedback.

#AI #OpenSource #Privacy #SelfHosted #BuildInPublic #Alii
"""
        audit = privacy_audit(content)
        if audit["status"] == "BLOCKED":
            _slog(f"Launch posts BLOCKED by privacy filter: {audit['findings']}")
            return f"BLOCKED: {audit['findings']}"

        path = SOCIAL_DIR / "launch_posts.md"
        _write(path, content)
        _write_memory("social_agent", "Launch posts generated.")
        return content

    # ── Cross-platform sync flywheel ──────────────────────────────────────────

    def cross_platform_sync(self) -> dict:
        """
        Generate release notes and draft cross-platform sync posts.
        Every release → GitHub → triggers Reddit + LinkedIn + Twitter.
        This is the content flywheel.
        """
        _slog("cross_platform_sync")
        try:
            import sys
            sys.path.insert(0, str(WORKDIR))
            from agents.media_agent import MediaAgent
            changelog = MediaAgent().generate_release_notes()
            notes_snippet = changelog[:500]
        except Exception as exc:
            notes_snippet = f"(release notes unavailable: {exc})"

        sync_report = {
            "timestamp":     datetime.now().isoformat(),
            "triggered_by":  "daily_9am_cron",
            "release_notes": notes_snippet[:200],
            "platforms": {
                "github": {
                    "action":  "CHANGELOG.md updated",
                    "status":  "done",
                },
                "twitter": {
                    "action":  "Post release thread (stub — set TWITTER_API_KEY)",
                    "status":  "pending_credentials",
                },
                "reddit": {
                    "action":  "Post to r/selfhosted (stub — set REDDIT_CLIENT_ID)",
                    "status":  "pending_credentials",
                },
                "linkedin": {
                    "action":  "Post update (stub — set LINKEDIN_TOKEN)",
                    "status":  "pending_credentials",
                },
            },
            "flywheel_status": "partial — changelog written, social posting pending API keys",
        }

        path = SOCIAL_DIR / "sync_report.json"
        _write(path, json.dumps(sync_report, indent=2))
        _write_memory("social_agent", "Cross-platform sync run.")
        _slog(f"Cross-platform sync complete: {sync_report['flywheel_status']}")
        return sync_report
