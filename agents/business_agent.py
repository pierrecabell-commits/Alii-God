#!/usr/bin/env python3
"""
BusinessAgent — AI startup strategist and CFO for Alii AI LLC.
Builds business plans, financial models, funding strategies, and campaign materials.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.business_agent")

WORKDIR  = Path(os.environ.get("ALII_WORKDIR", str(Path(__file__).resolve().parent.parent)))
BIZ_DIR  = WORKDIR / "docs" / "business"
LOG_DIR  = WORKDIR / "logs"


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    log.info("Written: %s (%d bytes)", path, len(content))


def _write_memory(category: str, content: str):
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception:
        pass


class BusinessAgent:
    """
    World-class AI startup strategist and virtual CFO for Alii AI LLC.

    ZERO-COST-FIRST STRATEGY: Pierre starts with zero capital.
    Every recommended action must be free to start and able to generate
    real income within 7 days. Priority order:
    1. GitHub Sponsors + Ko-fi (free, instant, community-funded)
    2. Freelance services on Upwork/Fiverr ($150-500/project, skills already built)
    3. OSS monetization: Polar.sh, thanks.dev, Open Collective (all free)
    4. HackerNews Show HN post (free, can go viral and fund the whole project)
    5. Product Hunt Upcoming page (free, builds email waitlist)
    Capital-intensive options (Kickstarter, SaaS hosting, ads) come LATER.
    """

    def __init__(self):
        BIZ_DIR.mkdir(parents=True, exist_ok=True)
        log.info("BusinessAgent initialised — zero-cost-first mode.")

    # ── (a) Business Plan ─────────────────────────────────────────────────────

    def build_business_plan(self) -> str:
        log.info("build_business_plan")
        ts = datetime.now().strftime("%B %Y")
        content = f"""# Alii AI — Business Plan
*{ts} | Confidential*

---

## Executive Summary

**Company:** Alii AI LLC (Ohio, 2026)
**Product:** Alii — an open-core autonomous AI agent platform that runs entirely on local hardware
**Stage:** Pre-revenue, MVP complete
**Ask:** $250,000 seed (SAFE, $2M cap)

Alii is a self-hosted, privacy-first AI assistant and autonomous agent platform. Unlike
cloud-dependent competitors, Alii gives users full control over their data and AI compute.
It routes tasks intelligently across local LLM models, orchestrates automated workflows,
and self-heals — all without a subscription to OpenAI or Anthropic.

**The opportunity:** The enterprise self-hosted AI market is projected to reach $47B by 2028.
Privacy regulations (GDPR, HIPAA, SOC2) are driving demand for on-premises AI solutions.
No current product combines multi-model routing + autonomous agents + private memory
in a developer-friendly, open-source package.

**Traction:**
- MVP deployed on production hardware (12-core CPU, 32GB RAM)
- Alfred orchestrator managing multiple services with self-healing
- 4 specialized agents (media, money, law, security)
- Seeking first 100 GitHub stars and 10 paying customers

---

## Problem

1. **Privacy:** ChatGPT, Claude, and Copilot send your data to third-party servers
2. **Cost:** API costs for heavy users reach $100–$500/month
3. **Control:** No ability to customize, fine-tune, or audit cloud AI behavior
4. **Compliance:** Regulated industries (healthcare, legal, finance) cannot use cloud AI

---

## Solution

Alii provides:
- **Local inference:** All AI runs on your hardware via Ollama
- **Smart routing:** Matches task type to the optimal local model automatically
- **Autonomous agents:** Pre-built agents for legal, business, media, security, finance
- **Self-healing:** Alfred orchestrator restarts failed services automatically
- **Open core:** Free to self-host; paid tiers for hosted and enterprise

---

## Market Analysis

### Total Addressable Market (TAM)
- Self-hosted AI tools market: **$8.2B** (2026), growing 34% CAGR
- Developer tools market: **$27B** (2026)
- Enterprise AI governance/compliance tools: **$5.1B** (2026)

