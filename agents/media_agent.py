#!/usr/bin/env python3
"""
MediaAgent — Alii social media and brand presence manager.
Handles posting, engagement tracking, and content scheduling across platforms.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("alii.media_agent")

WORKDIR = Path("/home/avalii/moltbot")
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


def _record_event(category: str, content: str):
    try:
        import sys
        sys.path.insert(0, str(WORKDIR))
        from alii_sqlite_memory import AliiSQLiteMemory
        AliiSQLiteMemory().add_memory(category=category, content=content)
    except Exception as exc:
        log.debug("Memory record skipped: %s", exc)


class MediaAgent:
    """Manages Alii's social media presence and brand visibility."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.twitter_key  = os.getenv("TWITTER_API_KEY")
        log.info("MediaAgent initialised.")

    # ── GitHub ──────────────────────────────────────────────────────────────

    def post_to_github(self, repo: str, title: str, body: str) -> dict:
        """Create a GitHub issue or release note on the given repo."""
        log.info("post_to_github: repo=%s title=%s", repo, title)
        if not self.github_token:
            log.warning("GITHUB_TOKEN not set — skipping post.")
            _add_todo(f"Set GITHUB_TOKEN and retry post_to_github for {repo}")
            return {"ok": False, "reason": "GITHUB_TOKEN missing"}
        # stub: would use github REST API POST /repos/{repo}/issues
        payload = {"title": title, "body": body}
        _record_event("media_agent", f"GitHub post stub: {repo} — {title}")
        return {"ok": True, "stub": True, "payload": payload}

    def generate_release_notes(self, version: str, changelog: list[str]) -> str:
        """Format a markdown release notes document from a changelog list."""
        log.info("generate_release_notes: version=%s items=%d", version, len(changelog))
        lines = [f"## Alii {version} — {datetime.utcnow().strftime('%Y-%m-%d')}", ""]
        for item in changelog:
            lines.append(f"- {item}")
        notes = "\n".join(lines)
        _record_event("media_agent", f"Release notes generated: {version}")
        return notes

    def track_github_stars(self, repo: str) -> dict:
        """Fetch current star count for a GitHub repo (stub)."""
        log.info("track_github_stars: repo=%s", repo)
        # stub: would GET /repos/{repo} and return stargazers_count
        _record_event("media_agent", f"Star tracking stub: {repo}")
        return {"repo": repo, "stars": None, "stub": True}

    # ── Twitter / X ──────────────────────────────────────────────────────────

    def post_to_twitter(self, text: str) -> dict:
        """Post a tweet (stub — requires TWITTER_API_KEY)."""
        log.info("post_to_twitter: %.60s…", text)
        if not self.twitter_key:
            log.warning("TWITTER_API_KEY not set — skipping tweet.")
            _add_todo("Set TWITTER_API_KEY and retry post_to_twitter")
            return {"ok": False, "reason": "TWITTER_API_KEY missing"}
        # stub: would use tweepy or twitter v2 API
        _record_event("media_agent", f"Twitter post stub: {text[:80]}")
        return {"ok": True, "stub": True, "text": text}

    # ── Reddit ───────────────────────────────────────────────────────────────

    def post_to_reddit(self, subreddit: str, title: str, body: str) -> dict:
        """Submit a text post to Reddit (stub — requires REDDIT credentials)."""
        log.info("post_to_reddit: r/%s — %s", subreddit, title)
        # stub: would use praw
        _record_event("media_agent", f"Reddit post stub: r/{subreddit} — {title}")
        _add_todo(f"Configure REDDIT_CLIENT_ID/SECRET for r/{subreddit} posting")
        return {"ok": True, "stub": True, "subreddit": subreddit, "title": title}

    # ── LinkedIn ─────────────────────────────────────────────────────────────

    def post_to_linkedin(self, text: str) -> dict:
        """Publish an update to LinkedIn (stub — requires LinkedIn token)."""
        log.info("post_to_linkedin: %.60s…", text)
        _record_event("media_agent", f"LinkedIn post stub: {text[:80]}")
        _add_todo("Configure LINKEDIN_TOKEN for post_to_linkedin")
        return {"ok": True, "stub": True, "text": text}

    # ── Kickstarter ──────────────────────────────────────────────────────────

    def manage_kickstarter(self, action: str = "status") -> dict:
        """Interact with a Kickstarter campaign (stub)."""
        log.info("manage_kickstarter: action=%s", action)
        _record_event("media_agent", f"Kickstarter stub: {action}")
        _add_todo("Set up Kickstarter campaign and configure API access")
        return {"ok": True, "stub": True, "action": action}

    # ── Content & engagement ─────────────────────────────────────────────────

    def track_brand_mentions(self, keywords: list[str] | None = None) -> list[dict]:
        """Search for brand mentions across platforms (stub)."""
        kw = keywords or ["Alii", "moltbot", "alii-ai"]
        log.info("track_brand_mentions: keywords=%s", kw)
        _record_event("media_agent", f"Brand mention tracking: {kw}")
        return [{"keyword": k, "mentions": [], "stub": True} for k in kw]

    def schedule_content(self, platform: str, content: str, post_at: str) -> dict:
        """Queue a piece of content for future posting."""
        log.info("schedule_content: platform=%s post_at=%s", platform, post_at)
        _add_todo(f"Post to {platform} at {post_at}: {content[:60]}")
        _record_event("media_agent", f"Scheduled: {platform} @ {post_at}")
        return {"ok": True, "platform": platform, "post_at": post_at}

    def analyze_engagement(self, platform: str = "all") -> dict:
        """Return engagement metrics summary (stub)."""
        log.info("analyze_engagement: platform=%s", platform)
        _record_event("media_agent", f"Engagement analysis: {platform}")
        return {
            "platform": platform,
            "impressions": None,
            "clicks": None,
            "follows": None,
            "stub": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
