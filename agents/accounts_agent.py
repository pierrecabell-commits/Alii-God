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

import hashlib
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("alii.accounts_agent")

WORKDIR      = Path("/home/avalii/moltbot")
VAULT_FILE   = WORKDIR / "accounts" / "vault.json"
ACCOUNTS_DIR = WORKDIR / "accounts"
DOCS_DIR     = WORKDIR / "docs" / "accounts"
ENV_FILE     = WORKDIR / ".env"

# Global lock — prevents race conditions when multiple callers hit the vault concurrently
_VAULT_LOCK = threading.Lock()


def _load_env() -> dict:
    """Load .env as key=value dict."""
    env = {}
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
        except OSError as e:
            log.warning("_load_env: could not read .env: %s", e)
    return env


def _save_env_key(key: str, value: str):
    """Append or update a key in .env — atomic write prevents corruption."""
    lines = []
    if ENV_FILE.exists():
        try:
            lines = ENV_FILE.read_text().splitlines()
        except OSError as e:
            log.warning("_save_env_key: could not read .env: %s", e)

    new_line = f"{key}={value}"
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)

    content = "\n".join(lines) + "\n"
    # Atomic write: write to tmp then rename so a crash mid-write never corrupts .env
    # NOTE: ENV_FILE is ".env" (no extension), so use parent dir for tmp to avoid
    # with_suffix(".env.tmp") producing the double-suffix ".env.env.tmp".
    tmp = ENV_FILE.parent / ".env.tmp"
    try:
        tmp.write_text(content)
        tmp.rename(ENV_FILE)
    except OSError as e:
        log.error("_save_env_key: failed to write .env: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _get_fernet():
    """Return a Fernet instance using VAULT_KEY from environment or .env."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "cryptography package not installed. Run: pip install cryptography"
        )

    vault_key = os.environ.get("VAULT_KEY") or _load_env().get("VAULT_KEY")
    if not vault_key:
        raise RuntimeError(
            "VAULT_KEY not found. Run setup_vault() first or set VAULT_KEY in .env"
        )
    return Fernet(vault_key.encode())


def _write_doc(path: Path, content: str):
    """Write doc file — creates parent dirs, logs result, handles disk errors."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        log.info("Written: %s (%d bytes)", path, len(content))
    except OSError as e:
        log.error("_write_doc: failed to write %s: %s", path, e)
        raise


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
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError(
                "cryptography package not installed. Run: pip install cryptography"
            )

        env = _load_env()
        key_exists = "VAULT_KEY" in env or "VAULT_KEY" in os.environ
        vault_existed = VAULT_FILE.exists()  # capture BEFORE any creation

        if key_exists:
            log.info("setup_vault: VAULT_KEY already exists — skipping key generation.")
        else:
            new_key = Fernet.generate_key().decode()
            _save_env_key("VAULT_KEY", new_key)
            os.environ["VAULT_KEY"] = new_key
            log.info("setup_vault: Generated new VAULT_KEY and saved to .env")

        with _VAULT_LOCK:
            if not vault_existed:
                f = _get_fernet()
                empty = f.encrypt(json.dumps({}).encode()).decode()
                VAULT_FILE.write_text(json.dumps({"vault": empty, "version": 1}))
                log.info("setup_vault: Created empty vault at %s", VAULT_FILE)
            else:
                log.info("setup_vault: Vault already exists at %s", VAULT_FILE)

        return {
            "vault_path":    str(VAULT_FILE),
            "key_generated": not key_exists,
            "vault_created": not vault_existed,   # BUG FIX: was evaluated after creation
            "status":        "ready",
            "warning":       "Keep .env safe. VAULT_KEY loss = permanent data loss.",
        }

    def _load_vault(self) -> dict:
        """Load and decrypt vault. Returns plaintext dict. Caller must hold _VAULT_LOCK."""
        if not VAULT_FILE.exists():
            return {}
        try:
            f = _get_fernet()
            raw = json.loads(VAULT_FILE.read_text())
            return json.loads(f.decrypt(raw["vault"].encode()).decode())
        except (OSError, json.JSONDecodeError) as e:
            log.error("_load_vault: file read/parse error: %s", e)
            raise
        except Exception as e:
            log.error("_load_vault: decryption error (wrong key?): %s", e)
            raise

    def _save_vault(self, data: dict):
        """Encrypt and save vault atomically. Caller must hold _VAULT_LOCK."""
        try:
            f = _get_fernet()
            encrypted = f.encrypt(json.dumps(data).encode()).decode()
            tmp = VAULT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps({"vault": encrypted, "version": 1}))
            tmp.rename(VAULT_FILE)
        except OSError as e:
            log.error("_save_vault: write failed: %s", e)
            raise

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
            with _VAULT_LOCK:
                vault = self._load_vault()
                existing = vault.get(service, {})
                vault[service] = {
                    "username": username,
                    "password": password,
                    "url":      url,
                    "notes":    notes,
                    # Preserve original stored_at if re-storing an existing service
                    "stored_at":  existing.get("stored_at", datetime.now(timezone.utc).isoformat()),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
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
            with _VAULT_LOCK:
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

    def update_account(self, service: str, **fields) -> bool:
        """
        Update specific fields of an existing vault entry without overwriting others.
        Never pass 'password' in kwargs if you want to keep the existing password.
        Returns False if service not found.
        """
        if not fields:
            return False
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
                if service not in vault:
                    log.warning("update_account: '%s' not found in vault", service)
                    return False
                vault[service].update(fields)
                vault[service]["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save_vault(vault)
            log.info("update_account: updated '%s' fields: %s", service,
                     [k for k in fields if k != "password"])
            return True
        except Exception as exc:
            log.error("update_account error for %s: %s", service, exc)
            return False

    def has_account(self, service: str) -> bool:
        """Return True if the service exists in the vault."""
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            return service in vault
        except Exception:
            return False

    def list_accounts(self) -> list:
        """Return list of stored service names (no credentials)."""
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            return sorted(vault.keys())
        except Exception as exc:
            log.error("list_accounts error: %s", exc)
            return []

    def delete_account(self, service: str) -> bool:
        """Remove an account entry from the vault."""
        try:
            with _VAULT_LOCK:
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

    def vault_key_fingerprint(self) -> str | None:
        """
        Return a SHA-256 fingerprint of the VAULT_KEY (safe to log/display —
        confirms which key is in use without exposing the key itself).
        Returns None if key is not set.
        """
        try:
            key = os.environ.get("VAULT_KEY") or _load_env().get("VAULT_KEY")
            if not key:
                return None
            digest = hashlib.sha256(key.encode()).hexdigest()[:16]
            return f"sha256:{digest}..."
        except Exception as exc:
            log.error("vault_key_fingerprint error: %s", exc)
            return None

    def rotate_key(self, new_key: str | None = None) -> dict:
        """
        Re-encrypt the entire vault with a new Fernet key.
        If new_key is None, a fresh key is generated automatically.
        Old key is replaced in .env. Returns fingerprint of new key.
        CAUTION: Back up .env before calling this.
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError(
                "cryptography package not installed. Run: pip install cryptography"
            )

        try:
            with _VAULT_LOCK:
                # Decrypt with current key
                vault = self._load_vault()

                # Generate or validate the new key
                if new_key is None:
                    new_key = Fernet.generate_key().decode()
                else:
                    # Validate it's a valid Fernet key before committing
                    Fernet(new_key.encode())

                # Re-encrypt with new key
                new_f = Fernet(new_key.encode())
                encrypted = new_f.encrypt(json.dumps(vault).encode()).decode()
                tmp = VAULT_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps({"vault": encrypted, "version": 1}))
                tmp.rename(VAULT_FILE)

                # Update in-memory env FIRST so the process can always decrypt
                # even if .env persistence fails below.
                os.environ["VAULT_KEY"] = new_key

                # Persist to .env — if this fails the process still works (os.environ
                # is correct); log a critical warning so Pierre can fix manually.
                try:
                    _save_env_key("VAULT_KEY", new_key)
                except OSError as env_err:
                    log.critical(
                        "rotate_key: vault re-encrypted with new key but .env write failed: %s. "
                        "os.environ is correct for this session but the new key will be LOST on "
                        "restart. Save VAULT_KEY manually immediately.", env_err
                    )

            digest = hashlib.sha256(new_key.encode()).hexdigest()[:16]
            fingerprint = f"sha256:{digest}..."
            log.info("rotate_key: vault re-encrypted with new key fingerprint %s", fingerprint)
            return {
                "ok":          True,
                "fingerprint": fingerprint,
                "entries":     len(vault),
                "warning":     "Update any process/service that depends on the old VAULT_KEY.",
            }
        except Exception as exc:
            log.error("rotate_key failed: %s", exc)
            return {"ok": False, "error": str(exc)}

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
        Appends a timestamped entry to the status log instead of overwriting it.
        """
        needed_accounts = [
            "github_personal", "github_org", "kofi", "paypal",
            "upwork", "fiverr", "replit", "producthunt", "coinbase",
            "polar", "twitter_alii", "reddit_alii", "linkedin_alii",
            "stripe", "anthropic_api",
        ]

        # list_accounts() catches all exceptions and returns [] — no need for try/except here
        stored = self.list_accounts()

        missing = [a for a in needed_accounts if a not in stored]
        completion_pct = round(
            len([a for a in needed_accounts if a in stored]) / len(needed_accounts) * 100
        )

        report = {
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "stored_accounts":  stored,
            "accounts_needed":  needed_accounts,
            "missing":          missing,
            "completion_pct":   completion_pct,
            "docs_written":     [str(p.name) for p in DOCS_DIR.glob("*.md")],
            "vault_fingerprint": self.vault_key_fingerprint(),
        }

        log.info(
            "accounts_status_report: %d stored, %d missing, %d%% complete",
            len(stored), len(missing), completion_pct,
        )

        # Append timestamped entry to log — never overwrite history
        log_path = WORKDIR / "logs" / "accounts_status.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(report) + "\n")
        except OSError as e:
            log.warning("accounts_status_report: could not write log: %s", e)

        return report


    # ── Vault Utilities ───────────────────────────────────────────────────────

    def vault_health_check(self) -> dict:
        """
        Verify the vault can be decrypted and return integrity stats.
        Safe to call anytime — never exposes credentials.
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            size = VAULT_FILE.stat().st_size if VAULT_FILE.exists() else 0
            return {
                "ok":             True,
                "entries":        len(vault),
                "fingerprint":    self.vault_key_fingerprint(),
                "vault_path":     str(VAULT_FILE),
                "vault_size_bytes": size,
            }
        except Exception as exc:
            log.error("vault_health_check failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def list_accounts_with_metadata(self) -> list:
        """
        Return service metadata (username, url, notes, timestamps) for all accounts.
        Passwords are never included.
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            return [
                {
                    "service":    service,
                    "username":   data.get("username", ""),
                    "url":        data.get("url", ""),
                    "notes":      data.get("notes", ""),
                    "stored_at":  data.get("stored_at", ""),
                    "updated_at": data.get("updated_at", ""),
                }
                for service, data in sorted(vault.items())
            ]
        except Exception as exc:
            log.error("list_accounts_with_metadata error: %s", exc)
            return []

    def search_accounts(self, query: str) -> list:
        """
        Case-insensitive search across service names, usernames, URLs, and notes.
        Returns a list of matching service names (no credentials).
        """
        q = query.lower()
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            matches = []
            for service, data in vault.items():
                haystack = " ".join([
                    service,
                    data.get("username", ""),
                    data.get("url", ""),
                    data.get("notes", ""),
                ]).lower()
                if q in haystack:
                    matches.append(service)
            return sorted(matches)
        except Exception as exc:
            log.error("search_accounts error: %s", exc)
            return []

    def vault_backup(self, backup_dir: str | None = None) -> dict:
        """
        Copy the encrypted vault file to a timestamped backup.
        Default backup location: accounts/backups/vault_<timestamp>.json.bak
        The backup is still encrypted — same VAULT_KEY required to restore.
        """
        dest_dir = Path(backup_dir) if backup_dir else ACCOUNTS_DIR / "backups"
        try:
            if not VAULT_FILE.exists():
                return {"ok": False, "error": "Vault file does not exist — run setup_vault() first"}
            dest_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = dest_dir / f"vault_{ts}.json.bak"
            shutil.copy2(VAULT_FILE, dest)
            log.info("vault_backup: backed up to %s", dest)
            return {"ok": True, "backup_path": str(dest)}
        except OSError as exc:
            log.error("vault_backup error: %s", exc)
            return {"ok": False, "error": str(exc)}


    def get_account_field(self, service: str, field: str) -> str | None:
        """
        Return a single field from a vault entry without exposing the full record.
        Field is never logged. Returns None if service or field not found.
        Common fields: 'username', 'url', 'notes', 'stored_at', 'updated_at'.
        To retrieve 'password', prefer inject_credentials() for silent injection.
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            entry = vault.get(service)
            if entry is None:
                log.info("get_account_field: '%s' not found in vault", service)
                return None
            value = entry.get(field)
            if field != "password":
                log.info("get_account_field: '%s'.%s retrieved", service, field)
            return value
        except Exception as exc:
            log.error("get_account_field error for %s.%s: %s", service, field, exc)
            return None

    def inject_credentials(self, service: str, env_dict: dict) -> bool:
        """
        Silently inject username and password for a service into an existing env dict
        (e.g., os.environ.copy() or subprocess env). Values are NEVER logged.
        Keys injected: <SERVICE_UPPER>_USERNAME, <SERVICE_UPPER>_PASSWORD.

        Usage:
            env = os.environ.copy()
            agent.inject_credentials("github_personal", env)
            subprocess.run(["my-script"], env=env)

        Returns True if credentials were found and injected, False otherwise.
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            entry = vault.get(service)
            if entry is None:
                log.warning("inject_credentials: '%s' not found in vault", service)
                return False
            prefix = service.upper().replace("-", "_").replace(".", "_").replace(" ", "_")
            env_dict[f"{prefix}_USERNAME"] = entry.get("username", "")
            env_dict[f"{prefix}_PASSWORD"] = entry.get("password", "")
            log.info("inject_credentials: '%s' injected into env (values not logged)", service)
            return True
        except Exception as exc:
            log.error("inject_credentials error for %s: %s", service, exc)
            return False

    def import_accounts(self, records: list[dict]) -> dict:
        """
        Bulk-import accounts from a list of dicts. Each dict must have at least
        'service' and 'username' keys; 'password', 'url', 'notes' are optional.
        Existing entries are updated (preserves stored_at). Returns summary.
        """
        ok, failed = [], []
        for rec in records:
            service = rec.get("service", "").strip()
            username = rec.get("username", "").strip()
            if not service or not username:
                failed.append({"record": rec, "reason": "missing service or username"})
                continue
            success = self.store_account(
                service=service,
                username=username,
                password=rec.get("password", ""),
                url=rec.get("url", ""),
                notes=rec.get("notes", ""),
            )
            (ok if success else failed).append(service)
        log.info("import_accounts: %d imported, %d failed", len(ok), len(failed))
        return {"imported": ok, "failed": failed}

    def vault_restore(self, backup_path: str) -> dict:
        """
        Restore vault from a backup file (must be encrypted with the current VAULT_KEY).
        The current vault is backed up first to prevent data loss.
        Returns status dict.
        """
        src = Path(backup_path)
        if not src.exists():
            return {"ok": False, "error": f"Backup file not found: {backup_path}"}
        try:
            # Verify the backup can actually be decrypted before touching current vault
            f = _get_fernet()
            raw = json.loads(src.read_text())
            test_data = json.loads(f.decrypt(raw["vault"].encode()).decode())
        except Exception as exc:
            return {"ok": False, "error": f"Cannot decrypt backup (wrong key or corrupt): {exc}"}

        try:
            with _VAULT_LOCK:
                # Back up current vault first
                pre_backup = None
                if VAULT_FILE.exists():
                    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    pre_backup = ACCOUNTS_DIR / "backups" / f"vault_pre_restore_{ts}.json.bak"
                    pre_backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(VAULT_FILE, pre_backup)

                shutil.copy2(src, VAULT_FILE)

            log.info(
                "vault_restore: restored from %s (%d entries). Pre-restore backup at %s",
                src, len(test_data), pre_backup,
            )
            return {
                "ok": True,
                "entries_restored": len(test_data),
                "source": str(src),
                "pre_restore_backup": str(pre_backup) if pre_backup else None,
            }
        except OSError as exc:
            log.error("vault_restore error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def prune_backups(self, keep_last_n: int = 10) -> dict:
        """
        Delete old vault backups, keeping only the most recent `keep_last_n` files.
        Operates on accounts/backups/ directory. Returns count of deleted files.
        """
        backup_dir = ACCOUNTS_DIR / "backups"
        if not backup_dir.exists():
            return {"ok": True, "deleted": 0, "kept": 0}
        try:
            backups = sorted(
                backup_dir.glob("vault_*.json.bak"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            to_delete = backups[keep_last_n:]
            for f in to_delete:
                f.unlink(missing_ok=True)
            log.info("prune_backups: deleted %d, kept %d", len(to_delete), min(len(backups), keep_last_n))
            return {"ok": True, "deleted": len(to_delete), "kept": min(len(backups), keep_last_n)}
        except OSError as exc:
            log.error("prune_backups error: %s", exc)
            return {"ok": False, "error": str(exc)}

    def create_all_guides(self) -> list[str]:
        """
        Write all account setup guides to docs/accounts/. Returns list of written paths.
        """
        written = []
        for method_name in [
            "create_github_account_guide",
            "create_kofi_guide",
            "create_crypto_wallet_guide",
            "create_upwork_guide",
        ]:
            try:
                getattr(self, method_name)()
                written.append(method_name)
            except Exception as exc:
                log.error("create_all_guides: %s failed: %s", method_name, exc)
        log.info("create_all_guides: wrote %d guides", len(written))
        return written

    # ── Safe Access Helpers ───────────────────────────────────────────────────

    def get_account_safe(self, service: str) -> dict | None:
        """
        Return vault entry for a service with password redacted.
        Safe for logging, display, or passing to untrusted callers.
        Returns None if service not found.
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            entry = vault.get(service)
            if entry is None:
                log.info("get_account_safe: '%s' not found", service)
                return None
            safe = {k: v for k, v in entry.items() if k != "password"}
            safe["password"] = "***REDACTED***"
            return safe
        except Exception as exc:
            log.error("get_account_safe error for %s: %s", service, exc)
            return None

    def rename_service(self, old_name: str, new_name: str) -> bool:
        """
        Rename a vault entry from old_name to new_name.
        Returns False if old_name not found or new_name already exists.
        """
        if not old_name or not new_name or old_name == new_name:
            return False
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
                if old_name not in vault:
                    log.warning("rename_service: '%s' not found", old_name)
                    return False
                if new_name in vault:
                    log.warning("rename_service: '%s' already exists", new_name)
                    return False
                vault[new_name] = vault.pop(old_name)
                vault[new_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save_vault(vault)
            log.info("rename_service: '%s' → '%s'", old_name, new_name)
            return True
        except Exception as exc:
            log.error("rename_service error: %s", exc)
            return False

    # ── Backup Management ─────────────────────────────────────────────────────

    def list_backups(self) -> list[dict]:
        """
        List available vault backups with metadata (name, size, mtime).
        Returns newest-first list of dicts.
        """
        backup_dir = ACCOUNTS_DIR / "backups"
        if not backup_dir.exists():
            return []
        try:
            backups = sorted(
                backup_dir.glob("vault_*.json.bak"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return [
                {
                    "name":     f.name,
                    "path":     str(f),
                    "size_bytes": f.stat().st_size,
                    "mtime":    datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
                for f in backups
            ]
        except OSError as exc:
            log.error("list_backups error: %s", exc)
            return []

    def auto_backup(self, max_age_days: int = 1) -> dict:
        """
        Create a vault backup only if no backup exists within the last max_age_days.
        Call this from periodic tasks to ensure a recent backup always exists.
        Returns a dict with 'skipped' (bool) and optional 'backup_path'.
        """
        import time
        backup_dir = ACCOUNTS_DIR / "backups"
        try:
            if backup_dir.exists():
                backups = sorted(
                    backup_dir.glob("vault_*.json.bak"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if backups:
                    age_secs = time.time() - backups[0].stat().st_mtime
                    if age_secs < max_age_days * 86400:
                        log.debug(
                            "auto_backup: skipped — last backup %.1fh ago",
                            age_secs / 3600,
                        )
                        return {"skipped": True, "last_backup": str(backups[0])}
        except OSError as exc:
            log.warning("auto_backup: could not inspect backups: %s", exc)

        result = self.vault_backup()
        result["skipped"] = False
        return result

    # ── Security Audit ────────────────────────────────────────────────────────

    def find_duplicate_passwords(self) -> dict:
        """
        Detect reused passwords across vault entries using SHA-256 hashes.
        Never logs or returns actual passwords — only service names and hash prefixes.
        Returns dict of hash_prefix → list of service names sharing that password.
        Only includes groups with 2+ entries (i.e., actual duplicates).
        """
        try:
            with _VAULT_LOCK:
                vault = self._load_vault()
            buckets: dict[str, list[str]] = {}
            for service, data in vault.items():
                pw = data.get("password", "")
                if not pw:
                    continue
                h = hashlib.sha256(pw.encode()).hexdigest()[:12]
                buckets.setdefault(h, []).append(service)
            duplicates = {h: svcs for h, svcs in buckets.items() if len(svcs) > 1}
            log.info(
                "find_duplicate_passwords: %d duplicate group(s) found across %d entries",
                len(duplicates), len(vault),
            )
            return duplicates
        except Exception as exc:
            log.error("find_duplicate_passwords error: %s", exc)
            return {}

    def vault_audit(self) -> dict:
        """
        Comprehensive security audit of the vault.
        Returns a structured report — no credentials are exposed.
        Covers: health, duplicates, empty passwords, missing fields, backup status.
        """
        health = self.vault_health_check()
        if not health["ok"]:
            return {"ok": False, "error": health.get("error")}

        try:
            with _VAULT_LOCK:
                vault = self._load_vault()

            empty_passwords = [s for s, d in vault.items() if not d.get("password")]
            missing_url = [s for s, d in vault.items() if not d.get("url")]
            duplicates = self.find_duplicate_passwords()
            backups = self.list_backups()

            report = {
                "ok":               True,
                "timestamp":        datetime.now(timezone.utc).isoformat(),
                "total_entries":    len(vault),
                "empty_passwords":  empty_passwords,
                "missing_url":      missing_url,
                "duplicate_groups": duplicates,
                "backup_count":     len(backups),
                "latest_backup":    backups[0]["mtime"] if backups else None,
                "vault_fingerprint": self.vault_key_fingerprint(),
                "recommendations":  [],
            }

            if empty_passwords:
                report["recommendations"].append(
                    f"Set passwords for: {', '.join(empty_passwords)}"
                )
            if duplicates:
                count = sum(len(v) for v in duplicates.values())
                report["recommendations"].append(
                    f"{count} accounts share passwords — consider unique passwords for each"
                )
            if not backups:
                report["recommendations"].append("No vault backups found — run vault_backup()")
            elif backups:
                import time
                age_days = (time.time() - (
                    datetime.fromisoformat(backups[0]["mtime"]).timestamp()
                )) / 86400
                if age_days > 7:
                    report["recommendations"].append(
                        f"Latest backup is {age_days:.0f} days old — run auto_backup()"
                    )

            log.info(
                "vault_audit: %d entries, %d empty passwords, %d duplicate groups, %d backups",
                len(vault), len(empty_passwords), len(duplicates), len(backups),
            )
            return report
        except Exception as exc:
            log.error("vault_audit error: %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Alfred Routing ────────────────────────────────────────────────────────

    def handle(self, text: str) -> str:
        """
        Natural-language dispatch for alfred.py routing.
        Handles simple intent keywords and returns a human-readable response.
        Never reveals passwords in responses.
        """
        t = text.lower().strip()

        if any(k in t for k in ("status", "report", "summary", "completion")):
            r = self.accounts_status_report()
            return (
                f"Accounts: {len(r['stored_accounts'])} stored, "
                f"{len(r['missing'])} missing, {r['completion_pct']}% complete. "
                f"Missing: {', '.join(r['missing'][:5]) or 'none'}."
            )

        if any(k in t for k in ("audit", "security check", "duplicate")):
            r = self.vault_audit()
            if not r["ok"]:
                return f"Vault audit failed: {r.get('error')}"
            recs = r["recommendations"]
            return (
                f"Vault audit: {r['total_entries']} entries, "
                f"{len(r['duplicate_groups'])} duplicate password groups, "
                f"{r['backup_count']} backups. "
                + (f"Recommendations: {'; '.join(recs)}" if recs else "All clear.")
            )

        if any(k in t for k in ("health", "check vault", "vault ok")):
            r = self.vault_health_check()
            if r["ok"]:
                return f"Vault healthy: {r['entries']} entries, fingerprint {r['fingerprint']}"
            return f"Vault unhealthy: {r.get('error')}"

        if any(k in t for k in ("backup", "back up")):
            r = self.auto_backup()
            if r.get("skipped"):
                return f"Backup skipped — recent backup exists at {r['last_backup']}"
            if r.get("ok"):
                return f"Vault backed up to {r.get('backup_path')}"
            return f"Backup failed: {r.get('error')}"

        if any(k in t for k in ("list accounts", "show accounts", "what accounts")):
            accounts = self.list_accounts()
            if not accounts:
                return "No accounts stored in vault yet."
            return f"Stored accounts ({len(accounts)}): {', '.join(accounts)}"

        if any(k in t for k in ("list backups", "show backups")):
            backups = self.list_backups()
            if not backups:
                return "No vault backups found."
            return f"{len(backups)} backup(s). Latest: {backups[0]['name']} ({backups[0]['mtime'][:10]})"

        if "guide" in t or "setup" in t:
            written = self.create_all_guides()
            return f"Account setup guides written: {', '.join(written)}"

        return (
            "AccountsAgent ready. Commands: status, audit, health, backup, "
            "list accounts, list backups, guides."
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    agent = AccountsAgent()

    print("\n=== setup_vault() ===")
    r = agent.setup_vault()
    print(f"  Status: {r['status']}")
    print(f"  Key generated: {r['key_generated']}")
    print(f"  Vault created: {r['vault_created']}")
    print(f"  Vault: {r['vault_path']}")
    print(f"  Fingerprint: {agent.vault_key_fingerprint()}")

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