### Serviceable Addressable Market (SAM)
- Privacy-conscious developers + SMBs: **$1.8B**

### Serviceable Obtainable Market (SOM) — Year 3
- Target: 5,000 paying customers at $20/mo avg = **$1.2M ARR**

### Target Segments
1. **Developers** (ICP 1): Solo devs / small teams wanting a private AI coding assistant
2. **Privacy-conscious SMBs** (ICP 2): Law firms, healthcare, finance needing on-prem AI
3. **AI enthusiasts** (ICP 3): Homelab operators who already run Ollama

---

## Product

### Current (v0.1 — MVP)
- Multi-model router (6 Ollama models)
- Alfred master orchestrator with HTTP API
- Chainlit web UI
- SQLite memory layer
- Specialized agents: law, business, media, money, security
- Watchdog self-healing system

### Roadmap
- **Q2 2026:** One-click installer, Docker image, GitHub Stars campaign
- **Q3 2026:** Managed cloud tier ($20/mo), Stripe integration
- **Q4 2026:** Team accounts, shared memory, API access
- **Q1 2027:** Mobile app, voice interface, plugin marketplace

---

## Revenue Model

| Tier | Price | Features |
|---|---|---|
| Free / Open Source | $0 | Self-hosted, community support |
| Pro | $20/mo | Hosted instance, 10GB memory, priority support |
| Team | $79/mo | 5 users, shared agents, admin dashboard |
| Enterprise | $299/mo | On-prem deploy, SSO, SLA, custom models |

**Additional revenue:**
- GitHub Sponsors (direct support): target $500/mo Y1
- Consulting / implementation: $150/hr
- Marketplace: 30% rev share on third-party agents

---

## Competitive Analysis

| Competitor | Weakness | Alii Advantage |
|---|---|---|
| AutoGPT | Unreliable, cloud-dependent | Local, self-healing, production-grade |
| LangChain | Framework, not product | Full product with UI and orchestration |
| CrewAI | No memory persistence | SQLite + episodic memory |
| Ollama | LLM server only | Full agent platform on top of Ollama |
| PrivateGPT | Single-model, limited agents | Multi-model routing + 10+ agents |

---

## Go-to-Market

### Phase 1 (Months 1–3): Community Building
- Open source release on GitHub
- HackerNews Show HN post
- r/selfhosted, r/LocalLLaMA posts
- Target: 500 GitHub stars, 50 Discord members

### Phase 2 (Months 4–6): Monetization
- Launch Pro tier with Stripe
- GitHub Sponsors
- Target: 50 paying customers, $1,000 MRR

### Phase 3 (Months 7–12): Scale
- Product Hunt launch
- Developer newsletter placements
- Content marketing (YouTube demos, blog)
- Target: 500 paying customers, $10,000 MRR

---

## Financial Projections (3-Year)

| Metric | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Customers | 150 | 1,200 | 5,000 |
| MRR (end of year) | $3,000 | $24,000 | $100,000 |
| ARR | $36,000 | $288,000 | $1,200,000 |
| Gross Margin | 85% | 87% | 89% |
| Burn Rate/mo | $5,000 | $15,000 | $30,000 |
| Break-Even | Month 18 | — | — |

---

## Team

- **Founder / CEO:** [Name] — Full-stack AI engineer, system architect
- **Advisors needed:** GTM advisor, legal counsel, CFO (part-time)

---

## Funding Ask

**Raising:** $250,000 on a SAFE note ($2M valuation cap, 20% discount)

**Use of funds:**
- Infrastructure & hosting: 20% ($50K)
- Marketing & community: 30% ($75K)
- Legal & compliance: 10% ($25K)
- Product development: 40% ($100K)

**Runway:** 18 months at $14K/mo burn

