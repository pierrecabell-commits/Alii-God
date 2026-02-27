# Alii AI — Business Plan
*February 2026 | Confidential*

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
