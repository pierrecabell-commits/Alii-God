#!/usr/bin/env python3
"""
Alii Revenue Tracker — autonomous multi-stream revenue monitoring and opportunity scanning.

Revenue streams monitored:
  - GitHub Sponsors (via GitHub API)
  - Ko-fi (via webhook ingestion)
  - Gumroad (via Gumroad API)
  - Stripe (via Stripe API — SaaS subscriptions)
  - GitHub Stars (growth indicator)

Opportunity scanning:
  - Upwork/Freelancer: search AI/automation gigs
  - Reddit: monitor relevant threads for engagement opportunities

Runs every INTERVAL seconds, aggregates into revenue.db, sends ntfy reports.
"""

import os, sys, json, sqlite3, time, logging, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKDIR   = Path("/home/avalii/moltbot")
LOG_FILE  = WORKDIR / "logs" / "revenue_tracker.log"
DB_PATH   = WORKDIR / "data" / "revenue.db"
NTFY_URL  = "https://ntfy.sh/alii-precision"
INTERVAL  = 3600   # 1 hour revenue check
REPORT_HOUR = 21   # 9 PM daily ntfy report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [revenue] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.revenue")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _ntfy(title: str, msg: str, priority: str = "default", tags: str = ""):
    try:
        headers = {"Title": title, "Priority": priority}
        if tags:
            headers["Tags"] = tags
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(), headers=headers, method="POST"
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        log.warning("ntfy failed: %s", e)


def _api_get(url: str, headers: dict = None, timeout: int = 10) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.debug("HTTP %d for %s", e.code, url)
        return None
    except Exception as e:
        log.debug("API error %s: %s", url, e)
        return None


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


# ── Revenue Collectors ─────────────────────────────────────────────────────────

def check_github_stars() -> dict:
    """Monitor GitHub stars as growth metric."""
    token = _env("GITHUB_TOKEN")
    if not token:
        return {"error": "no GITHUB_TOKEN"}

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    repos = ["Alii-God", "Alii-Core", "Alii-Authentic-Intelligence-Public"]
    total_stars = 0
    details = {}

    for repo in repos:
        data = _api_get(f"https://api.github.com/repos/pierrecabell-commits/{repo}", headers=headers)
        if data:
            stars = data.get("stargazers_count", 0)
            total_stars += stars
            details[repo] = stars

    return {"total_stars": total_stars, "by_repo": details}


def check_stripe_revenue() -> dict:
    """Check Stripe for recent payments."""
    stripe_key = _env("STRIPE_SECRET_KEY")
    if not stripe_key:
        return {"configured": False, "revenue_cents": 0, "note": "Add STRIPE_SECRET_KEY to .env"}

    headers = {"Authorization": f"Bearer {stripe_key}"}
    # Get recent successful charges from last 24h
    since = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    data = _api_get(
        f"https://api.stripe.com/v1/charges?limit=100&created[gte]={since}",
        headers=headers
    )
    if not data:
        return {"configured": True, "revenue_cents": 0, "error": "API call failed"}

    charges = data.get("data", [])
    total = sum(c.get("amount", 0) for c in charges if c.get("paid") and not c.get("refunded"))
    new_events = 0

    conn = _db()
    for charge in charges:
        if charge.get("paid") and not charge.get("refunded"):
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO revenue_events (source,amount_cents,currency,event_type,description,external_id,timestamp) VALUES (?,?,?,?,?,?,?)",
                    ("stripe", charge["amount"], charge.get("currency","usd").upper(),
                     "payment", charge.get("description","Stripe payment"),
                     charge["id"], datetime.now(timezone.utc).isoformat())
                )
                new_events += 1
            except Exception:
                pass
    conn.commit()
    conn.close()

    return {"configured": True, "revenue_cents": total, "new_events": new_events}


def check_gumroad_revenue() -> dict:
    """Check Gumroad for recent sales."""
    token = _env("GUMROAD_ACCESS_TOKEN")
    if not token:
        return {"configured": False, "revenue_cents": 0, "note": "Add GUMROAD_ACCESS_TOKEN to .env"}

    headers = {"Authorization": f"Bearer {token}"}
    data = _api_get("https://api.gumroad.com/v2/sales", headers=headers)
    if not data or not data.get("success"):
        return {"configured": True, "revenue_cents": 0}

    sales = data.get("sales", [])
    total = sum(int(float(s.get("price", 0)) * 100) for s in sales)
    return {"configured": True, "revenue_cents": total, "sales_count": len(sales)}