**Milestones this round achieves:**
- Product Hunt launch
- 1,000 GitHub stars
- 100 paying customers
- $3,000 MRR
- Series A ready metrics
"""
        path = BIZ_DIR / "business_plan.md"
        _write(path, content)
        _write_memory("business_agent", "Business plan generated.")
        return content

    # ── (b) Financial Model ───────────────────────────────────────────────────

    def financial_model(self) -> dict:
        log.info("financial_model")
        model = {
            "generated": datetime.now().isoformat(),
            "currency": "USD",
            "assumptions": {
                "avg_monthly_price": 20,
                "free_to_paid_conversion": 0.05,
                "monthly_churn": 0.03,
                "cac": 45,
                "ltv_months": 33,
                "gross_margin": 0.85,
                "monthly_burn_y1": 5000,
                "monthly_burn_y2": 15000,
                "monthly_burn_y3": 30000,
            },
            "projections": {
                "year_1": {
                    "q1": {"new_customers": 10, "mrr": 200, "burn": 15000, "net": -14800},
                    "q2": {"new_customers": 25, "mrr": 700, "burn": 15000, "net": -14300},
                    "q3": {"new_customers": 50, "mrr": 1700, "burn": 15000, "net": -13300},
                    "q4": {"new_customers": 65, "mrr": 3000, "burn": 15000, "net": -12000},
                    "annual": {"customers": 150, "arr": 36000, "burn": 60000, "loss": -24000},
                },
                "year_2": {
                    "q1": {"new_customers": 150, "mrr": 6000, "burn": 45000, "net": -39000},
                    "q2": {"new_customers": 250, "mrr": 11000, "burn": 45000, "net": -34000},
                    "q3": {"new_customers": 350, "mrr": 17000, "burn": 45000, "net": -28000},
                    "q4": {"new_customers": 450, "mrr": 24000, "burn": 45000, "net": -21000},
                    "annual": {"customers": 1200, "arr": 288000, "burn": 180000, "profit": 108000},
                },
                "year_3": {
                    "q1": {"new_customers": 600, "mrr": 36000, "burn": 90000, "net": -54000},
                    "q2": {"new_customers": 900, "mrr": 55000, "burn": 90000, "net": -35000},
                    "q3": {"new_customers": 1200, "mrr": 75000, "burn": 90000, "net": -15000},
                    "q4": {"new_customers": 1300, "mrr": 100000, "burn": 90000, "net": 10000},
                    "annual": {"customers": 5000, "arr": 1200000, "burn": 360000, "profit": 840000},
                },
            },
            "unit_economics": {
                "ltv": 660,
                "cac": 45,
                "ltv_cac_ratio": 14.7,
                "payback_months": 2.25,
                "gross_margin_pct": 85,
            },
            "break_even": {
                "month": 18,
                "mrr_required": 5000,
                "customers_required": 250,
            },
            "runway": {
                "seed_raise": 250000,
                "monthly_burn": 14000,
                "months": 17.8,
            },
        }
        path = BIZ_DIR / "financial_model.json"
        _write(path, json.dumps(model, indent=2))
        _write_memory("business_agent", "Financial model generated.")
        return model

    # ── (c) Funding Strategy ──────────────────────────────────────────────────

    def funding_strategy(self) -> str:
        log.info("funding_strategy")
        content = """# Alii AI — Funding Strategy & Roadmap

## Stage 0: Bootstrapping (Now — Month 6)

**Goal:** Reach $1,000 MRR with zero external capital

Actions:
- Open source release → GitHub stars → organic installs
- GitHub Sponsors ($5/$20/$99 tiers)
- Consulting revenue from local AI implementation projects
- Sell implementation services to small businesses

Target: 50 paying customers, $1K MRR, 500 GitHub stars

---

## Stage 1: Pre-Seed Angels (Month 4–8)

**Target raise:** $50,000–$150,000
**Instrument:** SAFE note, $1.5M cap, 20% discount
**Investors:** Angel investors, startup accelerators

How to find angels:
- Apply to Y Combinator (next batch: apply at ycombinator.com)
- Apply to Techstars (Columbus, Detroit cohorts)
- Network at Ohio Startup events (Columbus Startup Week, Rev1 Ventures)
- AngelList: https://www.angellist.com

