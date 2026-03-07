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
