#!/usr/bin/env python3
"""
MoneyAgent — Alii revenue tracking and monetisation manager.
Tracks metrics, analyses revenue streams, and generates daily financial reports.
"""

import json
import logging
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.money_agent")

WORKDIR       = Path("/home/avalii/moltbot")
TODO_FILE     = WORKDIR / "alfred_todo.json"
REVENUE_REPORT = WORKDIR / "memory" / "revenue_report.json"


def _load_todo() -> list:
    if TODO_FILE.exists():
        try:
            return json.loads(TODO_FILE.read_text())
        except Exception:
            return []
    return []


def _save_todo(tasks: list):
    TODO_FILE.write_text(json.dumps(tasks, indent=2))


def _add_todo(task: str):
    tasks = _load_todo()
    tasks.append({"task": task, "created_at": datetime.utcnow().isoformat() + "Z", "done": False})
    _save_todo(tasks)


def _write_memory(category: str, content: str):
    """Write an event to SQLite memory on every call."""
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
        log.debug("Memory written: [%s] %s", category, content[:80])
    except Exception as exc:
        log.warning("Memory write failed: %s", exc)


class MoneyAgent:
    """Tracks and optimises Alii's revenue opportunities."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        _write_memory("money_agent", "MoneyAgent initialised.")
        log.info("MoneyAgent initialised.")

    def _fetch_github_stars_curl(self, repo: str) -> int | None:
        """Fetch GitHub star count using curl subprocess (no auth needed for public repos)."""
        try:
            r = subprocess.run(
                ["curl", "-s", f"https://api.github.com/repos/{repo}"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return data.get("stargazers_count")
        except Exception as exc:
            log.warning("curl GitHub fetch failed: %s", exc)
        return None

    def _git_remote_repo(self) -> str | None:
        """Detect the GitHub repo slug from git remote origin."""
        try:
            r = subprocess.run(
                ["git", "-C", str(WORKDIR), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            url = r.stdout.strip()
            # https://github.com/user/repo.git  or  git@github.com:user/repo.git
            if "github.com" in url:
                slug = url.split("github.com")[-1].lstrip(":/").removesuffix(".git")
                return slug
        except Exception:
            pass
        return None

    def analyze_revenue_streams(self) -> dict:
        """
        Survey all known revenue streams, fetch live GitHub data, and write revenue_report.json.
        """
        log.info("analyze_revenue_streams called.")

        # Live GitHub star count
        repo_slug = self._git_remote_repo()
        stars = None
        if repo_slug:
            stars = self._fetch_github_stars_curl(repo_slug)
            log.info("GitHub stars for %s: %s", repo_slug, stars)

        # System uptime info
        try:
            uptime_r = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
            uptime = uptime_r.stdout.strip()
        except Exception:
            uptime = "unknown"

        # Alfred service status
        try:
            svc_r = subprocess.run(
                ["systemctl", "--user", "is-active", "alfred.service"],
                capture_output=True, text=True
            )
            alfred_status = svc_r.stdout.strip()
        except Exception:
            alfred_status = "unknown"

        streams = {
            "github_sponsors": {
                "active": bool(self.github_token),
                "monthly_usd": None,
                "github_stars": stars,
                "github_repo": repo_slug,
                "note": "Enable Sponsors at github.com/sponsors/dashboard",
                "action_required": not bool(self.github_token),
            },
            "kickstarter": {
                "active": False,
                "goal_usd": 10000,
                "pledged_usd": 0,
                "note": "Draft campaign not yet launched.",
                "action_required": True,
            },
            "saas_subscription": {
                "active": False,
                "mrr_usd": None,
                "note": "No hosted offering yet. Consider Stripe + hosted Alii tier.",
                "action_required": True,
            },
            "consulting": {
                "active": False,
                "hourly_rate_usd": None,
                "note": "Post availability on LinkedIn / Upwork.",
                "action_required": True,
            },
        }

        immediate_actions = [
            "1. Push repo to GitHub: gh repo create alii --public --source=. --push",
            "2. Enable GitHub Sponsors: https://github.com/sponsors/dashboard",
            "3. Create $5/$20/$99 sponsor tiers",
            "4. Write a project description and add topics on GitHub",
            "5. Post on r/selfhosted and r/MachineLearning",
            "6. Draft Kickstarter campaign page",
        ]

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "system_uptime": uptime,
            "alfred_status": alfred_status,
            "streams": streams,
            "total_mrr_usd": 0,
            "immediate_actions": immediate_actions,
        }

        REVENUE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        REVENUE_REPORT.write_text(json.dumps(result, indent=2))
        log.info("revenue_report.json written to %s", REVENUE_REPORT)
        _write_memory("money_agent", f"Revenue analysis written. Stars: {stars}")
        return result

    def track_github_stars(self, repo: str = "your-username/alii") -> dict:
        """Fetch GitHub star count — proxy for organic growth / validation."""
        log.info("track_github_stars: repo=%s", repo)
        result: dict = {"repo": repo, "stars": None, "stub": True}
        if self.github_token:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}",
                    headers={"Authorization": f"token {self.github_token}",
                             "Accept": "application/vnd.github.v3+json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                result = {"repo": repo, "stars": data.get("stargazers_count"), "stub": False}
            except Exception as exc:
                log.warning("GitHub API error: %s", exc)
                result["error"] = str(exc)
        _write_memory("money_agent", f"GitHub stars: {result}")
        return result

    def estimate_mrr(self) -> dict:
        """Estimate monthly recurring revenue from all active streams."""
        log.info("estimate_mrr called.")
        streams = self.analyze_revenue_streams()["streams"]
        mrr = sum(
            (v.get("monthly_usd") or 0)
            for v in streams.values()
            if isinstance(v, dict)
        )
        result = {
            "mrr_usd": mrr,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "note": "MRR is $0 until paid tiers are configured.",
        }
        _write_memory("money_agent", f"MRR estimate: {result}")
        if mrr == 0:
            _add_todo("Set up GitHub Sponsors tiers to start earning MRR")
        return result

    def recommend_pricing(self) -> list[dict]:
        """Return a tiered pricing recommendation for Alii-as-a-service."""
        log.info("recommend_pricing called.")
        tiers = [
            {"tier": "Free",        "price_usd": 0,    "features": ["Local install", "Community support"]},
            {"tier": "Supporter",   "price_usd": 5,    "features": ["GitHub Sponsors badge", "Priority issues"]},
            {"tier": "Pro",         "price_usd": 20,   "features": ["Hosted instance", "Private memory", "Email support"]},
            {"tier": "Enterprise",  "price_usd": 99,   "features": ["Multi-node cluster", "SLA", "Custom models"]},
        ]
        _write_memory("money_agent", "Pricing recommendation generated.")
        return tiers

    def manage_github_sponsors(self, action: str = "status") -> dict:
        """Check or update GitHub Sponsors configuration (stub)."""
        log.info("manage_github_sponsors: action=%s", action)
        result: dict = {"action": action, "stub": True}
        if not self.github_token:
            _add_todo("Set GITHUB_TOKEN to enable GitHub Sponsors management")
            result["error"] = "GITHUB_TOKEN not set"
        _write_memory("money_agent", f"GitHub Sponsors: {action}")
        return result

    def kickstarter_status(self) -> dict:
        """Return current Kickstarter campaign status (stub)."""
        log.info("kickstarter_status called.")
        status = {
            "launched": False,
            "goal_usd": 10000,
            "pledged_usd": 0,
            "backers": 0,
            "days_remaining": None,
            "stub": True,
            "note": "Create and launch campaign at kickstarter.com",
        }
        _add_todo("Create Kickstarter draft campaign for Alii")
        _write_memory("money_agent", f"Kickstarter status: {status}")
        return status

    # ── ZERO-COST REVENUE (runs free, can earn within 7 days) ─────────────────

    def zero_cost_revenue(self) -> dict:
        """
        Zero-capital-required revenue strategy.
        Writes 5 complete guides to docs/business/ and docs/social/.
        All actions cost $0 to start and can generate real money within 7 days.
        """
        log.info("zero_cost_revenue: writing all zero-cost guides.")
        docs_dir = WORKDIR / "docs" / "business"
        social_dir = WORKDIR / "docs" / "social"
        docs_dir.mkdir(parents=True, exist_ok=True)
        social_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        # ── (a) GitHub Sponsors ───────────────────────────────────────────────
        sponsors_guide = """\