What angels want to see:
- Working product (✓)
- Some traction (GitHub stars, first paying customers)
- Clear market (✓)
- Coachable founder

---

## Stage 2: Seed Round (Month 8–14)

**Target raise:** $250,000–$500,000
**Instrument:** SAFE note, $2M–$4M cap
**Investors:** Seed funds, super angels

Target metrics before raising:
- 100+ paying customers
- $3,000–$5,000 MRR
- 20% MoM growth rate
- Clear retention data (churn < 5%)

Ohio-friendly seed funds:
- Rev1 Ventures (Columbus, OH) — rev1ventures.com
- Flashstarts (Cleveland, OH)
- Drive Capital (Columbus, OH) — Series A but know angels

Remote seed funds open to non-SF:
- Backstage Capital
- Hustle Fund
- Calm Fund (bootstrapper-friendly)

---

## Stage 3: Series A (Month 18–30)

**Target raise:** $2M–$5M
**Instrument:** Priced equity (Preferred Stock)
**Target metrics:**
- $1M ARR run rate
- < 3% monthly churn
- Strong NPS (> 50)
- 3 enterprise customers

Before Series A:
- Convert Ohio LLC to Delaware C-Corp
- Hire experienced CFO (part-time OK)
- Get 409A valuation
- Board of directors (2 founder + 1 independent)
- Audited financials

---

## Non-Dilutive Options (Pursue Alongside All Stages)

| Source | Amount | How |
|---|---|---|
| SBIR/STTR grants | $150K–$2M | AI/tech research grants (NSF, DARPA) |
| Ohio TechCred | Up to $30K | Workforce training reimbursement |
| Rev1 Micro-Grant | $10K–$50K | Ohio startup program |
| Kickstarter | $10K–$100K | Community pre-sales |
| GitHub Sponsors | $500–$5K/mo | Developer community support |

---

## Investor Pitch Deck Outline (13 slides)

1. Cover: Alii AI — Your Private, Autonomous AI Platform
2. Problem: The privacy crisis in AI tools
3. Solution: Alii in 60 seconds (demo screenshot)
4. Product: Architecture + key features
5. Market: $8.2B TAM, 34% CAGR
6. Business model: Freemium → Pro → Enterprise
7. Traction: Stars, installs, early revenue
8. Competitive landscape: 2x2 matrix
9. Go-to-market: 3 phases
10. Financial projections: 3-year model
11. Team: Founder + advisors
12. The ask: $250K SAFE, use of funds
13. Vision: The private AI operating system for every company
"""
        path = BIZ_DIR / "funding_strategy.md"
        _write(path, content)
        _write_memory("business_agent", "Funding strategy generated.")
        return content

    # ── (d) Competitor Analysis ───────────────────────────────────────────────

    def competitor_analysis(self) -> str:
        log.info("competitor_analysis")
        content = """# Alii AI — Competitive Analysis
*Generated: """ + datetime.now().strftime("%Y-%m-%d") + """*

---

## Competitive Landscape Overview

The AI agent space is crowded but fragmented. Most solutions are either:
(a) cloud-dependent and expensive, or
(b) developer frameworks requiring significant setup

Alii occupies the **self-hosted, production-ready, privacy-first** niche.

---

## Top 10 Competitors

### 1. AutoGPT
- **What:** Pioneer autonomous AI agent, open source
- **Strengths:** Brand recognition, large community, GitHub stars (170K+)
- **Weaknesses:** Unreliable task completion, cloud-dependent by default, no production orchestration
- **Alii advantage:** Production-grade orchestration, self-healing, local-first

### 2. AgentGPT
- **What:** Web-based drag-and-drop agent builder
- **Strengths:** Easy to use, no-code
- **Weaknesses:** Cloud only, OpenAI API required, no privacy
- **Alii advantage:** Full local execution, no API costs

