#!/usr/bin/env python3
"""
MoneyAgent — Alii revenue tracking and monetisation manager.
Tracks metrics, analyses revenue streams, and generates daily financial reports.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.money_agent")

WORKDIR  = Path("/home/avalii/moltbot")
TODO_FILE = WORKDIR / "alfred_todo.json"


def _load_todo() -> list:
    if TODO_FILE.exists():
        try:
            return json.loads(TODO_FILE.read_text())
        except Exception:
            return []
    return []


def _save_todo(tasks: list):
    TODO_FILE.write_text(json.dumps(tasks, indent=2))


def _add_todo(task: str):
    tasks = _load_todo()
    tasks.append({"task": task, "created_at": datetime.utcnow().isoformat() + "Z", "done": False})
    _save_todo(tasks)


def _write_memory(category: str, content: str):
    """Write an event to SQLite memory on every call."""
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
        log.debug("Memory written: [%s] %s", category, content[:80])
    except Exception as exc:
        log.warning("Memory write failed: %s", exc)


class MoneyAgent:
    """Tracks and optimises Alii's revenue opportunities."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        _write_memory("money_agent", "MoneyAgent initialised.")
        log.info("MoneyAgent initialised.")

    def analyze_revenue_streams(self) -> dict:
        """
        Survey all known revenue streams and return a structured summary.
        Streams: GitHub Sponsors, Kickstarter, consulting, SaaS subscription.
        """
        log.info("analyze_revenue_streams called.")
        streams = {
            "github_sponsors": {
                "active": bool(self.github_token),
                "monthly_usd": None,
                "note": "Configure GitHub Sponsors on the repo page.",
            },
            "kickstarter": {
                "active": False,
                "pledged_usd": None,
                "note": "Draft campaign not yet launched.",
            },
            "saas_subscription": {
                "active": False,
                "mrr_usd": None,
                "note": "No hosted offering yet.",
            },
            "consulting": {
                "active": False,
                "hourly_rate_usd": None,
                "note": "Set a rate and post availability.",
            },
        }
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "streams": streams,
            "total_mrr_usd": 0,
        }
        _write_memory("money_agent", f"Revenue stream analysis: {json.dumps(result)}")
        return result

    def track_github_stars(self, repo: str = "your-username/alii") -> dict:
        """Fetch GitHub star count — proxy for organic growth / validation."""
        log.info("track_github_stars: repo=%s", repo)
        result: dict = {"repo": repo, "stars": None, "stub": True}
        if self.github_token:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}",
                    headers={"Authorization": f"token {self.github_token}",
                             "Accept": "application/vnd.github.v3+json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                result = {"repo": repo, "stars": data.get("stargazers_count"), "stub": False}
            except Exception as exc:
                log.warning("GitHub API error: %s", exc)
                result["error"] = str(exc)
        _write_memory("money_agent", f"GitHub stars: {result}")
        return result

    def estimate_mrr(self) -> dict:
        """Estimate monthly recurring revenue from all active streams."""
        log.info("estimate_mrr called.")
        streams = self.analyze_revenue_streams()["streams"]
        mrr = sum(
            (v.get("monthly_usd") or 0)
            for v in streams.values()
            if isinstance(v, dict)
        )
        result = {
            "mrr_usd": mrr,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "note": "MRR is $0 until paid tiers are configured.",
        }
        _write_memory("money_agent", f"MRR estimate: {result}")
        if mrr == 0:
            _add_todo("Set up GitHub Sponsors tiers to start earning MRR")
        return result

    def recommend_pricing(self) -> list[dict]:
        """Return a tiered pricing recommendation for Alii-as-a-service."""
        log.info("recommend_pricing called.")
        tiers = [
            {"tier": "Free",        "price_usd": 0,    "features": ["Local install", "Community support"]},
            {"tier": "Supporter",   "price_usd": 5,    "features": ["GitHub Sponsors badge", "Priority issues"]},
            {"tier": "Pro",         "price_usd": 20,   "features": ["Hosted instance", "Private memory", "Email support"]},
            {"tier": "Enterprise",  "price_usd": 99,   "features": ["Multi-node cluster", "SLA", "Custom models"]},
        ]
        _write_memory("money_agent", "Pricing recommendation generated.")
        return tiers

    def manage_github_sponsors(self, action: str = "status") -> dict:
        """Check or update GitHub Sponsors configuration (stub)."""
        log.info("manage_github_sponsors: action=%s", action)
        result: dict = {"action": action, "stub": True}
        if not self.github_token:
            _add_todo("Set GITHUB_TOKEN to enable GitHub Sponsors management")
            result["error"] = "GITHUB_TOKEN not set"
        _write_memory("money_agent", f"GitHub Sponsors: {action}")
        return result

    def kickstarter_status(self) -> dict:
        """Return current Kickstarter campaign status (stub)."""
        log.info("kickstarter_status called.")
        status = {
            "launched": False,
            "goal_usd": 10000,
            "pledged_usd": 0,
            "backers": 0,
            "days_remaining": None,
            "stub": True,
            "note": "Create and launch campaign at kickstarter.com",
        }
        _add_todo("Create Kickstarter draft campaign for Alii")
        _write_memory("money_agent", f"Kickstarter status: {status}")
        return status

    def generate_daily_report(self) -> str:
        """Produce a plain-text daily revenue and growth report."""
        log.info("generate_daily_report called.")
        stars   = self.track_github_stars()
        mrr     = self.estimate_mrr()
        ks      = self.kickstarter_status()
        ts      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        report = (
            f"=== Alii Daily Revenue Report — {ts} ===\n"
            f"GitHub Stars : {stars.get('stars', 'N/A')}\n"
            f"MRR (USD)    : ${mrr['mrr_usd']:.2f}\n"
            f"Kickstarter  : {'LIVE' if ks['launched'] else 'NOT LAUNCHED'} "
            f"(${ks['pledged_usd']} / ${ks['goal_usd']})\n"
            f"Next Action  : Check alfred_todo.json for pending tasks.\n"
        )
        _write_memory("money_agent", f"Daily report generated:\n{report}")
        log.info("Daily report:\n%s", report)
        return report