# GitHub Sponsors Setup Guide — Alii AI
*Free to set up. Can receive donations the same day repo goes public.*

---

## Why GitHub Sponsors First

- FREE: No platform fees (GitHub waives fees for 2 years for new sponsors)
- FAST: Activate in 30 minutes, visible to every visitor the moment repo is public
- TRUSTED: GitHub users already have payment info saved
- ALGOS BOOST: GitHub surfaces Sponsors repos in search and "Explore"

---

## Step-by-Step Setup

### 1. Enable GitHub Sponsors (5 minutes)

1. Push your repo to GitHub (public):
   ```
   gh repo create alii --public --source=. --push
   ```
2. Go to: https://github.com/sponsors/dashboard
3. Click "Join the waitlist" (usually approved within 1-3 business days)
4. Fill out: country (US), payee type (Individual), bank/PayPal info

### 2. Create Your Sponsor Tiers

Set these EXACT tiers (proven to convert):

| Tier | Price | What to Say |
|------|-------|-------------|
| Coffee | $5/mo | "Buy me a coffee — keeps the repo alive" |
| Supporter | $20/mo | "Get your name in the README + join Discord" |
| Pro Backer | $99/mo | "Early access to Pro features + direct Slack" |
| Corporate | $499/mo | "Logo on README + 2hrs support/month" |

**Key:** $5 tier converts the most. $499 tier makes the $5 look tiny (anchoring).

### 3. Optimize Your Profile

Add to your README (copy-paste):
```markdown
## Support Alii

If Alii saves you time or money, consider sponsoring:

[![GitHub Sponsors](https://img.shields.io/github/sponsors/YOUR_USERNAME?style=social)](https://github.com/sponsors/YOUR_USERNAME)

| [☕ $5/mo - Coffee](https://github.com/sponsors/YOUR_USERNAME) | [⭐ $20/mo - Supporter](https://github.com/sponsors/YOUR_USERNAME) | [🚀 $99/mo - Pro Backer](https://github.com/sponsors/YOUR_USERNAME) |
```

### 4. First Sponsors Strategy

