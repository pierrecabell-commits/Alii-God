# Intellectual Property Protection Strategy — Alii AI
*Generated: 2026-02-27*

---

## 1. IP Ownership Baseline

All IP created by founders before and during the company is owned by {"Alii AI LLC"} upon
execution of an IP Assignment Agreement (see section 5). All future contractor and employee
work product must be assigned via written agreement before work begins.

---

## 2. Copyright

- All source code is automatically protected by copyright upon creation (no registration required).
- Register key works with the U.S. Copyright Office (~$65) for ability to sue for statutory damages.
- Use SPDX license headers in all source files.
- Copyright notice: © 2026 Alii AI LLC. All rights reserved.

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
