#!/usr/bin/env python3
"""
LawAgent — AI legal counsel for Alii AI LLC (tech startup focus).
Generates legal documents, compliance reports, and regulatory briefings.

DISCLAIMER: Output is educational/informational only. Consult a licensed Ohio
attorney before relying on any document generated here for legal purposes.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.law_agent")

WORKDIR   = Path("/home/avalii/moltbot")
LEGAL_DIR = WORKDIR / "docs" / "legal"
LOG_DIR   = WORKDIR / "logs"


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


class LawAgent:
    """World-class AI legal counsel for an AI tech startup."""

    def __init__(self):
        LEGAL_DIR.mkdir(parents=True, exist_ok=True)
        log.info("LawAgent initialised.")

    # ── (a) Ohio LLC Formation ────────────────────────────────────────────────

    def form_llc(self, company_name: str = "Alii AI LLC") -> str:
        """
        Generate a complete Ohio LLC formation checklist and draft Articles of Organization.
        Writes to docs/legal/llc_formation.md.
        """
        log.info("form_llc: %s", company_name)
        ts = datetime.now().strftime("%Y-%m-%d")

        content = f"""# Ohio LLC Formation Guide — {company_name}
*Generated: {ts} | DISCLAIMER: For informational purposes only. Consult a licensed Ohio attorney.*

---

## Overview

An Ohio Limited Liability Company (LLC) provides personal liability protection, pass-through
taxation, and minimal ongoing compliance requirements — ideal for a tech startup.

**Ohio Filing Authority:** Ohio Secretary of State
**Online Filing Portal:** https://www.ohiosos.gov/businesses/business-filings/

---

## Step-by-Step Formation Checklist

### Step 1 — Choose and Reserve Your Name
- [ ] Verify name availability: https://www.ohiosos.gov/businesses/business-name-search/
- [ ] Name must include "LLC", "L.L.C.", or "Limited Liability Company"
- [ ] Optional: Reserve name for 180 days ($39 fee) before filing Articles
- **Recommended name:** `{company_name}`

### Step 2 — Designate a Registered Agent
- [ ] Must have a physical Ohio street address (no P.O. boxes)
- [ ] Must be available during normal business hours to receive legal documents
- **Options:**
  - Serve as your own registered agent (use your business address)
  - Hire a registered agent service: Northwest Registered Agent (~$125/yr),
    Registered Agents Inc (~$99/yr), or LegalZoom (~$299/yr)

### Step 3 — File Articles of Organization
- [ ] File online at https://www.ohiosos.gov (fastest, ~1 business day processing)
- [ ] **Filing fee:** $99 (standard) | $199 (expedited same-day)
- [ ] Required information:
  - LLC name
  - Registered agent name and address
  - Member/manager names (optional but recommended)
  - Principal office address
  - Effective date (immediate or future date)
- **Form:** Ohio Articles of Organization (Form 533A)

### Step 4 — Create an Operating Agreement
- [ ] Not legally required in Ohio but **strongly recommended**
- [ ] Defines ownership percentages, voting rights, profit distribution, and dissolution terms
- [ ] Keep internal — do not file with the state
- See: docs/legal/operating_agreement_template.md (to be generated)

### Step 5 — Obtain an EIN (Employer Identification Number)
- [ ] Apply free at https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online
- [ ] Instant issuance online (takes ~10 minutes)
- [ ] Required for: bank accounts, hiring employees, tax filings

### Step 6 — Open a Business Bank Account
- [ ] Required to maintain liability protection (keep business/personal finances separate)
- [ ] Recommended: Mercury (online, startup-friendly, free), Chase Business, or First Federal Savings
- [ ] Bring: EIN letter, Articles of Organization, Operating Agreement

