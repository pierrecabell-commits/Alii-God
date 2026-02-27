#!/usr/bin/env python3
"""
MoneyAgent — Alii revenue tracking and monetisation manager.
Tracks metrics, analyses revenue streams, and generates daily financial reports.
"""

import json
import logging
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.money_agent")

WORKDIR       = Path("/home/avalii/moltbot")
TODO_FILE     = WORKDIR / "alfred_todo.json"
REVENUE_REPORT = WORKDIR / "memory" / "revenue_report.json"


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

    def _fetch_github_stars_curl(self, repo: str) -> int | None:
        """Fetch GitHub star count using curl subprocess (no auth needed for public repos)."""
        try:
            r = subprocess.run(
                ["curl", "-s", f"https://api.github.com/repos/{repo}"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return data.get("stargazers_count")
        except Exception as exc:
            log.warning("curl GitHub fetch failed: %s", exc)
        return None

    def _git_remote_repo(self) -> str | None:
        """Detect the GitHub repo slug from git remote origin."""
        try:
            r = subprocess.run(
                ["git", "-C", str(WORKDIR), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            url = r.stdout.strip()
            # https://github.com/user/repo.git  or  git@github.com:user/repo.git
            if "github.com" in url:
                slug = url.split("github.com")[-1].lstrip(":/").removesuffix(".git")
                return slug
        except Exception:
            pass
        return None

    def analyze_revenue_streams(self) -> dict:
        """
        Survey all known revenue streams, fetch live GitHub data, and write revenue_report.json.
        """
        log.info("analyze_revenue_streams called.")

        # Live GitHub star count
        repo_slug = self._git_remote_repo()
        stars = None
        if repo_slug:
            stars = self._fetch_github_stars_curl(repo_slug)
            log.info("GitHub stars for %s: %s", repo_slug, stars)

        # System uptime info
        try:
            uptime_r = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
            uptime = uptime_r.stdout.strip()
        except Exception:
            uptime = "unknown"

        # Alfred service status
        try:
            svc_r = subprocess.run(
                ["systemctl", "--user", "is-active", "alfred.service"],
                capture_output=True, text=True
            )
            alfred_status = svc_r.stdout.strip()
        except Exception:
            alfred_status = "unknown"

        streams = {
            "github_sponsors": {
                "active": bool(self.github_token),
                "monthly_usd": None,
                "github_stars": stars,
                "github_repo": repo_slug,
                "note": "Enable Sponsors at github.com/sponsors/dashboard",
                "action_required": not bool(self.github_token),
            },
            "kickstarter": {
                "active": False,
                "goal_usd": 10000,
                "pledged_usd": 0,
                "note": "Draft campaign not yet launched.",
                "action_required": True,
            },
            "saas_subscription": {
                "active": False,
                "mrr_usd": None,
                "note": "No hosted offering yet. Consider Stripe + hosted Alii tier.",
                "action_required": True,
            },
            "consulting": {
                "active": False,
                "hourly_rate_usd": None,
                "note": "Post availability on LinkedIn / Upwork.",
                "action_required": True,
            },
        }

        immediate_actions = [
            "1. Push repo to GitHub: gh repo create alii --public --source=. --push",
            "2. Enable GitHub Sponsors: https://github.com/sponsors/dashboard",
            "3. Create $5/$20/$99 sponsor tiers",
            "4. Write a project description and add topics on GitHub",
            "5. Post on r/selfhosted and r/MachineLearning",
            "6. Draft Kickstarter campaign page",
        ]

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "system_uptime": uptime,
            "alfred_status": alfred_status,
            "streams": streams,
            "total_mrr_usd": 0,
            "immediate_actions": immediate_actions,
        }

        REVENUE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        REVENUE_REPORT.write_text(json.dumps(result, indent=2))
        log.info("revenue_report.json written to %s", REVENUE_REPORT)
        _write_memory("money_agent", f"Revenue analysis written. Stars: {stars}")
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