- Post in the repo's first commit: "Sponsorships open at github.com/sponsors/YOUR_USERNAME"
- Add a FUNDING.yml to .github/ directory:
  ```yaml
  # .github/FUNDING.yml
  github: YOUR_USERNAME
  ko_fi: YOUR_KOFI_USERNAME
  custom: ["https://ko-fi.com/YOUR_USERNAME"]
  ```
- This adds a "Sponsor" button to every page of your repo

### 5. Realistic First Month Projections

| Scenario | Sponsors | MRR |
|----------|----------|-----|
| Conservative | 3 @ $5 | $15 |
| Realistic | 5 @ $5 + 1 @ $20 | $45 |
| Good HN post | 20 @ $5 + 3 @ $20 | $160 |
| Viral | 100 @ $5 + 10 @ $20 | $700 |

---

## Tax Note
GitHub Sponsors sends a 1099-K if you earn over $600/year in the US.
Set aside 25-30% for taxes. Keep records of all expenses (hardware, software, internet).
"""
        p = docs_dir / "github_sponsors_setup.md"
        p.write_text(sponsors_guide)
        results["github_sponsors"] = str(p)
        log.info("Written: %s", p)

        # ── (b) Ko-fi ─────────────────────────────────────────────────────────
        kofi_guide = """\
# Ko-fi Setup Guide — Alii AI
*Free. No fees on donations. Instant PayPal/Stripe payout.*

---

## Why Ko-fi

- 0% platform fee on donations (Ko-fi takes nothing — they monetize via Ko-fi Gold upgrades)
- One-time AND monthly support options
- Instant payout to PayPal or Stripe (no 30-day hold like Patreon)
- Can sell digital products (guides, templates, agent packs) directly
- No minimum payout threshold

---

## Setup (15 minutes)

### 1. Create Account
- Go to: https://ko-fi.com
- Sign up with email or Google
- Username: `alii_ai` (or similar)

### 2. Connect Payments
- Settings → Payment → Connect PayPal or Stripe
- PayPal: money arrives in minutes
- Stripe: money arrives in 2 business days

### 3. Set Up Your Page

**Page Name:** Alii AI
**Tagline:** "Support the development of a private, self-hosted AI agent platform"

**About section (copy-paste this):**
```
Hi! I'm building Alii — an open-source AI agent platform that runs completely
on your own hardware. No subscriptions. No data sent to corporations. Your AI,
your rules.

Every coffee helps me:
- Keep the servers running for testing
- Dedicate more time to Alii instead of client work
- Buy hardware to test more AI models

Thank you for believing in private AI.
```

### 4. Add Monthly Memberships (Ko-fi Gold — $6/mo to Ko-fi)

If you upgrade to Ko-fi Gold ($6/mo — worth it at $100+/mo earnings):
- Unlimited monthly memberships
- Member-only posts
- Discord role integration

Membership tiers:
| Tier | Price | Perk |
|------|-------|------|
| Supporter | $3/mo | Discord access |
| Pro Backer | $10/mo | Early releases + Discord |
| Founding Member | $25/mo | Name in README + Discord |

### 5. Sell Digital Products on Ko-fi (FREE feature)

Products you can sell TODAY:
- "Alii Quick Setup Guide" — $9.99 PDF
- "AI Agent Prompt Templates Pack" — $14.99
- "How I Built a Self-Healing AI System" — $19.99 eBook

Ko-fi takes 0% on digital product sales.

### 6. Embed on GitHub

Add to README:
```markdown
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/YOUR_KOFI_USERNAME)
```

---

## Ko-fi vs GitHub Sponsors — Use Both

| | Ko-fi | GitHub Sponsors |
|---|---|---|
| Fees | 0% | 0% (2yr promo) |
| Payout | Instant | Monthly |
| Discoverability | Ko-fi explore page | GitHub explore |
| Digital products | YES | No |
| Best for | One-time + products | Recurring community |

Run both simultaneously. Different audiences will find different platforms.
"""
        p = docs_dir / "kofi_setup.md"
        p.write_text(kofi_guide)
        results["kofi"] = str(p)
        log.info("Written: %s", p)

        # ── (c) Replit Bounties ───────────────────────────────────────────────
        replit_guide = """\
# Replit Bounties Strategy — Alii AI
*Developers pay for AI tools. Offer Alii setup as a paid service.*

---

## What is Replit Bounties?