### 3. CrewAI
- **What:** Python framework for multi-agent systems
- **Strengths:** Elegant API, growing enterprise adoption
- **Weaknesses:** Framework not product, no UI, no memory persistence, cloud LLM required
- **Alii advantage:** Complete product with UI, SQLite memory, local LLM

### 4. LangChain / LangGraph
- **What:** Most popular LLM orchestration framework
- **Strengths:** Massive ecosystem, integrations, enterprise traction
- **Weaknesses:** Extremely complex, cloud-first, no self-healing, not a product
- **Alii advantage:** Out-of-box product experience, simpler architecture

### 5. Ollama (ollama.com)
- **What:** Local LLM server (Alii runs ON TOP of Ollama)
- **Strengths:** Best local LLM UX, 60K+ GitHub stars, large community
- **Weaknesses:** LLM server only, no agents, no memory, no UI
- **Alii advantage:** Alii is the agent layer + UI that Ollama users need
- **Partnership opportunity:** Deep Ollama integration, potential official plugin

### 6. PrivateGPT (zylon-ai/privateGPT)
- **What:** Private document Q&A with local LLMs
- **Strengths:** Privacy-focused, good SEO ranking
- **Weaknesses:** Document Q&A only, single model, no agents, no orchestration
- **Alii advantage:** Full agent platform vs. narrow document tool

### 7. Open WebUI (formerly Ollama WebUI)
- **What:** ChatGPT-like web UI for Ollama
- **Strengths:** Beautiful UI, massive adoption (30K+ stars)
- **Weaknesses:** Chat interface only, no agents, no automation, no orchestration
- **Alii advantage:** Agent platform vs. chat interface
- **Position:** Complementary — Alii can run alongside Open WebUI

### 8. AnythingLLM
- **What:** All-in-one local AI chat + document tool
- **Strengths:** Good UX, enterprise version, local execution
- **Weaknesses:** Chat/document focus, limited agent capability, no self-healing
- **Alii advantage:** Production orchestration, multi-agent framework

### 9. GPT4All
- **What:** Local LLM desktop app by Nomic AI
- **Strengths:** Easy install, desktop app, enterprise backing
- **Weaknesses:** Desktop app only, no server mode, no agents, no API
- **Alii advantage:** Server-grade, API-first, agent framework

### 10. Dify.ai
- **What:** Visual LLM application builder (open source + cloud)
- **Strengths:** Beautiful UI, workflows, strong enterprise traction
- **Weaknesses:** Primarily cloud, complex setup, less focus on privacy
- **Alii advantage:** Privacy-first, simpler, deeper agent autonomy

---

## Positioning Matrix

```
HIGH AUTONOMY
      │
      │    AutoGPT ●           ● Alii AI ← WE ARE HERE
      │                   (autonomous + local)
      │
      ├──────────────────────────────────────
CLOUD │                         │ LOCAL
      │                         │
      │  AgentGPT ●   Open WebUI ●
      │
      │
LOW AUTONOMY
```

---

## Alii's Defensible Moat

1. **Alfred orchestrator:** Production-grade self-healing no competitor has
2. **Multi-model routing with learning:** Unique performance optimization
3. **Integrated agent ecosystem:** Law + Business + Media + Security agents
4. **Open core + commercial:** Community flywheel drives enterprise leads
5. **Network effects:** More users → more agent templates → more valuable platform
"""
        path = BIZ_DIR / "competitor_analysis.md"
        _write(path, content)
        _write_memory("business_agent", "Competitor analysis generated.")
        return content

    # ── (e) Pricing Strategy ──────────────────────────────────────────────────

    def pricing_strategy(self) -> str:
        log.info("pricing_strategy")
        content = """# Alii AI — Pricing Strategy
*Generated: """ + datetime.now().strftime("%Y-%m-%d") + """*

---

## Pricing Philosophy

**Goal:** Maximize adoption (free tier) while capturing value from power users (Pro/Enterprise).
Use psychological pricing, anchoring, and freemium mechanics proven in developer tools.

---

## Recommended Pricing Tiers