def scan_freelance_opportunities() -> list:
    """
    Scan for AI/automation freelance opportunities.
    Uses Upwork RSS feed (public, no auth needed).
    Returns list of scored opportunities.
    """
    opportunities = []

    # Upwork RSS feeds for relevant searches
    rss_feeds = [
        "https://www.upwork.com/ab/feed/jobs/rss?q=AI+automation+python&sort=recency&paging=0%3B10",
        "https://www.upwork.com/ab/feed/jobs/rss?q=LLM+chatbot+agent&sort=recency&paging=0%3B10",
    ]

    for feed_url in rss_feeds:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AliiBot/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="ignore")

            # Simple XML parsing without lxml
            import re
            items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
            for item in items[:5]:
                title_m = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
                link_m  = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
                desc_m  = re.search(r"<description>(.*?)</description>", item, re.DOTALL)

                if not title_m:
                    continue

                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
                link  = link_m.group(1).strip() if link_m else ""
                desc  = re.sub(r"<[^>]+>", "", desc_m.group(1) if desc_m else "").strip()[:500]

                # Score relevance
                keywords = ["ai", "llm", "python", "automation", "chatbot", "agent", "claude", "openai", "gpt"]
                text = (title + " " + desc).lower()
                score = sum(1 for kw in keywords if kw in text) / len(keywords)

                if score > 0.2:
                    opportunities.append({
                        "platform": "upwork",
                        "title": title[:200],
                        "description": desc,
                        "url": link,
                        "relevance_score": round(score, 2),
                    })
        except Exception as e:
            log.debug("Upwork feed error: %s", e)

    # Store in DB
    if opportunities:
        conn = _db()
        now = datetime.now(timezone.utc).isoformat()
        for opp in opportunities:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO opportunities (platform,title,budget_min,budget_max,relevance_score,status,url,found_at) VALUES (?,?,0,0,?,?,?,?)",
                    (opp["platform"], opp["title"], opp["relevance_score"], "new", opp.get("url",""), now)
                )
            except Exception:
                pass
        conn.commit()
        conn.close()
        log.info("Found %d new opportunities", len(opportunities))

    return opportunities


def get_total_revenue() -> dict:
    """Get total revenue from DB."""
    conn = _db()
    try:
        row = conn.execute("SELECT SUM(amount_cents) FROM revenue_events WHERE event_type='payment'").fetchone()
        total = (row[0] or 0)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_row = conn.execute(
            "SELECT SUM(amount_cents) FROM revenue_events WHERE event_type='payment' AND timestamp LIKE ?",
            (f"{today}%",)
        ).fetchone()
        today_total = (today_row[0] or 0)
        return {"total_cents": total, "today_cents": today_total}
    finally:
        conn.close()


def save_daily_report(stars: int, revenue: dict, opportunities: int):
    """Persist daily report to DB."""
    conn = _db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    breakdown = json.dumps(revenue)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO daily_reports (date,total_revenue_cents,github_stars,new_opportunities,breakdown_json,created_at) VALUES (?,?,?,?,?,?)",
            (today, revenue.get("total_cents", 0), stars, opportunities, breakdown, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def format_revenue_report(github: dict, stripe: dict, gumroad: dict, total: dict, opps: list) -> str:
    """Format a rich ntfy revenue report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stars = github.get("total_stars", 0)
    total_usd = total.get("total_cents", 0) / 100
    today_usd = total.get("today_cents", 0) / 100

    lines = [
        f"━━ Alii Revenue Report — {now} ━━",
        f"⭐ GitHub Stars: {stars}",
        "",
        "💰 Revenue:",
        f"  Today:  ${today_usd:.2f}",
        f"  Total:  ${total_usd:.2f}",
        "",
        "🔌 Integrations:",
    ]

    if stripe.get("configured"):
        lines.append(f"  Stripe: ✅  ${stripe.get('revenue_cents',0)/100:.2f} (24h)")
    else:
        lines.append("  Stripe: ⚠️  " + stripe.get("note", "not configured"))

    if gumroad.get("configured"):
        lines.append(f"  Gumroad: ✅  ${gumroad.get('revenue_cents',0)/100:.2f}")
    else:
        lines.append("  Gumroad: ⚠️  " + gumroad.get("note", "not configured"))

    if opps:
        lines.append("")
        lines.append(f"🎯 New Opportunities: {len(opps)}")
        for opp in opps[:3]:
            lines.append(f"  [{opp['relevance_score']:.0%}] {opp['title'][:60]}")

    return "\n".join(lines)


# ── Main loop ──────────────────────────────────────────────────────────────────

def run_cycle():
    log.info("Revenue check cycle starting")
    github  = check_github_stars()
    stripe  = check_stripe_revenue()
    gumroad = check_gumroad_revenue()
    total   = get_total_revenue()
    opps    = scan_freelance_opportunities()

    stars = github.get("total_stars", 0)
    save_daily_report(stars, total, len(opps))

    log.info("Stars=%d  Revenue=$%.2f  Opportunities=%d",
             stars, total.get("total_cents",0)/100, len(opps))
    return github, stripe, gumroad, total, opps


def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log.info("Revenue Tracker started")
    _ntfy("Alii Revenue Tracker", "Revenue monitoring active — checking every 1h.", "low")

    last_report_day = ""

    while True:
        try:
            github, stripe, gumroad, total, opps = run_cycle()

            # Daily 9PM report
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if now.hour == REPORT_HOUR and today != last_report_day:
                report = format_revenue_report(github, stripe, gumroad, total, opps)
                _ntfy("💰 Alii Daily Revenue", report, "default", "money_bag")
                last_report_day = today

        except Exception as exc:
            log.exception("Revenue cycle error: %s", exc)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
