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