### Free (Open Source Self-Hosted)
**Price:** $0 forever
**Target:** Developers, hobbyists, evaluators
**Features:**
- Full local installation
- All core agents (law, business, media, money, security)
- Alfred orchestrator
- Community support (GitHub Issues)
- Unlimited local usage

**Why free:** Drive GitHub stars, community contributions, word-of-mouth.
AGPL license prevents commercial forks without a paid license.

---

### Pro — $19/mo (billed monthly) | $15/mo (annual — save 21%)
**Target:** Individual professionals, freelancers, solo founders
**Features (everything in Free plus):**
- Hosted Alii instance (we manage the server)
- 25GB persistent memory
- Web UI at your-name.alii.ai subdomain
- Email support (48h response)
- Automated daily backups
- Priority model access (faster Ollama inference)

**Psychological pricing note:** $19 (not $20) — left-digit effect. Annual option anchors
value and increases LTV by 2x.

---

### Team — $79/mo (up to 5 users)
**Target:** Small teams, startups, consulting firms
**Per-seat beyond 5:** $15/user/month
**Features (everything in Pro plus):**
- 5 team members
- Shared memory and agent library
- Admin dashboard
- SSO (Google Workspace)
- Audit logs
- Slack notifications

**Psychological note:** $79 for 5 users = $15.80/seat — cheaper than Pro per-person,
encouraging upgrades.

---

### Enterprise — $299/mo (unlimited users, annual contract)
**Target:** Companies with compliance requirements (healthcare, legal, finance)
**Features (everything in Team plus):**
- On-premises deployment (your infrastructure)
- Custom LLM models
- SLA: 99.9% uptime guarantee
- Dedicated support Slack channel
- HIPAA Business Associate Agreement
- Custom agent development (2 hrs/mo)
- Annual security audit report

**Psychological note:** Annual contract creates predictable revenue.
Enterprise pricing anchors against the $20 tier — makes Pro feel affordable.

---

## Freemium Conversion Strategy

**Conversion triggers (prompt upgrade when user hits):**
- Memory storage > 1GB (Pro prompt)
- Running agents > 5 per day (Pro prompt)
- Adding a second team member (Team prompt)
- Requesting uptime SLA (Enterprise prompt)

**Free → Pro conversion target:** 5% (industry standard: 2–7%)
**Pro → Team upgrade trigger:** When user invites first collaborator

---

## Annual vs Monthly Incentive

| Plan | Monthly | Annual | Annual Savings |
|---|---|---|---|
| Pro | $19/mo | $180/yr ($15/mo) | Save $48 (21%) |
| Team | $79/mo | $756/yr ($63/mo) | Save $192 (20%) |
| Enterprise | Quoted | Annual only | Predictable cost |

---

## Competitive Price Benchmarking

| Product | Cheapest Paid Tier |
|---|---|
| ChatGPT Plus | $20/mo |
| Claude Pro | $20/mo |
| GitHub Copilot | $10/mo |
| **Alii Pro** | **$19/mo (local, private)** |
| AnythingLLM Cloud | $15/mo |
| Dify Cloud | $59/mo |

**Positioning:** Price parity with ChatGPT Plus but offers privacy + local compute.

---

## GitHub Sponsors Tiers (Community Support)

| Tier | Price | Benefit |
|---|---|---|
| Supporter | $5/mo | Name in README, Discord access |
| Contributor | $20/mo | Pro account free, priority issues |
| Patron | $99/mo | Enterprise features, direct Slack access |
| Corporate | $499/mo | Logo on README, 4hrs support/mo |
"""
        path = BIZ_DIR / "pricing_strategy.md"
        _write(path, content)
        _write_memory("business_agent", "Pricing strategy generated.")
        return content

    # ── (f) Daily Business Briefing ───────────────────────────────────────────

    def daily_business_briefing(self) -> str:
        log.info("daily_business_briefing")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        briefing = f"""=== Alii AI Business Briefing — {ts} ===

