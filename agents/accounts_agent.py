#!/usr/bin/env python3
"""
AccountsAgent — Secure account and credential manager for Alii AI.

SECURITY RULES (never violate):
- Credentials stored ONLY as Fernet-encrypted JSON in accounts/vault.json
- Master key stored ONLY in .env as VAULT_KEY (never in code, never in logs)
- Passwords NEVER logged, NEVER printed, NEVER sent over ntfy
- vault.json is listed in .gitignore — never committed
- In-memory decryption only — no plaintext ever written to disk
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.accounts_agent")

WORKDIR      = Path("/home/avalii/moltbot")
VAULT_FILE   = WORKDIR / "accounts" / "vault.json"
ACCOUNTS_DIR = WORKDIR / "accounts"
DOCS_DIR     = WORKDIR / "docs" / "accounts"
ENV_FILE     = WORKDIR / ".env"


def _load_env() -> dict:
    """Load .env as key=value dict."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _save_env_key(key: str, value: str):
    """Append or update a key in .env."""
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()

    new_line = f"{key}={value}"
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)

    ENV_FILE.write_text("\n".join(lines) + "\n")


def _get_fernet():
    """Return a Fernet instance using VAULT_KEY from environment or .env."""
    from cryptography.fernet import Fernet

    # Try os.environ first (set by parent process), then .env file
    vault_key = os.environ.get("VAULT_KEY") or _load_env().get("VAULT_KEY")
    if not vault_key:
        raise RuntimeError(
            "VAULT_KEY not found. Run setup_vault() first or set VAULT_KEY in .env"
        )
    return Fernet(vault_key.encode())


