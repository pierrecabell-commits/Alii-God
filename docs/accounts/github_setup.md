# GitHub Account Setup Guide — Alii AI
*Create github.com account for alii-ai organization. Free.*

---

## Step 1: Create Personal Account (5 minutes)

1. Go to: https://github.com/signup
2. Email: Use a dedicated email for Alii business (e.g., pierre+alii@yourdomain.com)
   - Do NOT use your personal email — keeps business separate
   - Gmail alias trick: your+alii@gmail.com works perfectly
3. Username: `alii-pierre` or `pierre-alii` (keep it professional)
4. Password: Use a strong unique password, store via AccountsAgent:
   ```python
   agent.store_account("github_personal", "your-username", "your-password",
                        "https://github.com", "Personal GitHub account for Alii dev")
   ```

## Step 2: Secure the Account (10 minutes — DO NOT SKIP)

### Enable Two-Factor Authentication (mandatory)
1. Settings → Password and authentication → Two-factor authentication
2. Choose: Authenticator app (Google Authenticator, Authy, or 1Password)
3. Save the recovery codes in your vault:
   ```python
   agent.store_account("github_2fa_recovery", "your-username",
                        "recovery-codes-here", "https://github.com",
                        "GitHub 2FA recovery codes")
   ```

### Add SSH Key
1. On your Precision workstation:
   ```bash
   cat ~/.ssh/id_rsa.pub
   ```
2. GitHub → Settings → SSH and GPG keys → New SSH key
3. Title: "aliirecision" | Key type: Authentication
4. Paste the public key

### Add Signing Key (for verified commits)
Same public key, Key type: Signing
Then configure git:
```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_rsa.pub
git config --global commit.gpgsign true
```

## Step 3: Create the Alii Organization

1. GitHub → Your profile (top right) → Your organizations → New organization
2. Name: `alii-ai` (or `alii-platform`)
3. Plan: FREE (free for public repos, up to 3 private repos)
4. Contact email: Same dedicated Alii email
5. Organization type: My personal account (skip "company" for now)

## Step 4: Push the Alii Repo

```bash
# From /home/avalii/moltbot:
gh auth login  # follow prompts
gh repo create alii-ai/alii --public --source=. --push --description "Private, self-hosted AI agent platform"
```

OR push to personal account first:
```bash
gh repo create alii --public --source=. --push
```

## Step 5: Optimize the Repository

### Add Repository Topics (boosts discoverability)
Settings → General → Topics → add:
```
ai, agents, ollama, local-llm, python, self-hosted, privacy, automation,
llm, langchain, autonomous-agents, alfred, open-source
```

### Add Repository Description
```
Alii: A self-hosted autonomous AI agent platform. Multi-model routing,
self-healing orchestration, and persistent memory — all on your hardware.
```

### Add Website URL
Leave blank until you have a domain. Come back and add it when ready.

## Step 6: Apply for GitHub Sponsors

1. Go to: https://github.com/sponsors/dashboard
2. Click "Get started"
3. Select: Individual (not organization — easier to set up)
4. Country: United States
5. Payment: Connect Stripe or PayPal
6. Payout method: Direct bank transfer or PayPal
7. Submit — approval takes 1-5 business days

## Step 7: Add FUNDING.yml

Create `.github/FUNDING.yml` in your repo:
```yaml
github: YOUR_PERSONAL_USERNAME
ko_fi: YOUR_KOFI_USERNAME
polar: YOUR_POLAR_USERNAME
```

This adds a "Sponsor" button to your repo immediately.

---

## Security Checklist

- [ ] 2FA enabled with authenticator app
- [ ] Recovery codes stored in vault
- [ ] SSH key added and tested
- [ ] Personal email NOT used (use Alii-dedicated email)
- [ ] Recovery codes NOT stored in plain text anywhere

---

## GitHub Free Plan Limits

| Feature | Free |
|---------|------|
| Public repos | Unlimited |
| Private repos | Unlimited (3 collaborators) |
| GitHub Actions | 2,000 min/month |
| GitHub Packages | 500MB |
| GitHub Pages | YES (free hosting!) |
| Sponsors | YES (0% fee first 2 years) |

GitHub Pages is free hosting for a static website. Use it for alii-ai.github.io
as your project website until you buy a domain.
