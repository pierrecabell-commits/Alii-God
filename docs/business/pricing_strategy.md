# Alii AI — Pricing Strategy
*Generated: 2026-02-27*

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