Replit Bounties (https://replit.com/bounties) is a marketplace where:
- Businesses post programming tasks with a dollar reward
- Developers (you) claim and complete them for payment
- Replit handles payment processing and escrow

**Payout:** Direct to Stripe or PayPal, same-day after work approved

---

## How to Earn with Alii Skills Right Now

### Strategy 1: Claim AI Agent Bounties

Search bounties for:
- "AI chatbot" → You can build this with Alii in 2hrs
- "Ollama setup" → You literally just did this
- "LLM integration" → Your specialty
- "Python automation" → Alfred is Python automation
- "scraping + AI" → agents/social_agent.py does this

**Typical pay:** $50-500 per bounty
**Time to complete:** 2-8 hours with Alii as your toolkit

### Strategy 2: Post Alii as a Service Offering

On Replit's "Showcase" and community Discord:
```
Title: "I'll set up a private AI agent system on your server"

What you get:
- Alii AI platform installed and configured on your Linux server
- Alfred orchestrator running as a systemd service
- Web UI accessible via your domain
- 3 custom agents built for your use case
- 30 days of support

Price: $299 one-time setup fee
Delivery: 3-5 business days
```

### Strategy 3: Build Replit Templates for Alii

Create public Replit templates:
1. "Alii AI Lite — Single-Agent Chatbot" (free template, sell the upgrade)
2. "Alfred Orchestrator Demo" (demonstrates the platform)
3. "AI Business Plan Generator" (uses BusinessAgent)

Templates drive traffic to your GitHub → Sponsors

---

## Replit Profile Optimization

1. Profile URL: replit.com/@yourusername
2. Bio: "Building Alii: private AI agents that run on your hardware | Open source"
3. Link to GitHub repo
4. Post 2-3 Repls showing Alii capabilities

---

## Realistic Earning Potential

| Activity | Time | Payment |
|----------|------|---------|
| 1 AI chatbot bounty | 3hrs | $100-300 |
| 1 automation bounty | 4hrs | $150-400 |
| Alii setup service | 5hrs | $299 |
| Monthly: 4 setups | 20hrs | $1,196 |

**First 7 days goal:** Claim 1 bounty ($100-300). Use earnings for LLC filing.
"""
        p = docs_dir / "replit_bounties_strategy.md"
        p.write_text(replit_guide)
        results["replit_bounties"] = str(p)
        log.info("Written: %s", p)

        # ── (d) Product Hunt Upcoming ─────────────────────────────────────────
        ph_guide = """\
# Product Hunt Upcoming Page — Alii AI
*Free to create. Builds email waitlist before launch. Generates buzz.*

---

## Why Product Hunt Upcoming

- FREE to set up at producthunt.com/upcoming/your-product
- Collects emails before launch — so you have a list to notify on launch day
- Products with 100+ upvotes on launch day often make #1 Product of the Day
- Being featured = thousands of visitors, press, and early customers

---

## Your Upcoming Page (Ready to Submit)

**Go to:** https://www.producthunt.com/posts/new

### Page Details

**Name:** Alii AI

**Tagline (60 chars max):**
```
Your private AI agent that runs entirely on your hardware
```

**Description:**
```
Alii is an open-source autonomous AI platform that gives you a personal
Alfred — a self-healing AI orchestrator that manages specialized agents
for law, business, media, security, and finance.

Unlike ChatGPT or Claude, Alii runs 100% on your own machine. Your data
never leaves. No subscriptions. No API fees. No surveillance.

Built on Ollama + Python + SQLite. Runs on any Linux machine with 8GB RAM.
```

**Topics (select all that apply):**
- Artificial Intelligence
- Developer Tools
- Open Source
- Productivity
- Privacy

**Links:**
- Website: https://github.com/your-username/alii (until you have a domain)
- GitHub: https://github.com/your-username/alii

### Thumbnail Image Description
Create a simple image (240x240px):
- Dark background (#0d1117)
- Alii logo or "A" lettermark in white
- Tagline: "Your Private AI Agent"
- Can use Canva (free) in 10 minutes

---

## Launch Day Checklist (do this the day you launch)

- [ ] Post at 12:01 AM Pacific Time (when PH resets)
- [ ] Share in HackerNews (Show HN post ready in docs/social/hackernews_post.md)
- [ ] Post in r/selfhosted, r/LocalLLaMA, r/MachineLearning
- [ ] Tweet / post to LinkedIn
- [ ] Message all GitHub stargazers (via GH API)
- [ ] Email waitlist from Upcoming page
- [ ] Ask 20 friends to upvote (don't ask to "upvote" — ask if they'd "check it out")

---

## Maker Profile

Fill out your Product Hunt maker profile:
- Name: Your real name
- Bio: "Building Alii — private, self-hosted AI agents | OSS founder"
- Twitter / LinkedIn links
- Your product's GitHub link

---

## Realistic PH Launch Results

| Scenario | Upvotes | Visitors | New GitHub Stars | New Sponsors |
|----------|---------|----------|-----------------|--------------|
| No prep | 10-30 | 200 | 5 | 0 |
| With waitlist (50 emails) | 50-100 | 1,000 | 50 | 2-5 |
| Great HN + PH combo | 200-500 | 5,000 | 200 | 10-20 |
| #1 Product of Day | 500+ | 20,000+ | 500+ | 50+ |

Product Hunt is free. The upside is enormous. The downside is zero.
"""
        p = docs_dir / "product_hunt_upcoming.md"
        p.write_text(ph_guide)
        results["product_hunt"] = str(p)
        log.info("Written: %s", p)

        # ── (e) HackerNews Show HN post ───────────────────────────────────────
        hn_post = """\
# HackerNews Show HN Post — Alii AI
*One viral HN post has funded entire startups. This costs nothing.*

---

## POSTING INSTRUCTIONS

- URL: https://news.ycombinator.com/submit
- Title MUST start with: "Show HN:"
- Post at: 9-10am Eastern on a Tuesday, Wednesday, or Thursday
- Do NOT pay for upvotes (instant ban)
- DO respond to every single comment within the first 2 hours

---

## THE POST (copy-paste ready)

**Title (80 chars max):**
```
Show HN: Alii – an open-source autonomous AI agent platform that runs locally
```

**Text (optional but strongly recommended for Show HN):**
```
I've been building Alii for the past few months — a self-hosted AI agent
platform designed to run entirely on your own hardware with no cloud
dependencies.

The core idea: you shouldn't need to send your data to OpenAI to get
serious AI-assisted workflows.

What it does:
- Alfred orchestrator: manages multiple AI agents with self-healing
  (restarts failed services automatically via systemd)
- Multi-model router: routes tasks to the best local Ollama model
  (fast model for quick questions, powerful model for reasoning tasks)
- Persistent SQLite memory: every conversation is saved and searchable
- Specialized agents: law (LLC formation, contracts), business (financial
  models, competitor analysis), media (release notes, changelogs),
  security (port audits, hardening), money (revenue tracking)
- Two-way mobile control: send commands from your phone via ntfy.sh

Hardware requirements: Linux, 8GB+ RAM, any modern CPU. No GPU required
(though it helps). I'm running this on a 12-core workstation with 32GB RAM.

The whole stack: Python + asyncio + aiohttp + Ollama + SQLite + Chainlit

GitHub: [link]

Happy to answer questions about the architecture, the self-healing design,
or why I chose local LLMs over API calls.
```

---

## EXPECTED HN COMMENT QUESTIONS (prepare answers now)

**"Why not just use AutoGPT/LangChain/CrewAI?"**
```
AutoGPT is unreliable in production — it hallucinates tool calls and has no
self-healing. LangChain is a framework, not a product; you still have to build
everything yourself. CrewAI has no memory persistence or production orchestration.

Alii is production-grade: Alfred has been running for [X] days with zero manual
restarts. The watchdog automatically recovers failed services.
```

**"What models does it use?"**
```
Currently Ollama-based: Mistral 7B for fast tasks, Qwen 2.5 14B for reasoning,
neural-chat for conversation, dolphin-phi for lightweight. The router uses
keyword classification to pick the right model automatically.

You can swap in any Ollama-compatible model — llama3, gemma, mixtral, etc.
```

**"How is this different from Open WebUI?"**
```
Open WebUI is a chat interface for Ollama. Alii is an agent platform — it
takes autonomous actions, manages scheduled tasks, writes documents, monitors
your system, and coordinates specialized agents. Think of Open WebUI as a
keyboard; Alii is the whole autonomous system.
```

**"What's the licensing?"**
```
AGPL-3.0 for the core platform. This means you can self-host freely,
but if you build a SaaS on top of it, you need to open-source your changes
or get a commercial license. Same model as Grafana, MongoDB, etc.
```

**"Is this production-ready?"**
```
It's running in my personal production environment. I wouldn't call it
enterprise-ready yet — there's no multi-user auth, no encrypted memory,
no horizontal scaling. Those are on the roadmap. It's solid for solo use
and small teams with a Linux server.
```

**"What's your monetization plan?"**
```
Open core: free to self-host. Paid hosted tier coming (managed instance,
no server required). GitHub Sponsors for community support.
Long-term: enterprise on-premises licenses for regulated industries
that can't use cloud AI (healthcare, legal, finance).
```

---

## AFTER YOU POST

1. Set a 2-hour timer — respond to every comment within 2 hours
2. Never be defensive — "that's a great point, here's how I'm thinking about it"
3. If someone says something harsh: "Fair criticism, adding to the roadmap"
4. Share on Twitter/LinkedIn ONLY AFTER you have 10+ comments (creates social proof)
5. Screenshot the thread for your Product Hunt launch

---

## REALISTIC HN OUTCOMES

| Result | Front Page? | Traffic | Stars | Sponsors |
|--------|-----------|---------|-------|----------|
| <10 points | No | 50 | 0-2 | 0 |
| 10-50 points | Maybe | 500 | 10-30 | 0-2 |
| 50-200 points | Yes | 3,000 | 50-200 | 2-10 |
| 200+ points | Top 5 | 15,000+ | 500+ | 20-50 |
| 500+ points | #1 | 50,000+ | 2000+ | 100+ |

Tarsnap launched from HN. Hacker News has directly funded dozens of startups.
The cost to try: $0.
"""
        p = social_dir / "hackernews_post.md"
        p.write_text(hn_post)
        results["hackernews"] = str(p)
        log.info("Written: %s", p)

        _write_memory("money_agent", f"zero_cost_revenue: wrote {len(results)} guides.")
        log.info("zero_cost_revenue complete. Files: %s", list(results.values()))
        return results

    # ── FREELANCE PIPELINE ────────────────────────────────────────────────────

    def freelance_pipeline(self) -> str:
        """
        Write docs/business/freelance_strategy.md — how to earn $150-500/project
        offering AI agent setup as a freelance service using Alii skills right now.
        """
        log.info("freelance_pipeline")
        docs_dir = WORKDIR / "docs" / "business"
        docs_dir.mkdir(parents=True, exist_ok=True)

        content = """\
# Freelance AI Agent Setup — Revenue Strategy
*Use skills you already have. Earn $150-500 per project. Start today.*

---

## The Opportunity

You just built:
- A self-healing AI orchestrator (Alfred)
- Multi-model LLM routing
- Specialized AI agents (law, business, media, security, money)
- Systemd service management
- Private AI infrastructure on Linux

**Businesses will pay $150-500 for this exact setup.** Most companies don't have
a developer who knows Ollama + Python + Linux + AI agents. You do.

---

## Platform 1: Upwork

**URL:** https://www.upwork.com

### Profile Setup (30 minutes)

**Title:**
```
AI Agent Developer | Ollama | LangChain | Private LLM Systems | Python
```

**Overview (copy-paste, customize):**
```
I build private, self-hosted AI systems that run on your own infrastructure —
no API fees, no data leaving your servers.

Specialties:
• Autonomous AI agents (planning, execution, monitoring)
• Local LLM deployment (Ollama, LLaMA, Mistral, Qwen)
• AI workflow automation and orchestration
• Custom chatbots with persistent memory
• Python/FastAPI AI backends
• Linux server setup and hardening

Recent project: Built "Alfred" — a self-healing AI orchestrator managing
10+ specialized agents across law, business, media, security, and finance
for a production Linux workstation.

I work fast, communicate clearly, and deliver working systems — not demos.
```

**Skills to add:**
Python, Artificial Intelligence, Machine Learning, Natural Language Processing,
Linux System Administration, API Development, Automation, Ollama, LangChain,
FastAPI, Docker, SQLite, Bash Scripting

**Hourly Rate:**
- Start at $45/hr (competitive for AI work, will get jobs quickly)
- Raise to $75/hr after first 3 reviews
- Raise to $125/hr after 5-star rating established

### Services to Offer (Fixed Price Projects)

#### Service 1: AI Chatbot Setup — $199
```
What you get:
- Ollama installed and configured on your Linux server
- 2 AI models set up (fast + smart)
- Web chat interface (Chainlit or Open WebUI)
- Systemd service (runs 24/7, auto-restarts)
- 14 days of support

Delivery: 2-3 business days
Requirements: Linux server with 8GB+ RAM
```

#### Service 2: Full Alii Agent Platform — $399
```
What you get:
- Complete Alii platform installed and configured
- Alfred orchestrator as a systemd service
- 3 custom agents for your use case
- Web UI at your domain/IP
- API access (Alfred HTTP API)
- 30 days of support

Delivery: 5-7 business days
Requirements: Linux server with 16GB+ RAM
```

#### Service 3: AI Automation Workflow — $299
```
What you get:
- Custom Python AI agent for your specific task
- Scheduled automation (daily/weekly/on-trigger)
- Logging and error alerts
- Documentation

Examples: email summarizer, report generator, data analyzer,
          content creator, market monitor

Delivery: 3-5 business days
```

### How to Get First Jobs Fast

1. **Bid on 5 jobs per day** for the first 2 weeks
2. **Target jobs under $500** (less competition, faster hire)
3. **Write personalized proposals** (mention specific details from their job post)
4. **Offer a free 30-min consultation** to close the deal
5. **First 3 jobs: underprice to build reviews** (even $99 for a basic setup)

**Search terms for good leads:**
- "AI chatbot setup"
- "Ollama install"
- "local LLM"
- "AI automation Python"
- "self-hosted AI"
- "private ChatGPT"
- "AI agent developer"

---

## Platform 2: Fiverr

**URL:** https://www.fiverr.com

### Gig Setup

**Gig Title:**
```
I will set up a private AI chatbot on your Linux server using Ollama
```

**Category:** Programming & Tech → Web Programming → AI Services

**Packages:**

| | Basic | Standard | Premium |
|-|-------|----------|---------|
| Name | AI Starter | AI Pro | Alii Platform |
| Price | $149 | $299 | $499 |
| What's included | Ollama + 1 model + basic UI | Ollama + 3 models + Chainlit | Full Alii platform + 3 agents |
| Delivery | 3 days | 5 days | 7 days |
| Revisions | 1 | 2 | 3 |
| Support after | 7 days | 14 days | 30 days |

**Gig Description (copy-paste):**
```
I'll set up a completely private AI assistant on YOUR server — no OpenAI API
costs, no data leaving your machine, no monthly subscriptions.

Perfect if you want:
✅ A private ChatGPT that costs nothing after setup
✅ AI that runs on your own hardware (no privacy concerns)
✅ Custom AI workflows and automation
✅ Professional AI integration without hiring a full-time developer

What I use: Ollama, Python, Chainlit, systemd, Linux

Requirements you need: A Linux server (VPS or physical) with 8GB+ RAM

Message me before ordering to make sure your server meets requirements.
I respond within 2 hours.
```

### Fiverr Profile Tips

- Add a profile video (2 mins — walk through Alii running live)
- Offer 1-day delivery on the Basic tier to appear in "Fast Delivery" filter
- Respond to ALL messages within 1 hour (Fiverr rewards response rate)

---

## Platform 3: Direct Outreach (Highest ROI)

### Who to Target

- Reddit: r/selfhosted posters asking "how do I set up local AI?"
- Reddit: r/LocalLLaMA — people struggling with setup
- Discord: Ollama Discord — users with setup problems
- LinkedIn: IT managers at small law firms, healthcare practices, finance companies

### Message Template (DM on Reddit)

```
Hey! Saw your post about [their specific problem]. I actually built a
system that solves exactly this — a self-healing AI orchestrator called
Alii that runs locally.

I offer setup services for $299. Happy to jump on a quick call if you
want to see a demo.

No pressure either way — if you want to DIY it, I can point you to the
GitHub repo.
```

---

## Income Projections (Realistic First Month)

| Work | Rate | Monthly |
|------|------|---------|
| 2 Upwork projects | $299 each | $598 |
| 1 Fiverr gig | $149 | $149 |
| 1 direct client | $399 | $399 |
| **Total** | | **$1,146** |

This covers: Ohio LLC filing ($99), any software costs, + profit.

---

## Portfolio: Use Alii Itself

Your best portfolio piece is what you just built. For every proposal:
- Screenshot of Alfred running (terminal + web UI)
- List of agents you built
- Mention "running in production on a 12-core workstation"
- GitHub link (once public)

**Clients hire people who've done the thing. You've done the thing.**

---

## Fulfillment Process (How to Deliver)

1. Client provides SSH access to their server
2. You run the Alii installer / setup script (takes ~2hrs)
3. You configure agents for their use case
4. You write a quick docs file explaining how to use it
5. Deliver, collect payment, request a review

Total time per delivery: 2-5 hours.
At $299: that's $60-150/hr effective rate.
"""
        p = docs_dir / "freelance_strategy.md"
        p.write_text(content)
        _write_memory("money_agent", "freelance_pipeline: strategy written.")
        log.info("Written: %s", p)
        return content

    # ── OPEN SOURCE MONETIZATION ──────────────────────────────────────────────

    def open_source_monetization(self) -> str:
        """
        Write docs/business/oss_monetization.md — all free OSS funding platforms:
        GitHub Sponsors, Open Collective, Polar.sh, thanks.dev.
        """
        log.info("open_source_monetization")
        docs_dir = WORKDIR / "docs" / "business"
        docs_dir.mkdir(parents=True, exist_ok=True)

        content = """\
# Open Source Monetization Guide — Alii AI
*All platforms below are FREE to set up. Multiple streams = real income.*

---

## Strategy: Stack All Four Platforms

Don't pick one. Set up all four today. They take different audiences:
- GitHub Sponsors → developers who live on GitHub
- Ko-fi → general supporters and one-time donors
- Polar.sh → developers who want to support and get perks
- thanks.dev → passive attribution from other OSS projects

Total setup time: ~3 hours. Total cost: $0.

---

## Platform 1: GitHub Sponsors
**URL:** https://github.com/sponsors/dashboard
**Fee:** 0% (GitHub waives fees for qualifying maintainers)
**Payout:** Monthly via Stripe or PayPal

### Setup
1. Push repo public: `gh repo create alii --public --source=. --push`
2. Go to github.com/sponsors/dashboard → Join waitlist
3. Approval: 1-5 business days
4. Create tiers (see github_sponsors_setup.md for exact tier config)

### Add FUNDING.yml (required for "Sponsor" button on every page)
Create `.github/FUNDING.yml`:
```yaml
github: YOUR_GITHUB_USERNAME
ko_fi: YOUR_KOFI_USERNAME
polar: YOUR_POLAR_USERNAME
custom: ["https://ko-fi.com/YOUR_USERNAME"]
```

### Tier Recommendations
| Tier | Price | Suggested Perk |
|------|-------|----------------|
| Coffee | $5/mo | Name in CONTRIBUTORS.md |
| Supporter | $20/mo | Discord + priority issues |
| Pro Backer | $99/mo | Early feature access + Slack |
| Corporate | $499/mo | Logo in README + 2hrs/mo support |

### Realistic Income
- 0 stars: $0
- 100 stars: $15-50/mo (1-3 sponsors at $5-20)
- 500 stars: $100-300/mo
- 1000 stars: $300-1000/mo
- 5000 stars: $1000-5000/mo

---

## Platform 2: Ko-fi
**URL:** https://ko-fi.com
**Fee:** 0% on donations (5% on shop sales, 0% with Ko-fi Gold)
**Payout:** Instant to PayPal or Stripe

### What Makes Ko-fi Different
- One-time donations work great (GitHub Sponsors is monthly-first)
- Can sell digital products (guides, templates, agent configs)
- No minimum payout
- Appears in Ko-fi's "explore" section for discoverability

### Products to Sell on Ko-fi (all digital, zero marginal cost)
| Product | Price | Description |
|---------|-------|-------------|
| Alii Setup Guide PDF | $9.99 | Step-by-step install + config |
| Agent Prompt Template Pack | $14.99 | 50 tested prompts for all agents |
| Alfred Config Templates | $19.99 | Custom systemd configs for 5 use cases |
| Private AI Starter Bundle | $39.99 | All of the above |

### Setup: 15 minutes
See kofi_setup.md for complete walkthrough.

---

## Platform 3: Polar.sh
**URL:** https://polar.sh
**Fee:** 5% + Stripe fees (lowest combined fee in OSS funding)
**Payout:** Via Stripe, monthly

### What Makes Polar.sh Unique

Polar.sh is built specifically for OSS maintainers. Key features:

1. **Issue Funding:** Backers fund specific GitHub issues
   - "Add Docker support" → funded by community at $250
   - You solve it → you get paid
   - Zero-risk: only paid on completion

2. **Subscriptions with GitHub Perks:**
   - Automatically grants GitHub access on subscription
   - Connects to your repo's "Sponsor" button
   - Supporters get a "Supporter" badge in Issues/PRs

3. **Benefit Automation:**
   - Discord role automatically granted on subscription
   - GitHub repo access (for private bonus features) automatically granted

### Polar.sh Setup

1. Go to polar.sh → "Sign in with GitHub"
2. Connect your repository
3. Set up subscription tiers (mirrors your GitHub Sponsors tiers)
4. Optional: Set up Issue Funding for specific GitHub Issues

### Issue Funding Strategy

Create GitHub Issues for desired features, then fund them on Polar:

Example issues to create and fund:
- "Docker image for easy install" — Fund at $100
- "Windows/Mac support" — Fund at $200
- "One-click installer script" — Fund at $150
- "GPU acceleration support" — Fund at $200

Post in r/selfhosted: "These features are community-funded on Polar.sh"
→ Community contributes → You build → Everyone wins

---

## Platform 4: thanks.dev
**URL:** https://thanks.dev
**Fee:** 5%
**Payout:** Monthly

### What Is thanks.dev?

thanks.dev automatically distributes money to OSS dependencies.
When companies use your package and pay into thanks.dev, you receive
a share based on how heavily your package is used as a dependency.

### How to Receive From thanks.dev

1. Go to thanks.dev → "Claim your project"
2. Verify GitHub ownership
3. Connect Stripe for payouts
4. That's it — passive income as companies use packages that depend on yours

### How to SEND to your dependencies (and set an example)

$10/mo into thanks.dev distributes automatically to:
- Chainlit maintainers
- aiohttp maintainers
- Ollama contributors
- SQLite Python library maintainers

This builds goodwill and gets you mentioned in their communities.

---

## Open Collective
**URL:** https://opencollective.com
**Fee:** 10% + payment processor fees (higher than others)
**Best for:** When you have a community/foundation angle

### When to Use Open Collective
- You form an open-source foundation (not just a product)
- You want transparent finances (all expenses public)
- You need to pay contributors (OSS employees)
- You need fiscal sponsorship before forming an LLC

### Alii on Open Collective
Create a collective: opencollective.com/alii-ai
- Budget visible to all sponsors (builds trust)
- Can pay contractors directly through platform
- Corporate sponsors prefer Open Collective for accounting

---

## Combined Monthly Income Projections

Assumptions: 500 GitHub stars, 3 months old

| Platform | Scenario A (Low) | Scenario B (Mid) | Scenario C (Good) |
|----------|-----------------|-----------------|------------------|
| GitHub Sponsors | $30 | $150 | $500 |
| Ko-fi donations | $20 | $80 | $200 |
| Ko-fi products | $0 | $50 | $200 |
| Polar subscriptions | $20 | $100 | $300 |
| Polar issue funding | $0 | $100 | $400 |
| thanks.dev (passive) | $1 | $5 | $20 |
| **Total** | **$71** | **$485** | **$1,620** |

---

## Priority Action List (Do Today)

1. Push repo to GitHub (public) → unlocks everything else
2. Set up Ko-fi (15 min, instant payout) → start receiving TODAY
3. Apply for GitHub Sponsors (waitlist, 1-5 days)
4. Create Polar.sh account + connect repo (10 min)
5. Claim thanks.dev project (5 min)
6. Add FUNDING.yml to .github/ directory
7. Add sponsor badge/link to README top section
8. Post Show HN (see docs/social/hackernews_post.md)

---

## README Sponsor Section (copy-paste)

Add this near the top of your README.md:

```markdown
## Support Alii Development

Alii is free and open source. If it saves you time or money:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/YOUR_USERNAME)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/YOUR_USERNAME?style=social)](https://github.com/sponsors/YOUR_USERNAME)
[![Polar.sh](https://polar.sh/embed/seeks-funding-shield.svg?org=YOUR_USERNAME)](https://polar.sh/YOUR_USERNAME)

| [☕ Ko-fi](https://ko-fi.com/YOUR_USERNAME) | [💛 GitHub Sponsors](https://github.com/sponsors/YOUR_USERNAME) | [⭐ Polar.sh](https://polar.sh/YOUR_USERNAME) |
```
"""
        p = docs_dir / "oss_monetization.md"
        p.write_text(content)
        _write_memory("money_agent", "open_source_monetization: guide written.")
        log.info("Written: %s", p)
        return content

    def generate_daily_report(self) -> str:
        """Produce a plain-text daily revenue and growth report."""
        log.info("generate_daily_report called.")
        stars   = self.track_github_stars()
        mrr     = self.estimate_mrr()
        ks      = self.kickstarter_status()
        ts      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        report = (
            f"=== Alii Daily Revenue Report — {ts} ===\n"
            f"GitHub Stars : {stars.get('stars', 'N/A')}\n"
            f"MRR (USD)    : ${mrr['mrr_usd']:.2f}\n"
            f"Kickstarter  : {'LIVE' if ks['launched'] else 'NOT LAUNCHED'} "
            f"(${ks['pledged_usd']} / ${ks['goal_usd']})\n"
            f"Next Action  : Check alfred_todo.json for pending tasks.\n"
        )
        _write_memory("money_agent", f"Daily report generated:\n{report}")
        log.info("Daily report:\n%s", report)
        return report