def _write_doc(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    log.info("Written: %s (%d bytes)", path, len(content))


class AccountsAgent:
    """
    Secure account and credential manager.
    All credentials encrypted with Fernet symmetric encryption.
    Master key lives ONLY in .env as VAULT_KEY.
    """

    def __init__(self):
        ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        log.info("AccountsAgent initialised.")

    # ── Vault Setup ───────────────────────────────────────────────────────────

    def setup_vault(self) -> dict:
        """
        Create encrypted vault. Generate VAULT_KEY if not already in .env.
        Safe to run multiple times (idempotent — won't overwrite existing key).
        Returns status dict (never returns the key itself).
        """
        from cryptography.fernet import Fernet

        env = _load_env()
        key_exists = "VAULT_KEY" in env or "VAULT_KEY" in os.environ

        if key_exists:
            log.info("setup_vault: VAULT_KEY already exists — skipping key generation.")
        else:
            new_key = Fernet.generate_key().decode()
            _save_env_key("VAULT_KEY", new_key)
            # Also set in current process environment
            os.environ["VAULT_KEY"] = new_key
            log.info("setup_vault: Generated new VAULT_KEY and saved to .env")

        # Create empty vault if it doesn't exist
        if not VAULT_FILE.exists():
            f = _get_fernet()
            empty = f.encrypt(json.dumps({}).encode()).decode()
            VAULT_FILE.write_text(json.dumps({"vault": empty, "version": 1}))
            log.info("setup_vault: Created empty vault at %s", VAULT_FILE)
        else:
            log.info("setup_vault: Vault already exists at %s", VAULT_FILE)

        return {
            "vault_path": str(VAULT_FILE),
            "key_generated": not key_exists,
            "vault_created": not VAULT_FILE.exists(),
            "status": "ready",
            "warning": "Keep .env safe. VAULT_KEY loss = permanent data loss.",
        }

    def _load_vault(self) -> dict:
        """Load and decrypt vault. Returns plaintext dict."""
        if not VAULT_FILE.exists():
            return {}
        f = _get_fernet()
        raw = json.loads(VAULT_FILE.read_text())
        return json.loads(f.decrypt(raw["vault"].encode()).decode())

    def _save_vault(self, data: dict):
        """Encrypt and save vault."""
        f = _get_fernet()
        encrypted = f.encrypt(json.dumps(data).encode()).decode()
        VAULT_FILE.write_text(json.dumps({"vault": encrypted, "version": 1}))

    # ── Credential Storage ────────────────────────────────────────────────────

    def store_account(
        self,
        service: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
    ) -> bool:
        """
        Encrypt and store an account credential in the vault.
        Password is never logged.
        """
        try:
            vault = self._load_vault()
            vault[service] = {
                "username": username,
                "password": password,   # encrypted at rest inside Fernet blob
                "url": url,
                "notes": notes,
                "stored_at": datetime.utcnow().isoformat() + "Z",
            }
            self._save_vault(vault)
            log.info("store_account: stored credentials for '%s' (username=%s)", service, username)
            return True
        except Exception as exc:
            log.error("store_account error for %s: %s", service, exc)
            return False

    def get_account(self, service: str) -> dict | None:
        """
        Decrypt and return account credentials for a service.
        Returns None if not found.
        SECURITY: Caller is responsible for not logging the returned password.
        """
        try:
            vault = self._load_vault()
            entry = vault.get(service)
            if entry is None:
                log.info("get_account: no entry found for '%s'", service)
            else:
                log.info("get_account: returning credentials for '%s'", service)
            return entry
        except Exception as exc:
            log.error("get_account error: %s", exc)
            return None

    def delete_account(self, service: str) -> bool:
        """Remove an account entry from the vault."""
        try:
            vault = self._load_vault()
            if service in vault:
                del vault[service]
                self._save_vault(vault)
                log.info("delete_account: removed '%s'", service)
                return True
            log.warning("delete_account: '%s' not found", service)
            return False
        except Exception as exc:
            log.error("delete_account error: %s", exc)
            return False

    # ── Account Guides ────────────────────────────────────────────────────────

    def create_github_account_guide(self) -> str:
        """Write docs/accounts/github_setup.md — exact steps for GitHub account creation."""
        content = """\
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
"""
        _write_doc(DOCS_DIR / "github_setup.md", content)
        return content

    def create_kofi_guide(self) -> str:
        """Write docs/accounts/kofi_setup.md — exact Ko-fi account creation steps."""
        content = """\
# Ko-fi Account Setup Guide — Alii AI
*Free. 0% fees on donations. Instant PayPal payout.*

---

## Step 1: Create Ko-fi Account (10 minutes)

1. Go to: https://ko-fi.com
2. Click "Sign up for free"
3. Email: Use your dedicated Alii business email
4. Username: `alii_ai` (check availability)
   - This becomes your URL: ko-fi.com/alii_ai
5. Store credentials:
   ```python
   agent.store_account("kofi", "alii_ai", "your-password",
                        "https://ko-fi.com/alii_ai", "Ko-fi donation page")
   ```

## Step 2: Connect PayPal (REQUIRED for payouts)

1. Ko-fi Dashboard → Settings → Payment
2. Connect PayPal:
   - You need a PayPal account (free at paypal.com)
   - PayPal personal account is fine — no business account needed yet
   - Use: pierre@youremail.com (or dedicated Alii email)
3. Alternatively: Connect Stripe (2-day payout vs PayPal's instant)

### PayPal Setup (if you don't have one)
1. Go to: https://www.paypal.com/us/digital-wallet/send-receive-money/request-money
2. Sign up with your Alii email
3. Verify email (check inbox)
4. Add bank account for withdrawal (ACH transfer, free, 1-3 days)

## Step 3: Configure Your Ko-fi Page

### Profile Settings

**Display name:** Alii AI
**Category:** Technology

**About (copy-paste):**
```
I'm building Alii — an open-source AI agent platform that runs entirely
on your own hardware. No subscriptions. No data sent to corporations.
Your AI, your rules.

Every coffee funds:
• Keeping the repo maintained and updated
• Building new agents (law, business, media, security)
• Testing on more hardware configurations

Thank you for supporting private AI. ☕
```

**Profile image:** Use Alii logo (create a simple "A" logo on Canva — free)

**Social links:**
- GitHub: github.com/your-username/alii
- Twitter/X: @alii_ai (create this too)

## Step 4: Set Donation Amount Options

Settings → Payments → Donation/payment amounts:
- Default amount: $5
- Suggested amounts: $3, $5, $10, $25

## Step 5: Create a Goal (optional but converts better)

Goals appear on your page as a progress bar:
- Goal: "Fund Ohio LLC formation ($99)"
- Description: "Help Alii become a real business"
- Amount: $99

After hitting that, new goal:
- Goal: "Server upgrade for faster model inference"
- Amount: $299

Goals create urgency and social proof.

## Step 6: Add Ko-fi Button to GitHub README

```markdown
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/alii_ai)
```

## Step 7: Test the Payment Flow

Before promoting, do a $1 test donation to yourself:
1. Open incognito window
2. Go to ko-fi.com/alii_ai
3. Click "Support"
4. Pay $1 via PayPal
5. Confirm it shows up in your Ko-fi dashboard
6. Confirm PayPal received it

---

## Ko-fi Gold (upgrade later at $6/mo — worth it above $50/mo income)

Unlocks:
- Monthly memberships
- Unlimited shop products
- Custom URL (ko-fi.com/alii instead of ko-fi.com/alii_ai)
- Discord integration
- 0% fee on shop sales (down from 5%)

Wait to upgrade until you're earning $50+/mo from Ko-fi. ROI is immediate then.
"""
        _write_doc(DOCS_DIR / "kofi_setup.md", content)
        return content

    def create_crypto_wallet_guide(self) -> str:
        """Write docs/accounts/crypto_setup.md — MetaMask (no ID) + Coinbase (needs ID)."""
        content = """\
# Crypto Wallet Setup Guide — Alii AI
*Accept crypto donations as an alternative payment method.*

---

## IMPORTANT: Two Options

| | MetaMask | Coinbase |
|---|---|---|
| ID required | NO | YES (government ID) |
| Setup time | 10 minutes | 1-3 days (verification) |
| Custody | Self-custody (you control keys) | Custodial (Coinbase holds funds) |
| Withdraw to bank | No (need to swap first) | YES (free ACH) |
| Accepts | ETH, ERC-20 tokens, any EVM chain | ETH, BTC, SOL, and 200+ coins |
| Cost | FREE | FREE |

**Recommendation:** Set up MetaMask TODAY (no ID needed, immediate). Set up
Coinbase when you have a government ID handy (needed for bank withdrawal).

---

## Option A: MetaMask — No ID, Set Up in 10 Minutes

### What is MetaMask?
MetaMask is a browser wallet. You hold your own private keys. No company can
freeze your account. Accepts ETH, USDC, MATIC, and thousands of other tokens.

### Setup Steps

1. Install MetaMask browser extension:
   - Chrome: https://metamask.io/download/
   - Firefox: https://metamask.io/download/
   - Click "Add to Chrome/Firefox"

2. Create new wallet:
   - Click "Create a new wallet"
   - Create a password (for this device only)
   - CRITICAL: Write down your 12-word seed phrase on paper
     - This is your ONLY recovery method
     - Anyone with this phrase controls your funds
     - Store it somewhere safe (NOT digitally, NOT in a photo)
     - Do NOT store it in the AccountsAgent vault (digital = risk)

3. Your Ethereum address will look like:
   `0x742d35Cc6634C0532925a3b844Bc454e4438f44e`

4. Share this address to receive ETH/USDC donations:
   - Add to README: "Crypto: `0x...YOUR_ADDRESS`"
   - Add to Ko-fi page in About section
   - Add to GitHub Sponsors profile

### Add to README

```markdown
## Crypto Donations

**ETH / USDC / MATIC:** `0xYOUR_METAMASK_ADDRESS`

*Any EVM-compatible chain accepted. USDC preferred (stable value).*
```

### Accept USDC (Recommended Over ETH)

USDC is a stablecoin: 1 USDC = $1 USD always. Ask donors to send USDC
instead of ETH to avoid price volatility.

On Polygon network: gas fees are < $0.01 (vs $5-50 on Ethereum mainnet).
Tell donors: "Send USDC on Polygon for near-zero fees"

### Convert to USD (requires Coinbase or exchange)

To convert to actual dollars:
1. Send from MetaMask → Coinbase account (once you have one)
2. Sell on Coinbase → withdraw to bank
3. Alternative: Use Uniswap to swap USDC → then off-ramp via Coinbase

---

## Option B: Coinbase — Requires Government ID

### What You Need
- Government-issued ID (passport or driver's license)
- Social Security Number (for US tax reporting)
- Phone number for 2FA

### ⚠️ FLAGGED FOR PIERRE ⚠️

This step requires YOU to complete manually — Alii cannot upload your ID.

Steps when ready:
1. Go to: https://coinbase.com
2. Sign up with Alii business email
3. Complete identity verification:
   - Upload driver's license or passport
   - Take selfie for facial verification
   - Wait 1-3 business days for approval
4. Connect bank account (routing + account number)
5. Free ACH withdrawal: 1-3 business days

### Coinbase Advantages Over MetaMask
- Direct USD withdrawal to bank (no middle step)
- BTC acceptance (larger donor pool)
- Better for recurring donations
- Tax reporting (1099 form) — important for IRS

### Store Coinbase credentials (when created):
```python
agent.store_account("coinbase", "your-email@alii.ai", "your-password",
                     "https://coinbase.com", "Coinbase exchange account for Alii crypto donations")
```

---

## Tax Note on Crypto

- Crypto received as donations: taxable as ordinary income at fair market value on receipt date
- Crypto held and then sold: capital gains tax (long-term if held > 1 year)
- Keep records: date received, amount in USD at time of receipt
- Coinbase provides tax forms (1099-MISC) automatically
- MetaMask does NOT provide tax forms — use Koinly.io (free tier available) for tracking

---

## Which Coins to Accept (Recommended)

| Priority | Coin | Why |
|----------|------|-----|
| 1 | USDC (Polygon) | Stable value, nearly free fees |
| 2 | ETH | Most common, everyone has it |
| 3 | BTC | Largest donor pool, some prefer BTC |
| 4 | SOL | Fast, cheap, growing ecosystem |

---

## Quick Start (Today, No ID)

1. Install MetaMask → 10 minutes → get your address
2. Add address to README, Ko-fi, GitHub profile
3. Post in HN/Reddit comments: "Also accepting USDC at 0x..."

That's it. You can receive crypto in the next 30 minutes.
"""
        _write_doc(DOCS_DIR / "crypto_setup.md", content)
        return content

    def create_upwork_guide(self) -> str:
        """Write docs/accounts/upwork_setup.md — Upwork profile for AI consulting."""
        content = """\
# Upwork Profile Setup — AI Agent Consulting
*Use skills you already have. First client possible within 7 days.*

---

## Step 1: Create Upwork Account (15 minutes)

1. Go to: https://www.upwork.com
2. Click "Sign up as a freelancer"
3. Email: Alii business email
4. Name: Your real name (Upwork requires real identity)
5. Store credentials:
   ```python
   agent.store_account("upwork", "your-email", "your-password",
                        "https://www.upwork.com", "Upwork freelancing account")
   ```

## Step 2: Identity Verification (REQUIRED — needs your ID)

⚠️ FLAGGED FOR PIERRE: Upwork requires identity verification (driver's license
or passport) before you can send proposals. Complete this manually.

After account creation:
1. Settings → Trust & Safety → Identity Verification
2. Upload ID photo
3. Approval: Usually within 24 hours

## Step 3: Build Your Profile

### Title (120 chars max):
```
AI Agent Developer | Private LLM Systems | Ollama | Python | Linux Automation
```

### Professional Overview (copy-paste, customize):
```
I build private, self-hosted AI systems that run on your own infrastructure.
No ongoing API costs. No data sent to third parties. Full control.

What I specialize in:
━━━━━━━━━━━━━━━━━━━━
🤖 Autonomous AI agents (Python + asyncio)
🧠 Local LLM deployment (Ollama, LLaMA, Mistral, Qwen, Phi)
⚙️ AI workflow orchestration and self-healing systems
💬 Custom chatbots with persistent memory (SQLite/PostgreSQL)
🔒 Private AI for compliance-sensitive industries
🐧 Linux server setup, hardening, and systemd services
🐍 Python/FastAPI/aiohttp backends

Recent work:
Built "Alfred" — a production AI orchestrator managing 10+ autonomous
agents for law, business, media, security, and finance. Running 24/7
with self-healing on a 12-core Linux workstation.

I communicate clearly, deliver on time, and build systems that actually
work in production — not just demos.

Ready to start immediately. Let's talk.
```

### Skills (add all):
Python, Artificial Intelligence, Machine Learning, Natural Language Processing,
Linux, API Development, Automation, Ollama, LangChain, FastAPI, Docker,
SQLite, Bash Scripting, Chatbot Development, LLM, Prompt Engineering,
System Administration, aiohttp, asyncio

### Hourly Rate:
- Start: $45/hr (competitive, will get hired faster)
- After 3 reviews: $75/hr
- After 5-star rating established: $125/hr

### Profile Photo:
Use a professional headshot. No logo — Upwork requires a real person photo.
LinkedIn-style photo works well.

## Step 4: Set Up Fixed-Price Services (Project Catalog)

Upwork Project Catalog lets clients buy without posting a job:

### Catalog Item 1: AI Chatbot Setup — $199

**Title:** I will deploy a private AI chatbot on your Linux server

**Category:** AI & Machine Learning > Chatbot Development

**Description:**
```
Get a fully private AI chatbot running on YOUR server in 2-3 days.
No OpenAI subscription. No API fees. No data leaving your network.

What's included:
✅ Ollama installed and configured (2 AI models: fast + smart)
✅ Chainlit or Open WebUI interface
✅ Running as a systemd service (always on, auto-restart)
✅ 14-day post-delivery support
✅ Basic documentation

Requirements: Linux server (Ubuntu 20.04+), 8GB+ RAM, SSH access
Delivery: 2-3 business days
```

### Catalog Item 2: Full AI Agent Platform — $399

**Title:** I will set up the complete Alii AI agent platform on your server

**Description:**
```
A full autonomous AI agent platform on your hardware:

✅ Alfred orchestrator (self-healing, HTTP API)
✅ Multi-model router (routes to best model automatically)
✅ 3 custom agents for your use case
✅ Web UI at your domain/IP
✅ Persistent memory (SQLite)
✅ 30-day support

Use cases: business automation, document analysis, customer service,
internal knowledge base, security monitoring

Requirements: Linux, 16GB+ RAM, SSH access
Delivery: 5-7 business days
```

## Step 5: First Proposals Strategy

**Day 1-3: Apply to 5 jobs per day**

Search for:
- "AI chatbot" (sort by: newest)
- "Ollama" (sort by: newest)
- "local LLM"
- "private ChatGPT"
- "Python automation"
- "AI agent"

**Proposal Template (customize per job):**
```
Hi [Name],

I read your post carefully. [One sentence about their specific need].

I recently built exactly this: a self-hosted AI agent system running on
Linux with [relevant feature they need]. It handles [their use case] using
Ollama + Python.

I can deliver [their specific ask] in [realistic time]. My approach:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Fixed price: $[amount] | Timeline: [X] days

I'm happy to share screenshots of similar work and jump on a quick
10-minute call to confirm I understand your needs before you commit.

[Your name]
```

**Key rules for proposals:**
- NEVER use a generic template — always reference their specific job
- Keep it under 200 words — clients skim
- Include a question (shows genuine interest, prompts reply)
- Send within 1 hour of job posting (early proposals get 3x more views)

## Step 6: Getting First Review (Critical)

Your first review is everything on Upwork. To get it:

1. **Accept any reasonable job** for your first 3 — even if underpaying
2. Over-deliver: Add something extra they didn't ask for
3. After delivery: "If you're happy with the work, a review would mean
   the world to me as I'm just building my Upwork profile"
4. Leave them a 5-star review first — they'll almost always reciprocate

---

## Payment Processing

Upwork holds payment for 5 days after client approves work (fraud protection).
After 5 days: withdraw via:
- Direct to US bank (ACH): FREE, 3-5 business days
- Instant pay to debit card: 1% fee, instant
- PayPal: 2% fee

---

## Upwork Connects (the bidding currency)

- New accounts get 80 free connects
- Each proposal costs 2-16 connects depending on job budget
- Buy more at $0.15/connect if you run out
- Budget $5-10/month on connects to keep bidding

---

## 30-Day Income Target

| Week | Goal | Target Income |
|------|------|--------------|
| 1 | Profile setup + 25 proposals sent | $0 (building) |
| 2 | First job won + delivered | $149-299 |
| 3 | Second job + first review | $299-399 |
| 4 | Third job (higher rate with reviews) | $299-499 |
| **Month 1 total** | | **$747-1,197** |
"""
        _write_doc(DOCS_DIR / "upwork_setup.md", content)
        return content

    # ── Status Report ─────────────────────────────────────────────────────────

    def accounts_status_report(self) -> dict:
        """
        List all stored account services (names only, no passwords) and
        which standard accounts still need to be created.
        """
        # Accounts we know Alii needs
        needed_accounts = [
            "github_personal",
            "github_org",
            "kofi",
            "paypal",
            "upwork",
            "fiverr",
            "replit",
            "producthunt",
            "coinbase",
            "polar",
            "twitter_alii",
            "reddit_alii",
            "linkedin_alii",
            "stripe",
            "anthropic_api",
        ]

        # Load what's in the vault (names only)
        stored = []
        try:
            vault = self._load_vault()
            stored = list(vault.keys())
        except RuntimeError:
            log.warning("accounts_status_report: vault not set up yet (run setup_vault())")
        except Exception as exc:
            log.warning("accounts_status_report: vault read error: %s", exc)

        missing = [a for a in needed_accounts if a not in stored]

        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stored_accounts": stored,           # names only, NO passwords
            "accounts_needed": needed_accounts,
            "missing": missing,
            "completion_pct": round(
                len([a for a in needed_accounts if a in stored]) / len(needed_accounts) * 100
            ),
            "docs_written": [str(p.name) for p in DOCS_DIR.glob("*.md")],
        }

        log.info(
            "accounts_status_report: %d stored, %d missing, %d%% complete",
            len(stored), len(missing), report["completion_pct"]
        )

        # Write report to disk (no credentials)
        report_path = WORKDIR / "logs" / "accounts_status.log"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))

        return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    agent = AccountsAgent()

    print("\n=== setup_vault() ===")
    r = agent.setup_vault()
    print(f"  Status: {r['status']}")
    print(f"  Key generated: {r['key_generated']}")
    print(f"  Vault: {r['vault_path']}")

    print("\n=== create_github_account_guide() ===")
    agent.create_github_account_guide()
    print("  docs/accounts/github_setup.md written")

    print("\n=== create_kofi_guide() ===")
    agent.create_kofi_guide()
    print("  docs/accounts/kofi_setup.md written")

    print("\n=== create_crypto_wallet_guide() ===")
    agent.create_crypto_wallet_guide()
    print("  docs/accounts/crypto_setup.md written")

    print("\n=== create_upwork_guide() ===")
    agent.create_upwork_guide()
    print("  docs/accounts/upwork_setup.md written")

    print("\n=== accounts_status_report() ===")
    status = agent.accounts_status_report()
    print(f"  Stored accounts : {status['stored_accounts'] or '(none yet)'}")
    print(f"  Missing         : {status['missing']}")
    print(f"  Completion      : {status['completion_pct']}%")
    print(f"  Docs written    : {status['docs_written']}")
    print("\n=== DONE ===")
