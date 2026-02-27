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