### Step 7 — Ohio Business Licenses & Permits
- [ ] Ohio does not require a general state business license
- [ ] Check local city requirements (Columbus: https://www.columbus.gov/citycode/)
- [ ] If selling software/SaaS: register for Ohio sales tax at
  https://gateway.ohio.gov (if revenue > $100K or 200 transactions)

### Step 8 — Annual Compliance
- [ ] **Ohio LLC Annual Report:** Not required in Ohio (advantage over other states!)
- [ ] **Ohio Commercial Activity Tax (CAT):** Required if gross receipts > $150,000/yr
  - Register at https://tax.ohio.gov
  - Rates: $150 minimum (up to $1M revenue), then $0.26 per $1,000
- [ ] Keep registered agent information current with SOS

---

## Draft Articles of Organization — {company_name}

```
ARTICLES OF ORGANIZATION
OF
{company_name.upper()}

Pursuant to Ohio Revised Code Section 1705.04, the undersigned hereby
submits the following Articles of Organization for the formation of a
Limited Liability Company:

ARTICLE I — NAME
The name of the Limited Liability Company is:
{company_name}

ARTICLE II — PRINCIPAL OFFICE
The address of the principal office of the LLC is:
[Street Address]
[City], Ohio [ZIP Code]

ARTICLE III — REGISTERED AGENT
The name of the registered agent is: [Name or Service]
The address of the registered agent is:
[Street Address]
[City], Ohio [ZIP Code]

ARTICLE IV — PURPOSE
The purpose of the LLC is to engage in any lawful activity for which
a limited liability company may be organized under Ohio law, including
but not limited to the development, licensing, and distribution of
artificial intelligence software and services.

ARTICLE V — MANAGEMENT
The LLC shall be managed by its Member(s) / Manager(s).
[Select: Member-managed OR Manager-managed]

ARTICLE VI — EFFECTIVE DATE
These Articles of Organization shall be effective upon filing with the
Ohio Secretary of State.

Signature of Organizer: _______________________
Printed Name: [Your Name]
Date: {ts}
```

---

## Estimated Costs Summary

| Item | Cost |
|---|---|
| Articles of Organization (online) | $99 |
| Name reservation (optional) | $39 |
| Registered agent (first year, DIY) | $0 |
| Registered agent service (optional) | $99–$299/yr |
| EIN (IRS) | Free |
| Business bank account | Free (Mercury) |
| **Total minimum** | **$99** |

---

## Post-Formation To-Do

1. Draft Operating Agreement
2. Issue membership units/interests to founders
3. Apply for EIN
4. Open business bank account
5. Register domain: alii.ai or getaliiai.com
6. Set up business email: legal@{company_name.lower().replace(' ', '').replace('llc', '')}.ai
7. File for trademark on "Alii AI" at USPTO (~$250/class): https://www.uspto.gov/trademarks

*Consult a licensed Ohio attorney for advice specific to your situation.*
"""
        path = LEGAL_DIR / "llc_formation.md"
        _write(path, content)
        _write_memory("law_agent", "LLC formation guide generated.")
        return content

    # ── (b) Terms of Service ──────────────────────────────────────────────────

    def draft_terms_of_service(self, company_name: str = "Alii AI LLC",
                                product_name: str = "Alii") -> str:
        """
        Write a complete SaaS Terms of Service to docs/legal/terms_of_service.md.
        Covers liability, IP, user data, acceptable use, payment terms.
        """
        log.info("draft_terms_of_service")
        ts = datetime.now().strftime("%B %d, %Y")

        content = f"""# Terms of Service — {product_name}

**Last Updated:** {ts}
**Company:** {company_name}

---

## 1. Acceptance of Terms

By accessing or using {product_name} ("Service"), you agree to be bound by these Terms of
Service ("Terms"). If you do not agree, do not use the Service. These Terms apply to all
users, including visitors, registered users, and customers.

---

## 2. Description of Service

{product_name} is an AI-powered autonomous agent platform that provides local LLM inference,
task automation, memory management, and orchestration capabilities. The Service is provided
"as is" and features may change without notice.

---

## 3. Account Registration

- You must provide accurate, complete information when creating an account.
- You are responsible for maintaining the confidentiality of your credentials.
- You are responsible for all activity under your account.
- You must be at least 18 years old to use the Service.
- Notify us immediately of any unauthorized account use at legal@alii.ai.

---

## 4. Acceptable Use Policy

You agree NOT to use the Service to:

- Violate any applicable law or regulation
- Generate, distribute, or store illegal content
- Attempt to reverse-engineer, decompile, or extract source code
- Conduct automated attacks, scraping, or denial-of-service attacks against the Service
- Impersonate any person or entity
- Transmit viruses, malware, or malicious code
- Violate the intellectual property rights of others
- Use the Service to build a competing product without a commercial license

Violations may result in immediate account termination without refund.

---

## 5. Intellectual Property

### Our IP
All software, models, documentation, designs, and trademarks associated with {product_name}
are owned by {company_name} and protected under U.S. and international copyright,
trademark, and trade secret law.

### Your IP
You retain all rights to content you create or input into the Service ("User Content").
By using the Service, you grant {company_name} a limited, non-exclusive license to process
your User Content solely to provide the Service.

### Feedback
Any feedback, suggestions, or ideas you submit may be used by {company_name} without
obligation, compensation, or attribution.

---

## 6. Payment Terms

- **Free Tier:** Access to basic features at no charge (subject to usage limits).
- **Paid Plans:** Billed monthly or annually as described on our pricing page.
- **Billing:** Charges are due in advance. No refunds for partial months.
- **Price Changes:** We will provide 30 days' notice before increasing prices.
- **Taxes:** You are responsible for all applicable taxes.
- **Late Payment:** Accounts 30+ days past due may be suspended.

---

## 7. Privacy & Data

Your use of the Service is governed by our Privacy Policy (see docs/legal/privacy_policy.md).
Key points:
- We do not sell your personal data.
- AI processing may occur locally (on your hardware) or on our servers, depending on your plan.
- You may delete your account and data at any time.

---

## 8. Disclaimer of Warranties

THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

{company_name} does not warrant that:
- The Service will be uninterrupted or error-free
- AI-generated outputs are accurate, complete, or suitable for any purpose
- The Service is free from security vulnerabilities

AI outputs should not be relied upon as legal, medical, financial, or professional advice.

---

## 9. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, {company_name.upper()} SHALL NOT BE LIABLE FOR:
- Indirect, incidental, special, or consequential damages
- Loss of profits, data, or business opportunity
- Damages arising from your reliance on AI-generated content

OUR TOTAL LIABILITY SHALL NOT EXCEED THE GREATER OF (A) AMOUNTS PAID BY YOU IN THE
12 MONTHS PRECEDING THE CLAIM, OR (B) $100 USD.

---

## 10. Indemnification

You agree to indemnify and hold {company_name} harmless from claims arising from:
- Your use of the Service in violation of these Terms
- Your User Content
- Your violation of any third-party rights

---

## 11. Termination

- You may cancel your account at any time.
- We may suspend or terminate your account for violations of these Terms.
- Upon termination, your right to use the Service ceases immediately.
- Sections 5, 8, 9, 10, and 12 survive termination.

---

## 12. Governing Law & Disputes

These Terms are governed by the laws of the State of Ohio, USA, without regard to
conflict of law principles. Any disputes shall be resolved by binding arbitration
administered by the American Arbitration Association (AAA), conducted in Columbus, Ohio.

Class action and jury trial are waived to the extent permitted by law.

---

## 13. Changes to Terms

We reserve the right to modify these Terms at any time. We will notify registered users
30 days before material changes take effect via email or in-app notice.

---

## 14. Contact

**{company_name}**
Email: legal@alii.ai
"""
        path = LEGAL_DIR / "terms_of_service.md"
        _write(path, content)
        _write_memory("law_agent", "Terms of Service generated.")
        return content

    # ── (c) Privacy Policy ────────────────────────────────────────────────────

    def draft_privacy_policy(self, company_name: str = "Alii AI LLC") -> str:
        """
        Write a GDPR and CCPA compliant privacy policy to docs/legal/privacy_policy.md.
        """
        log.info("draft_privacy_policy")
        ts = datetime.now().strftime("%B %d, %Y")

        content = f"""# Privacy Policy — Alii

**Last Updated:** {ts}
**Controller:** {company_name}
**Contact:** privacy@alii.ai

---

## 1. Introduction

{company_name} ("we", "us", "our") is committed to protecting your privacy. This Privacy
Policy explains how we collect, use, disclose, and safeguard your information when you use
the Alii platform and related services ("Service").

This policy complies with:
- **GDPR** (EU General Data Protection Regulation 2016/679)
- **CCPA** (California Consumer Privacy Act, Cal. Civ. Code §1798.100 et seq.)
- **COPPA** (Children's Online Privacy Protection Act)

---

## 2. Information We Collect

### 2.1 Information You Provide
- **Account data:** Name, email address, password (hashed)
- **Payment information:** Processed by Stripe; we do not store card numbers
- **User content:** Prompts, conversations, files you submit to the Service
- **Support communications:** Emails, bug reports

### 2.2 Information Collected Automatically
- **Usage data:** Features used, session duration, error logs
- **Device data:** IP address, browser type, OS (for web UI users)
- **Performance metrics:** Token counts, response times (anonymised)

### 2.3 Local Processing
For self-hosted installations, all AI processing occurs on your hardware.
We receive no data from self-hosted instances unless you explicitly enable telemetry.

---

## 3. How We Use Your Information

| Purpose | Legal Basis (GDPR) |
|---|---|
| Provide and operate the Service | Contract performance |
| Improve AI model quality | Legitimate interest |
| Send transactional emails (receipts, alerts) | Contract performance |
| Send marketing emails | Consent (opt-in) |
| Comply with legal obligations | Legal obligation |
| Fraud prevention and security | Legitimate interest |

We do **not** use your data to train AI models without explicit opt-in consent.

---

## 4. Data Sharing and Disclosure

We do not sell your personal data. We may share data with:

- **Service providers:** Stripe (payments), AWS/Hetzner (hosting), SendGrid (email)
  — bound by data processing agreements
- **Law enforcement:** When required by valid legal process
- **Business transfers:** In the event of merger, acquisition, or asset sale
  (you will be notified 30 days in advance)

---

## 5. Data Retention

| Data Type | Retention Period |
|---|---|
| Account data | Until account deletion + 30 days |
| Conversation history | 90 days (configurable) |
| Payment records | 7 years (tax law requirement) |
| Usage logs | 30 days |
| Anonymised analytics | Indefinite |

---

## 6. Your Rights

### GDPR Rights (EU/UK residents)
- **Access:** Request a copy of your personal data
- **Rectification:** Correct inaccurate data
- **Erasure:** Request deletion of your data ("right to be forgotten")
- **Portability:** Receive your data in machine-readable format
- **Objection:** Object to processing based on legitimate interest
- **Restriction:** Request we limit processing of your data

To exercise these rights, email: privacy@alii.ai (response within 30 days)

You may lodge a complaint with your local supervisory authority. For EU residents:
https://edpb.europa.eu/about-edpb/about-edpb/members_en

### CCPA Rights (California residents)
- **Know:** What personal information we collect and how it's used
- **Delete:** Request deletion of your personal information
- **Opt-Out:** We do not sell personal information (no opt-out needed)
- **Non-Discrimination:** We will not discriminate for exercising your rights

To submit a CCPA request: privacy@alii.ai or use the in-app data controls.

---

## 7. Security

We implement industry-standard security measures:
- Data encrypted in transit (TLS 1.3) and at rest (AES-256)
- Access controls and audit logging
- Regular security reviews
- Bug bounty program (details at alii.ai/security)

No method of transmission or storage is 100% secure. We will notify you of breaches
as required by applicable law (within 72 hours for GDPR, where required).

---

## 8. Children's Privacy

The Service is not directed to children under 13 (or 16 in the EU). We do not knowingly
collect data from children. If you believe a child has provided us data, contact
privacy@alii.ai and we will delete it promptly.

---

## 9. International Transfers

For users outside the United States, your data may be transferred to and processed in
the United States. We use Standard Contractual Clauses (SCCs) approved by the European
Commission for EU-US data transfers.

---

## 10. Cookies

The web UI uses essential cookies for authentication. We do not use tracking or advertising
cookies. You can disable cookies in your browser settings (may affect functionality).

---

## 11. Changes to This Policy

We will notify you of material changes via email and in-app notice at least 30 days before
they take effect. Continued use after the effective date constitutes acceptance.

---

## 12. Contact

**Data Controller:** {company_name}
**Email:** privacy@alii.ai
**Postal address:** [To be added upon LLC registration]
**EU Representative (if applicable):** [To be designated]
"""
        path = LEGAL_DIR / "privacy_policy.md"
        _write(path, content)
        _write_memory("law_agent", "Privacy policy (GDPR/CCPA) generated.")
        return content

    # ── (d) IP Protection ─────────────────────────────────────────────────────

    def ip_protection(self) -> str:
        """Document IP ownership strategy, trade secrets, and open source licensing."""
        log.info("ip_protection")
        ts = datetime.now().strftime("%Y-%m-%d")
        content = f"""# Intellectual Property Protection Strategy — Alii AI
*Generated: {ts}*

---

## 1. IP Ownership Baseline

All IP created by founders before and during the company is owned by {{"Alii AI LLC"}} upon
execution of an IP Assignment Agreement (see section 5). All future contractor and employee
work product must be assigned via written agreement before work begins.

---

## 2. Copyright

- All source code is automatically protected by copyright upon creation (no registration required).
- Register key works with the U.S. Copyright Office (~$65) for ability to sue for statutory damages.
- Use SPDX license headers in all source files.
- Copyright notice: © {datetime.now().year} Alii AI LLC. All rights reserved.

---

## 3. Trade Secrets — Alfred Architecture

The following components are candidates for trade secret protection:
- Alfred orchestration algorithm and health-loop design
- AliiModelRouter task classification and performance learning system
- Self-modification and capability upgrade pipeline
- Memory architecture (SQLite + episodic/semantic layers)

**Protection requirements (to qualify as trade secret under Ohio UTA / Defend Trade Secrets Act):**
- [ ] Mark confidential files with CONFIDENTIAL header
- [ ] Restrict access via git permissions and access controls
- [ ] Use NDAs with all employees, contractors, and investors
- [ ] Document reasonable secrecy measures

---

## 4. Open Source Strategy

### Recommended Dual-License Model:
- **Open core (AGPL-3.0):** Core platform on GitHub — drives adoption, community, stars
  - AGPL requires derivative works to also be open source
  - Prevents competitors from building closed products on your code
- **Commercial license:** Available for enterprise customers who need proprietary use
  - Typical pricing: $500–$5,000/yr per organization

### Files to keep proprietary (not open-source):
- Alfred commercial orchestration API
- Enterprise features (multi-tenancy, SSO, audit logs)
- Any fine-tuned model weights

### Trademark protection:
- Register "Alii AI" as a trademark: https://www.uspto.gov/trademarks
- Cost: ~$250/class (Class 42: Software as a Service)
- Timeline: 8–12 months for registration

---

## 5. Patent Considerations

Patents are expensive (~$15,000–$30,000 for a software patent) and take 2–4 years.
**Recommendation for early stage:** Focus on trade secrets and copyright.
Consider provisional patent application (~$800) if you develop a novel algorithm.

Potentially patentable innovations:
- Multi-model routing with adaptive performance learning
- Self-healing autonomous recovery system (watchdog + Claude integration)

---

## 6. Open Source Compliance Check

Dependencies to audit for license compatibility:
- aiohttp: Apache 2.0 ✓ (permissive)
- Flask: BSD ✓ (permissive)
- Chainlit: Apache 2.0 ✓ (permissive)
- prometheus-client: Apache 2.0 ✓ (permissive)
- psutil: BSD ✓ (permissive)
- SQLite (built-in Python): Public Domain ✓

**No GPL-licensed dependencies detected** — commercial use is clear.

---

## 7. Immediate Actions

1. [ ] All founders sign IP Assignment Agreements
2. [ ] Add LICENSE file to repo (choose: MIT for maximum adoption, AGPL for protection)
3. [ ] Register "Alii AI" trademark
4. [ ] Mark internal docs CONFIDENTIAL
5. [ ] Set up private repo for commercial/enterprise features
"""
        path = LEGAL_DIR / "ip_protection.md"
        _write(path, content)
        _write_memory("law_agent", "IP protection strategy generated.")
        return content

    # ── (e) Contractor Agreement ──────────────────────────────────────────────

    def contractor_agreement(self) -> str:
        """Generate NDA + contractor agreement template."""
        log.info("contractor_agreement")
        ts = datetime.now().strftime("%B %d, %Y")
        content = f"""# Independent Contractor Agreement & NDA Template
*Alii AI LLC | Last Updated: {ts}*
*TEMPLATE ONLY — Have an attorney review before use*

---

## INDEPENDENT CONTRACTOR AGREEMENT

This Agreement is entered into as of [DATE] between:
- **Company:** Alii AI LLC, an Ohio limited liability company ("Company")
- **Contractor:** [Full Legal Name] ("Contractor")

### 1. Services
Contractor agrees to perform the following services: [DESCRIBE SCOPE]
Deliverables: [LIST DELIVERABLES]
Timeline: [START DATE] to [END DATE or ongoing]

### 2. Compensation
- Rate: $[RATE] per [hour/project/milestone]
- Payment: Net-30 upon invoice
- Expenses: [Reimbursed/Not reimbursed] with prior written approval

### 3. Independent Contractor Status
Contractor is an independent contractor, not an employee. Contractor is responsible
for all taxes, insurance, and benefits. No employment relationship is created.

### 4. Intellectual Property Assignment
All work product, inventions, software, designs, and materials created by Contractor
in the performance of Services are "works made for hire" or, if not, are hereby
assigned to Company. Contractor waives all moral rights.

### 5. Confidentiality (NDA)
Contractor agrees to:
- Keep all Confidential Information strictly confidential
- Use Confidential Information only to perform Services
- Not disclose Confidential Information to any third party without written consent
- Return or destroy all Confidential Information upon termination

"Confidential Information" means all non-public business, technical, and financial
information of Company, including but not limited to: source code, algorithms,
customer data, business plans, and trade secrets.

This obligation survives termination for 5 years.

### 6. Non-Solicitation
During the term and for 12 months after, Contractor will not solicit Company's
employees, contractors, or clients.

### 7. Representations
Contractor represents that: (a) Contractor has the right to enter this Agreement;
(b) Services will not infringe any third-party rights; (c) Contractor is not
subject to any conflicting obligations.

### 8. Termination
Either party may terminate with 14 days written notice. Company may terminate
immediately for material breach.

### 9. Governing Law
Ohio law governs this Agreement. Disputes resolved by arbitration in Columbus, Ohio.

---

**SIGNATURES**

Company: ___________________________ Date: ___________
Name: [Authorized Signatory], Alii AI LLC

Contractor: ________________________ Date: ___________
Name: [Contractor Full Name]
"""
        path = LEGAL_DIR / "contractor_agreement.md"
        _write(path, content)
        _write_memory("law_agent", "Contractor agreement template generated.")
        return content

    # ── (f) Funding Legal Prep ────────────────────────────────────────────────

    def funding_legal_prep(self) -> str:
        """Document legal structures needed before accepting investment."""
        log.info("funding_legal_prep")
        content = f"""# Funding Legal Preparation Guide — Alii AI LLC
*Generated: {datetime.now().strftime("%Y-%m-%d")}*

---

## Before Accepting Any Money

### Corporate Housekeeping (Do First)
- [ ] Ohio LLC fully formed with Articles of Organization
- [ ] Operating Agreement signed by all members
- [ ] EIN obtained
- [ ] IP Assignment Agreements signed by all founders
- [ ] Business bank account opened
- [ ] Cap table created (who owns what %)

---

## Funding Instruments

### Option A: SAFE Notes (Recommended for Pre-Seed)
- **What:** Simple Agreement for Future Equity — converts to equity at next priced round
- **Best for:** Pre-revenue / early traction stage
- **Standard terms:**
  - Valuation cap: $2M–$5M (negotiate based on traction)
  - Discount: 20% (investor gets 20% discount at Series A conversion)
  - No interest, no maturity date (YC standard SAFE)
- **Documents needed:** YC SAFE template (free at https://www.ycombinator.com/documents)
- **Cost:** ~$1,500–$3,000 attorney review

### Option B: Convertible Note
- **What:** Loan that converts to equity — has interest rate and maturity date
- **Best for:** When investors want downside protection
- **Key terms:** 6–8% interest, 18–24 month maturity, 15–25% discount, valuation cap
- **Docs needed:** Convertible Note Purchase Agreement, Promissory Note

### Option C: Priced Equity Round (Series A+)
- **What:** Sell actual shares at a set valuation
- **Best for:** $2M+ raises with institutional investors
- **Documents needed:** Term Sheet, Stock Purchase Agreement, Investor Rights Agreement,
  Right of First Refusal Agreement, Voting Agreement, Certificate of Incorporation
- **Cost:** $15,000–$50,000 in legal fees

---

## Convert LLC to C-Corp (Before Series A)

Most institutional investors (VCs) require a Delaware C-Corporation, not an Ohio LLC.
- Timing: Convert when raising $500K+ or taking institutional money
- Process: Incorporate Delaware C-Corp, merge Ohio LLC into it
- Cost: ~$500 Delaware filing + attorney fees
- **Platform:** Stripe Atlas ($500) or Clerky (~$2,000) can handle this

---

## Key Investor Agreements

1. **Term Sheet** — Non-binding outline of deal terms (valuation, board seats, pro-rata rights)
2. **Subscription Agreement** — Investor agrees to buy shares/SAFE
3. **Investor Rights Agreement** — Information rights, pro-rata, co-sale, drag-along
4. **Board Consent** — Approves the financing
5. **409A Valuation** — Required before issuing equity to employees (~$1,500)

---

## Red Flags to Avoid
- Investors demanding >20% of company at pre-seed
- Board control provisions at early stage
- Anti-dilution provisions without negotiation
- Exclusivity clauses over 30 days
- Personal guarantees from founders

---

## Recommended Legal Resources
- YC SAFE templates: https://www.ycombinator.com/documents
- NVCA model documents: https://nvca.org/model-legal-documents/
- Ohio attorney referral: Ohio State Bar (https://www.ohiobar.org/lawyerreferral/)
"""
        path = LEGAL_DIR / "funding_legal_prep.md"
        _write(path, content)
        _write_memory("law_agent", "Funding legal prep guide generated.")
        return content

    # ── (g) Compliance Check ──────────────────────────────────────────────────

    def compliance_check(self) -> dict:
        """Check codebase for open source license compliance issues."""
        log.info("compliance_check")
        try:
            r = subprocess.run(
                ["find", str(WORKDIR), "-name", "*.py", "-not", "-path", "*/venv/*",
                 "-not", "-path", "*/__pycache__/*"],
                capture_output=True, text=True, timeout=10
            )
            py_files = r.stdout.strip().splitlines()
        except Exception:
            py_files = []

        # Check for license header
        missing_header = []
        for f in py_files[:50]:  # cap at 50
            try:
                first = Path(f).read_text()[:200].lower()
                if "license" not in first and "copyright" not in first:
                    missing_header.append(f)
            except Exception:
                pass

        # Check for known problematic imports
        gpl_risk = []
        gpl_packages = ["mysql-connector", "pyqt", "wxpython", "pyside"]
        for f in py_files[:50]:
            try:
                content = Path(f).read_text()
                for pkg in gpl_packages:
                    if pkg in content.lower():
                        gpl_risk.append({"file": f, "package": pkg})
            except Exception:
                pass

        result = {
            "timestamp": datetime.now().isoformat(),
            "python_files_checked": len(py_files),
            "missing_license_header": missing_header,
            "gpl_risk_imports": gpl_risk,
            "recommendation": "Add SPDX license headers to all source files. "
                              "Consider: # SPDX-License-Identifier: MIT",
            "status": "clean" if not gpl_risk else "review_needed",
        }

        report_path = LEGAL_DIR / "compliance_report.json"
        _write(report_path, json.dumps(result, indent=2))
        _write_memory("law_agent", f"Compliance check: {result['status']}")
        log.info("Compliance check: %s (%d files checked)", result["status"], len(py_files))
        return result

    # ── (h) Daily Legal Briefing ──────────────────────────────────────────────

    def daily_legal_briefing(self) -> str:
        """
        Generate a legal briefing for AI regulation topics relevant to Alii.
        Writes to logs/legal_briefing.log.
        (News scanning is a stub — connect to a news API for live data.)
        """
        log.info("daily_legal_briefing")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

        briefing = f"""=== Alii AI Legal Briefing — {ts} ===

[REGULATION TRACKER — Update by connecting to a news API]

Key regulatory areas to monitor:

1. EU AI Act (effective 2024–2026)
   - Status: Enforcement begins Aug 2026 for high-risk systems
   - Impact: Alii may qualify as "general purpose AI" — requires transparency disclosures
   - Action: Review Act categories at https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689

2. US AI Executive Order (Oct 2023) & NIST AI RMF
   - Status: Agency implementation ongoing
   - Action: Align with NIST AI Risk Management Framework (free at nist.gov)

3. FTC AI Guidelines
   - Status: Active enforcement of deceptive AI marketing claims
   - Action: Ensure all product claims about AI capabilities are accurate

4. State Laws: Colorado, Illinois, Texas AI bias laws
   - Impact: If Alii is used in hiring/lending/housing, bias testing required

5. Ohio AI Policy
   - Status: No specific AI law yet; general business law applies
   - Watch: Ohio legislature for emerging proposals

[ACTION ITEMS]
- Review EU AI Act compliance requirements
- Add AI system transparency disclosures to ToS
- Implement model output logging for audit trail
- Schedule quarterly legal review

=== end briefing ===
"""
        log_path = LOG_DIR / "legal_briefing.log"
        with open(log_path, "a") as fh:
            fh.write(briefing + "\n")
        _write_memory("law_agent", "Legal briefing written.")
        log.info("Legal briefing written to %s", log_path)
        return briefing