MRR        : $0 (pre-launch)
Customers  : 0 (pre-launch)
GitHub Stars: 0 (repo not yet public)
MoM Growth : N/A

MILESTONES THIS WEEK:
[ ] Open source release on GitHub
[ ] Write Show HN post
[ ] Set up GitHub Sponsors tiers
[ ] Create Stripe account

PRIORITY ACTIONS:
1. Push repo to GitHub (public)
2. Post on r/selfhosted and r/LocalLLaMA
3. Set up GitHub Sponsors
4. Write first blog post: "Building Alii: A Self-Hosted AI Agent Platform"

FINANCIALS:
- Burn: ~$0/mo (self-hosted, no cloud costs)
- Runway: Infinite (bootstrapped)
- Next milestone: First dollar of revenue

=== end briefing ===
"""
        log_path = LOG_DIR / "business_briefing.log"
        with open(log_path, "a") as fh:
            fh.write(briefing + "\n")
        _write_memory("business_agent", "Business briefing written.")
        log.info("Business briefing written to %s", log_path)
        return briefing

    # ── (g) Kickstarter Campaign ──────────────────────────────────────────────

    def kickstarter_campaign(self) -> str:
        log.info("kickstarter_campaign")
        content = """# Alii AI — Kickstarter Campaign
*Complete campaign content for launch*

---

## CAMPAIGN TITLE
**Alii: The Self-Hosted AI That Protects Your Privacy and Actually Works**

## TAGLINE
*Your own Alfred. Your own data. No subscriptions. No surveillance.*

## FUNDING GOAL: $10,000
## CAMPAIGN DURATION: 30 days

---

## SHORT DESCRIPTION (140 chars)
Alii is an open-source AI agent platform that runs entirely on your hardware. Private. Fast. Self-healing. No API fees.

---

## FULL STORY

### The Problem We're Solving

Every time you use ChatGPT, Claude, or Copilot, your ideas, your code, your business plans —
everything — gets sent to a corporation's server. You're not the customer. You're the product.

And you're paying for it. At $20/month, those API costs add up fast.

Meanwhile, incredible open-source AI models like Mistral, Qwen, and LLaMA sit on your hard
drive, capable of extraordinary things — but with no good way to use them in your daily workflow.

**We built Alii to fix this.**

---

### What Is Alii?

Alii is an autonomous AI agent platform that runs completely on your own hardware.

Think of it as your personal Alfred — a brilliant, tireless AI assistant that:
- 🧠 **Remembers everything** — persistent memory across all conversations
- ⚡ **Routes tasks to the right model** — fast models for quick questions, powerful models for complex tasks
- 🔧 **Fixes itself when things break** — Alfred, our orchestrator, restarts failed services automatically
- ⚖️ **Gives you AI legal counsel** — draft contracts, check compliance, understand regulations
- 💰 **Tracks your finances** — revenue analysis, pricing strategy, financial projections
- 🔒 **Guards your security** — monitors your system for threats, audits open ports
- 📣 **Manages your brand** — generates release notes, social content, and launch posts

**All of this. On your machine. Offline. Private. Free.**

---

### How It Works

```
You ask a question
     ↓
Alfred (our orchestrator) routes it to the best local AI model
     ↓
The model thinks on YOUR hardware using YOUR electricity
     ↓
The answer never leaves your machine
     ↓
Results saved to YOUR private memory database
```

Alii currently runs on any Linux machine with 8GB+ RAM. Mac and Windows support coming Q3 2026.

---

### What We've Built

In 3 months of nights and weekends, we've shipped:

✅ **Alfred** — master orchestrator with self-healing and HTTP control API
✅ **Multi-model router** — intelligently routes to the best Ollama model
✅ **6 AI agents** — law, business, media, money, security, social
✅ **Chainlit web UI** — real-time streaming chat
✅ **SQLite memory** — persistent, searchable conversation history
✅ **Watchdog** — automatic recovery when services crash
✅ **Systemd integration** — Alfred runs as a system service, always on

This isn't a prototype. It's running on a 12-core, 32GB production machine right now.

