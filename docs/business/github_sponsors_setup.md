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