---

### Why Kickstarter?

Kickstarter lets us:
1. **Validate demand** before spending on infrastructure
2. **Fund the hosted tier** so non-technical users can try Alii without a Linux server
3. **Build the community** that will grow with us

We're not a VC-funded startup. We're a solo founder building in public, sharing everything.
Every dollar goes directly into making Alii better.

---

## REWARD TIERS

### 🌱 Seedling — $5
- Your name in the README Hall of Fame
- Discord access
- Our eternal gratitude

### ⭐ Star Gazer — $25 (Early Bird: first 100 backers)
- Everything in Seedling
- **1 year Pro account** (when launched, value: $228)
- Backer badge in the UI

### 🚀 Early Adopter — $49
- Everything in Star Gazer
- **Lifetime Pro account** (never pay again)
- Your feature request prioritized in roadmap

### 🔧 Builder — $99
- Everything in Early Adopter
- **1 year Team account** (5 users, value: $948)
- 30-min onboarding call with the founder

### 🏢 Enterprise Pioneer — $299
- Everything in Builder
- **Lifetime Enterprise license** (on-premises, value: $3,588/yr)
- Custom agent developed for your use case (2hrs)
- Your company logo on the website

### 💎 Founding Partner — $999 (limited to 10 backers)
- Everything in Enterprise Pioneer
- **Co-founder advisory role** — shape the product roadmap
- 1% revenue share for 12 months (via side letter)
- Monthly calls with the founding team

---

## FAQ

**Q: Does this require any cloud services?**
A: No. Alii runs 100% locally. The only internet connection needed is to download AI models once.

**Q: What hardware do I need?**
A: Minimum: 8GB RAM, modern CPU, Linux (Ubuntu 20.04+). Recommended: 16GB+ RAM, GPU optional.

**Q: What AI models does it use?**
A: Ollama-compatible models: Mistral, LLaMA 3, Qwen 2.5, Phi-3, and more. You choose.

**Q: Is my data private?**
A: Yes. Nothing leaves your machine. No telemetry by default.

**Q: When will the hosted tier launch?**
A: Q3 2026, funded by this campaign.

**Q: Is it open source?**
A: Yes. Core platform is AGPL-3.0 on GitHub. Commercial features have a separate license.

**Q: What if you don't reach your goal?**
A: The open-source version continues regardless. Kickstarter funds only the hosted cloud tier.

---

## RISKS AND CHALLENGES

Building AI infrastructure is hard. Here's what could go wrong and how we'll handle it:

1. **Ollama compatibility:** We stay in sync with Ollama releases. Risk: low — we control the integration layer.
2. **Hosting costs for cloud tier:** Mitigated by early pricing — we won't launch cloud until we have 50 paying customers to cover costs.
3. **Solo founder burnout:** Mitigated by selective scope — we ship less, better, more reliably.

---

## ABOUT THE CREATOR

I've been building AI systems for [X] years. Alii started as a personal tool to reclaim
privacy while still benefiting from AI. When it became genuinely useful — drafting my
LLC, analyzing my finances, auditing my server — I realized others needed this too.

I build in public. Follow the journey: github.com/your-username/alii

---

*Thank you for believing in private AI.*
"""
        path = BIZ_DIR / "kickstarter_campaign.md"
        _write(path, content)
        _write_memory("business_agent", "Kickstarter campaign content generated.")
        return content


    def daily_business_briefing(self) -> str:
        log.info("daily_business_briefing")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        briefing = (
            f"=== Alii AI Business Briefing — {ts} ===\n"
            f"MRR: $0 | Customers: 0 | Stars: 0 (pre-launch)\n"
            f"Actions: Push to GitHub, post Show HN, launch Sponsors\n"
            f"=== end ===\n"
        )
        log_path = LOG_DIR / "business_briefing.log"
        with open(log_path, "a") as fh:
            fh.write(briefing + "\n")
        _write_memory("business_agent", "Business briefing written.")
        return briefing
