#!/usr/bin/env python3
"""
Account Agent — Autonomous platform account management + content publishing.
7 subsystems: Identity, Content, Strategy, Publisher, Analytics, Compliance, Autonomy.
Platforms: GitHub, Ko-fi, Gumroad, Reddit, DevTo (full); Twitter, LinkedIn, ProductHunt (partial).
"""

import json, logging, os, re, subprocess, sys, time, hashlib, secrets, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import requests

# ---------------------------------------------------------------------------
# Vault integration
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
try:
    from vault.vault_client import get_secret
except ImportError:
    def get_secret(k, d=None): return os.getenv(k, d)

# ---------------------------------------------------------------------------
# Constants — file paths
# ---------------------------------------------------------------------------
try:
    from config import WORKDIR, DATA_DIR
except ImportError:
    WORKDIR = _project_root
ACCOUNTS_FILE   = WORKDIR / "data" / "accounts_registry.json"
REVENUE_FILE    = WORKDIR / "data" / "revenue_live.json"
PERSONAL_INFO   = WORKDIR / "data" / "personal_info_patterns.json"
STRATEGY_FILE   = WORKDIR / "data" / "growth_strategy.json"
LOG_FILE              = WORKDIR / "logs" / "accounts_status.log"
_REVENUE_CHECK_TS_FILE = WORKDIR / "data" / ".last_revenue_check"

# ---------------------------------------------------------------------------
# Platform voices
# ---------------------------------------------------------------------------
PLATFORM_VOICES = {
    "reddit":      "casual, helpful, community-focused. No marketing speak. Real talk.",
    "github":      "technical, precise, open-source focused. README/docs style.",
    "kofi":        "warm, appreciative, creator-to-supporter. Personal and genuine.",
    "twitter":     "punchy, insightful, <280 chars. Hook in first 5 words.",
    "linkedin":    "professional, value-focused, industry insights. 3-5 sentences.",
    "hackernews":  "minimal hype, technical depth, cite sources. Hacker mindset.",
    "producthunt": "exciting launch energy, clear value prop, emoji ok.",
    "devto":       "developer-focused tutorial/insight style. Code examples welcome.",
    "substack":    "long-form, thoughtful newsletter. Personal story + insight.",
}

# Maps scheduled task names (from content_schedule) to (platform, topic, content_type).
# None entries are planning tasks with no publish action.
TASK_MAP: dict = {
    "github_commit":       ("github",       "Open source AI project milestone", "post"),
    "devto_article":       ("devto",        "Building autonomous AI agents with Python", "article"),
    "reddit_comment_x5":   ("reddit",       "Self-hosting and AI automation best practices", "post"),
    "reddit_post":         ("reddit",       "Building autonomous AI agents — lessons learned", "post"),
    "twitter_thread":      ("twitter",      "AI agent development tips and pitfalls", "thread"),
    "linkedin_post":       ("linkedin",     "AI automation: what's working in 2025", "post"),
    "hackernews_comment":  ("hackernews",   "Open source AI tooling landscape", "post"),
    "kofi_update":         ("kofi",         "Project update and what's coming next", "post"),
    "producthunt_hunt":    ("producthunt",  "AI automation tools for developers", "post"),
    "substack_newsletter": ("substack",     "Weekly digest: AI agent development insights", "article"),
    "metrics_review":      None,
    "next_week_planning":  None,
}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("account_agent")


# ---------------------------------------------------------------------------
# Helper: atomic JSON write — prevents corruption on partial write
# ---------------------------------------------------------------------------
def _atomic_write_json(path: Path, data, mode: int = 0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        # Set restrictive permissions on tmp file BEFORE writing sensitive data
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        # chmod before rename so the file is never world-readable at destination
        tmp.chmod(mode)
        tmp.rename(path)
    except (TypeError, OSError) as e:
        log.warning(f"atomic_write_json failed for {path}: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ===========================================================================
# SUBSYSTEM 1: IdentityManager
# ===========================================================================
class IdentityManager:
    PLATFORMS = ["github", "kofi", "gumroad", "reddit", "twitter", "linkedin",
                 "producthunt", "hackernews", "devto", "hashnode", "mastodon", "substack"]

    def __init__(self):
        self.registry = self._load_registry()

    def _load_registry(self) -> dict:
        if ACCOUNTS_FILE.exists():
            try:
                return json.loads(ACCOUNTS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {p: {"status": "not_created", "username": None, "email": None,
                    "created_at": None, "last_health_check": None,
                    "health": "unknown"} for p in self.PLATFORMS}

    def save(self):
        _atomic_write_json(ACCOUNTS_FILE, self.registry)

    def get_account(self, platform: str) -> dict:
        return self.registry.get(platform, {})

    def update_account(self, platform: str, **kwargs):
        if platform not in self.registry:
            self.registry[platform] = {}
        self.registry[platform].update(kwargs)
        self.registry[platform]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def health_check_all(self) -> dict:
        results = {}
        for platform in self.PLATFORMS:
            acct = self.registry.get(platform, {})
            status = acct.get("status", "not_created")
            results[platform] = {
                "status": status,
                "username": acct.get("username"),
                "health": acct.get("health", "unknown"),
                "last_check": acct.get("last_health_check"),
            }
        return results

    def get_credentials(self, platform: str) -> dict:
        creds = {}
        prefix = platform.upper()
        for key in [f"{prefix}_TOKEN", f"{prefix}_API_KEY", f"{prefix}_USERNAME",
                    f"{prefix}_PASSWORD", f"{prefix}_CLIENT_ID", f"{prefix}_CLIENT_SECRET"]:
            val = get_secret(key)
            if val:
                creds[key] = val
        return creds


# ===========================================================================
# SUBSYSTEM 2: ContentEngine
# ===========================================================================
class ContentEngine:
    def __init__(self):
        self.model = self._best_model()

    def _best_model(self) -> str:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            if r.ok:
                models = [m["name"] for m in r.json().get("models", [])]
                for preferred in ["llama3.3:70b", "llama3.1:70b", "llama3.2:latest",
                                  "mistral:latest", "llama3.2:3b", "llama3:latest"]:
                    if preferred in models:
                        return preferred
                    for m in models:
                        if preferred in m:
                            return m  # return actual model name, not the search pattern
                if models:
                    return models[0]
        except (requests.RequestException, ValueError, KeyError):
            pass
        return "llama3.2:3b"

    _FAILURE_PREFIX = "[Content generation failed"

    @staticmethod
    def is_failure(content: str) -> bool:
        """Return True if content is a generation failure placeholder (not safe to publish)."""
        return content.startswith(ContentEngine._FAILURE_PREFIX)

    def generate(self, topic: str, platform: str, content_type: str = "post") -> str:
        voice = PLATFORM_VOICES.get(platform, "clear, professional, authentic")
        prompt = (f"Write a {content_type} for {platform} about: {topic}\n"
                  f"Voice: {voice}\n"
                  f"Platform: {platform}\n"
                  f"Be genuine, helpful, not promotional. Max 500 words.")
        for attempt, timeout in enumerate([60, 45, 30]):
            try:
                r = requests.post("http://localhost:11434/api/generate",
                                  json={"model": self.model, "prompt": prompt, "stream": False},
                                  timeout=timeout)
                r.raise_for_status()
                result = r.json().get("response", "").strip()
                if result:
                    return result
            except requests.Timeout:
                if attempt < 2:
                    log.debug(f"Ollama timeout on attempt {attempt + 1}, retrying...")
                    continue
            except Exception as e:
                log.warning(f"ContentEngine generate error: {e}")
                break
        return f"{ContentEngine._FAILURE_PREFIX} for {platform}: {topic}]"

    def generate_response(self, platform: str, original_comment: str, context: str = "") -> str:
        voice = PLATFORM_VOICES.get(platform, "helpful, authentic")
        prompt = (f"Write a reply on {platform} to this comment:\n\"{original_comment}\"\n"
                  f"Context: {context}\nVoice: {voice}\nBe genuine, add value. Max 200 words.")
        for attempt, timeout in enumerate([45, 30]):
            try:
                r = requests.post("http://localhost:11434/api/generate",
                                  json={"model": self.model, "prompt": prompt, "stream": False},
                                  timeout=timeout)
                r.raise_for_status()
                result = r.json().get("response", "").strip()
                if result:
                    return result
            except requests.Timeout:
                if attempt < 1:
                    log.debug(f"generate_response timeout on attempt {attempt + 1}, retrying...")
                    continue
            except Exception as e:
                log.warning(f"generate_response error: {e}")
                break
        return ""

    def refresh_model(self):
        """Refresh model selection from Ollama. Call at start of each daily cycle."""
        new = self._best_model()
        if new != self.model:
            log.info(f"ContentEngine: model updated {self.model!r} -> {new!r}")
            self.model = new


# ===========================================================================
# SUBSYSTEM 3: StrategyEngine
# ===========================================================================
class StrategyEngine:
    def __init__(self):
        self.strategy = self._load()

    def _load(self) -> dict:
        if STRATEGY_FILE.exists():
            try:
                return json.loads(STRATEGY_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_strategy()

    def _default_strategy(self) -> dict:
        return {
            "monthly_goal": "First $100 MRR",
            "weekly_focus": ["GitHub README optimization", "Reddit presence building",
                             "Ko-fi page setup", "DevTo article draft"],
            "daily_queue": [],
            "growth_playbook": {
                "week1": "Setup all profiles + post intro on each platform",
                "week2": "3 GitHub repos, 2 DevTo articles, 5 Reddit comments/day",
                "week3": "Ko-fi launch post, ProductHunt prep, LinkedIn article",
                "week4": "Analyze metrics, AB test titles, double down on what works",
            },
            "ab_tests": [],
            "content_schedule": {
                "monday":    ["github_commit", "devto_article"],
                "tuesday":   ["reddit_comment_x5", "twitter_thread"],
                "wednesday": ["linkedin_post", "hackernews_comment"],
                "thursday":  ["github_commit", "kofi_update"],
                "friday":    ["reddit_post", "devto_article"],
                "saturday":  ["producthunt_hunt", "substack_newsletter"],
                "sunday":    ["metrics_review", "next_week_planning"],
            }
        }

    def save(self):
        _atomic_write_json(STRATEGY_FILE, self.strategy, mode=0o644)

    def today_tasks(self) -> list:
        day = datetime.now(timezone.utc).strftime("%A").lower()  # UTC matches schedule_today_tasks dedup
        return self.strategy.get("content_schedule", {}).get(day, [])

    def add_ab_test(self, variant_a: str, variant_b: str, metric: str):
        test = {"id": secrets.token_hex(4), "variant_a": variant_a,
                "variant_b": variant_b, "metric": metric,
                "started": datetime.now(timezone.utc).isoformat(),
                "results": {"a": 0, "b": 0}, "winner": None}
        self.strategy.setdefault("ab_tests", []).append(test)
        self.save()
        return test["id"]

    def record_ab_result(self, test_id: str, variant: str, value: float = 1.0) -> bool:
        """Record a measurement for an A/B test variant ('a' or 'b'). Returns True if found."""
        for test in self.strategy.get("ab_tests", []):
            if test.get("id") == test_id:
                if variant not in ("a", "b"):
                    raise ValueError(f"variant must be 'a' or 'b', got {variant!r}")
                test["results"][variant] = test["results"].get(variant, 0) + value
                ra, rb = test["results"].get("a", 0), test["results"].get("b", 0)
                if ra != rb:
                    test["winner"] = "a" if ra > rb else "b"
                self.save()
                return True
        return False

    def set_weekly_focus(self, items: list):
        """Replace the weekly focus list."""
        self.strategy["weekly_focus"] = list(items)
        self.save()

    def set_monthly_goal(self, goal: str):
        """Update the monthly goal string."""
        self.strategy["monthly_goal"] = goal
        self.save()

    def add_to_queue(self, task: dict):
        queue = self.strategy.get("daily_queue", [])
        queue.append({**task, "added_at": datetime.now(timezone.utc).isoformat(),
                      "status": task.get("status", "pending")})
        self.strategy["daily_queue"] = queue[-50:]  # keep last 50
        self.save()

    def get_queue_stats(self) -> dict:
        queue = self.strategy.get("daily_queue", [])
        return {
            "pending": sum(1 for t in queue if t.get("status") == "pending"),
            "done":    sum(1 for t in queue if t.get("status") == "done"),
            "failed":  sum(1 for t in queue if t.get("status") == "failed"),
            "total":   len(queue),
        }

    def clear_completed_tasks(self):
        """Remove done/failed tasks, keep only pending."""
        before = len(self.strategy.get("daily_queue", []))
        self.strategy["daily_queue"] = [
            t for t in self.strategy.get("daily_queue", [])
            if t.get("status", "pending") == "pending"
        ]
        removed = before - len(self.strategy["daily_queue"])
        if removed:
            self.save()
            log.info(f"Cleared {removed} completed/failed tasks from queue")
        return removed

    def requeue_failed_tasks(self, max_retries: int = 3):
        """Reset failed tasks back to pending (capped at max_retries attempts)."""
        count = 0
        exhausted = 0
        for task in self.strategy.get("daily_queue", []):
            if task.get("status") == "failed":
                if task.get("retry_count", 0) < max_retries:
                    task["status"] = "pending"
                    task["retry_count"] = task.get("retry_count", 0) + 1
                    task.pop("result", None)
                    count += 1
                else:
                    exhausted += 1
        if count or exhausted:
            self.save()
            if count:
                log.info(f"Requeued {count} failed tasks for retry")
            if exhausted:
                log.info(f"Skipped {exhausted} exhausted tasks (exceeded {max_retries} retries)")
        return count

    def get_queue(self) -> list:
        """Return current daily queue list. Mutations propagate to strategy state."""
        return self.strategy.setdefault("daily_queue", [])

    def purge_exhausted_tasks(self, max_retries: int = 3) -> int:
        """Permanently remove failed tasks that have hit max_retries. Returns count purged."""
        queue = self.strategy.get("daily_queue", [])
        before = len(queue)
        self.strategy["daily_queue"] = [
            t for t in queue
            if not (t.get("status") == "failed" and t.get("retry_count", 0) >= max_retries)
        ]
        purged = before - len(self.strategy["daily_queue"])
        if purged:
            self.save()
            log.info(f"Purged {purged} exhausted task(s) (>={max_retries} retries)")
        return purged

    def remove_task(self, source_task: str) -> bool:
        """Cancel a pending task by its source_task name. Returns True if removed."""
        queue = self.strategy.get("daily_queue", [])
        before = len(queue)
        self.strategy["daily_queue"] = [
            t for t in queue
            if not (t.get("source_task") == source_task and t.get("status") == "pending")
        ]
        if len(self.strategy["daily_queue"]) < before:
            self.save()
            log.info(f"Removed pending task: {source_task}")
            return True
        return False

    def update_schedule(self, day: str, tasks: list):
        """Replace a day's task list in the content schedule."""
        day = day.lower()
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if day not in valid_days:
            raise ValueError(f"Invalid day: {day}")
        self.strategy.setdefault("content_schedule", {})[day] = tasks
        self.save()
        log.info(f"Updated schedule for {day}: {tasks}")


# ===========================================================================
# SUBSYSTEM 4: AnalyticsEngine
# ===========================================================================
class AnalyticsEngine:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if REVENUE_FILE.exists():
            try:
                return json.loads(REVENUE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"total_mrr": 0, "platforms": {}, "last_updated": None}

    def save(self):
        _atomic_write_json(REVENUE_FILE, self.data)

    def update_revenue(self, platform: str, amount: float, currency: str = "USD"):
        if "platforms" not in self.data:
            self.data["platforms"] = {}
        self.data["platforms"][platform] = {
            "revenue": amount, "currency": currency,
            "updated": datetime.now(timezone.utc).isoformat()
        }
        self.data["total_mrr"] = sum(
            p.get("revenue", 0) for p in self.data["platforms"].values()
        )
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.save()
        self._check_milestones(self.data["total_mrr"])

    def _check_milestones(self, mrr: float):
        milestones_file = WORKDIR / "data" / "milestones.json"
        reached = []
        if milestones_file.exists():
            try:
                reached = json.loads(milestones_file.read_text())
            except (json.JSONDecodeError, OSError):
                reached = []
        checks = [(0.01, "first_dollar"), (100, "100_mrr"), (1000, "1k_mrr")]
        for threshold, name in checks:
            if mrr >= threshold and name not in reached:
                reached.append(name)
                _atomic_write_json(milestones_file, reached)  # atomic — prevents corruption
                msg = f"MILESTONE: {name} reached! MRR=${mrr:.2f}"
                log.info(msg)
                self._ntfy(msg, title="Revenue Milestone!")

    def _ntfy(self, msg: str, title: str = "Alii Analytics"):
        for url in ["http://localhost:8080/alii-revenue", "https://ntfy.sh/alii-precision"]:
            try:
                requests.post(url, data=msg.encode(), headers={"Title": title}, timeout=3)
                return
            except requests.RequestException as e:
                log.debug(f"Analytics ntfy failed ({url}): {e}")

    def collect_all(self, identity: 'IdentityManager') -> dict:
        """Pull revenue from all platforms. Called every 6h."""
        results = {}

        # GitHub Sponsors — delegate to handler to avoid duplicating API logic
        gh = GitHubHandler(identity.get_credentials("github"))
        if gh.token:
            try:
                monthly = gh.get_revenue()
                self.update_revenue("github_sponsors", monthly)
                results["github_sponsors"] = monthly
            except Exception as e:
                log.warning(f"GitHub Sponsors fetch error: {e}")

        # Ko-fi (read from accounts registry — no public API)
        kofi_total = identity.get_account("kofi").get("revenue_total", 0)
        if kofi_total:
            self.update_revenue("kofi", kofi_total)
            results["kofi"] = kofi_total

        # Gumroad — delegate to handler
        gumroad = GumroadHandler(identity.get_credentials("gumroad"))
        if gumroad.token:
            try:
                total = gumroad.get_revenue()
                self.update_revenue("gumroad", total)
                results["gumroad"] = total
            except Exception as e:
                log.warning(f"Gumroad fetch error: {e}")

        return results


# ===========================================================================
# SUBSYSTEM 5: ComplianceEngine
# ===========================================================================
class ComplianceEngine:
    def __init__(self):
        self.patterns = self._load_patterns()
        self._compile()

    def _load_patterns(self) -> dict:
        default = {
            "phone_numbers":  [r"\+?1?\s*\(?\d{3}\)?\s*[-.\s]?\d{3}[-.\s]\d{4}"],
            "private_ips":    [r"192\.168\.\d+\.\d+", r"10\.\d+\.\d+\.\d+",
                               r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"],
            "tailscale_ips":  [r"100\.\d+\.\d+\.\d+"],
            "hostnames":      [r"\baliirecision\b", r"\baliiaiserv\w*\b",
                               r"\bxpsavalii\w*\b", r"\bavalii\b"],
            "vault_paths":    [r"\.alii_vault", r"vault\.enc"],
            "key_patterns":   [r"[A-Za-z0-9+/]{43}=", r"sk-[a-zA-Z0-9]{48,}",
                               r"ghp_[a-zA-Z0-9]{36}", r"pplx-[a-zA-Z0-9]{48}"],
        }
        if PERSONAL_INFO.exists():
            try:
                saved = json.loads(PERSONAL_INFO.read_text())
                default.update(saved)
            except (json.JSONDecodeError, OSError):
                pass
        return default

    def _compile(self):
        self._compiled = []
        for category, patterns in self.patterns.items():
            for p in patterns:
                try:
                    self._compiled.append((category, re.compile(p, re.I)))
                except re.error:
                    pass

    def filter(self, text: str) -> str:
        replacements = {
            "phone_numbers": "[PHONE]",
            "private_ips":   "[PRIVATE-IP]",
            "tailscale_ips": "[TAILSCALE-IP]",
            "hostnames":     "[HOST]",
            "vault_paths":   "[VAULT-PATH]",
            "key_patterns":  "[REDACTED-KEY]",
        }
        for category, pattern in self._compiled:
            replacement = replacements.get(category, "[REDACTED]")
            text = pattern.sub(replacement, text)
        return text

    def is_safe(self, text: str) -> tuple:
        """Returns (is_safe, list_of_violations)"""
        violations = []
        for category, pattern in self._compiled:
            if pattern.search(text):
                violations.append(category)
        return len(violations) == 0, violations

    def save_patterns(self):
        _atomic_write_json(PERSONAL_INFO, self.patterns)


# ===========================================================================
# Platform Handlers
# ===========================================================================

class GitHubHandler:
    def __init__(self, creds: dict):
        self.token = creds.get("GITHUB_TOKEN") or get_secret("GITHUB_TOKEN", "")
        self.username = creds.get("GITHUB_USERNAME") or get_secret("GITHUB_USERNAME", "")
        self._headers = {"Authorization": f"token {self.token}",
                         "Accept": "application/vnd.github+json"} if self.token else {}

    def post_content(self, content: str, repo: str = None, **kwargs) -> dict:
        """Create a GitHub gist as a post."""
        if not self.token:
            return {"ok": False, "error": "No GitHub token"}
        try:
            r = requests.post("https://api.github.com/gists",
                              headers=self._headers,
                              json={"description": content[:100], "public": True,
                                    "files": {"post.md": {"content": content}}},
                              timeout=10)
            return {"ok": r.ok, "url": r.json().get("html_url"), "status": r.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_analytics(self) -> dict:
        if not self.token:
            return {}
        try:
            r = requests.get("https://api.github.com/user/repos",
                             headers=self._headers, params={"per_page": 30}, timeout=10)
            repos = r.json() if r.ok else []
            if not isinstance(repos, list):
                repos = []
            return {
                "repos": len(repos),
                "total_stars": sum(repo.get("stargazers_count", 0) for repo in repos),
                "total_forks": sum(repo.get("forks_count", 0) for repo in repos),
            }
        except (requests.RequestException, ValueError, KeyError):
            return {}

    def get_revenue(self) -> float:
        if not self.token:
            return 0.0
        try:
            r = requests.get("https://api.github.com/user/sponsorships/as_maintainer",
                             headers=self._headers,
                             timeout=10)
            if r.ok:
                sponsors = r.json()
                if isinstance(sponsors, list):
                    return sum(s.get("tier", {}).get("monthly_price_in_dollars", 0)
                               for s in sponsors)
        except (requests.RequestException, ValueError, KeyError):
            pass
        return 0.0

    def respond_to_comments(self, issue_number: str, text: str, repo: str = None) -> dict:
        if not self.token or not repo:
            return {"ok": False, "error": "Missing token or repo"}
        try:
            r = requests.post(
                f"https://api.github.com/repos/{self.username}/{repo}/issues/{issue_number}/comments",
                headers=self._headers, json={"body": text}, timeout=10)
            return {"ok": r.ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_profile(self, bio: str = None, name: str = None, **kwargs) -> dict:
        if not self.token:
            return {"ok": False, "error": "No token"}
        data = {}
        if bio:
            data["bio"] = bio
        if name:
            data["name"] = name
        try:
            r = requests.patch("https://api.github.com/user", headers=self._headers,
                               json=data, timeout=10)
            return {"ok": r.ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def create_account(self) -> dict:
        return {"ok": False, "note": "GitHub accounts created manually at github.com"}

    def verify_email(self, code: str = None) -> dict:
        return {"ok": False, "note": "GitHub email verification done manually"}

    def follow(self, username: str) -> dict:
        if not self.token:
            return {"ok": False}
        try:
            r = requests.put(f"https://api.github.com/user/following/{username}",
                             headers=self._headers, timeout=10)
            return {"ok": r.status_code == 204}
        except Exception as e:
            return {"ok": False, "error": str(e)}


class KofiHandler:
    def __init__(self, creds: dict):
        self.token = creds.get("KOFI_TOKEN") or get_secret("KOFI_TOKEN", "")
        self.username = creds.get("KOFI_USERNAME") or get_secret("KOFI_USERNAME", "")

    def post_content(self, content: str, **kwargs) -> dict:
        if not self.token:
            return {"ok": False, "error": "Ko-fi API not available — post manually at ko-fi.com"}
        return {"ok": False, "error": "Ko-fi REST API not publicly available"}

    def get_analytics(self) -> dict:
        return {"username": self.username, "note": "Ko-fi analytics via dashboard only"}

    def get_revenue(self) -> float:
        return 0.0

    def respond_to_comments(self, comment_id: str, text: str) -> dict:
        return {"ok": False, "note": "Ko-fi comments via dashboard"}

    def follow(self, username: str) -> dict:
        return {"ok": False, "note": "Ko-fi follow via dashboard"}

    def update_profile(self, **kwargs) -> dict:
        return {"ok": False, "note": "Ko-fi profile via dashboard"}

    def create_account(self) -> dict:
        return {"ok": False, "note": "Ko-fi account creation requires browser automation"}

    def verify_email(self, code: str = None) -> dict:
        return {"ok": False, "note": "Ko-fi email verification via dashboard"}


class GumroadHandler:
    def __init__(self, creds: dict):
        self.token = creds.get("GUMROAD_ACCESS_TOKEN") or get_secret("GUMROAD_ACCESS_TOKEN", "")

    def post_content(self, content: str, title: str = "New Post", price: float = 0, **kwargs) -> dict:
        """Create a Gumroad product/post."""
        if not self.token:
            return {"ok": False, "error": "No Gumroad token"}
        try:
            try:
                price_cents = int(round(float(price) * 100))
            except (ValueError, TypeError):
                return {"ok": False, "error": f"Invalid price value: {price!r}"}
            r = requests.post("https://api.gumroad.com/v2/products",
                              headers={"Authorization": f"Bearer {self.token}"},
                              data={"name": title, "description": content, "price": price_cents},
                              timeout=10)
            if not r.ok:
                return {"ok": False, "error": f"Gumroad {r.status_code}: {r.text[:200]}"}
            d = r.json()
            return {"ok": d.get("success"), "url": d.get("product", {}).get("url")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_analytics(self) -> dict:
        if not self.token:
            return {}
        try:
            r = requests.get("https://api.gumroad.com/v2/products",
                             headers={"Authorization": f"Bearer {self.token}"}, timeout=10)
            if not r.ok:
                return {}
            products = r.json().get("products", [])
            return {
                "products": len(products),
                "total_sales": sum(p.get("sales_count", 0) for p in products),
                "total_revenue": sum(p.get("sales_usd_cents", 0) for p in products) / 100,
            }
        except (requests.RequestException, ValueError, KeyError):
            return {}

    def get_revenue(self) -> float:
        analytics = self.get_analytics()
        return analytics.get("total_revenue", 0.0)

    def respond_to_comments(self, product_id: str, text: str) -> dict:
        return {"ok": False, "note": "Gumroad comments via dashboard"}

    def follow(self, username: str) -> dict:
        return {"ok": False, "note": "Gumroad follow via dashboard"}

    def update_profile(self, **kwargs) -> dict:
        return {"ok": False, "note": "Gumroad profile via dashboard"}

    def create_account(self) -> dict:
        return {"ok": False, "note": "Gumroad account creation requires browser"}

    def verify_email(self, code: str = None) -> dict:
        return {"ok": False, "note": "Gumroad email via dashboard"}


class RedditHandler:
    def __init__(self, creds: dict):
        # Prefer vault-injected creds; fall back to env via get_secret
        self.client_id     = creds.get("REDDIT_CLIENT_ID")     or get_secret("REDDIT_CLIENT_ID", "")
        self.client_secret = creds.get("REDDIT_CLIENT_SECRET") or get_secret("REDDIT_CLIENT_SECRET", "")
        self.username      = creds.get("REDDIT_USERNAME")      or get_secret("REDDIT_USERNAME", "")
        self.password      = creds.get("REDDIT_PASSWORD")      or get_secret("REDDIT_PASSWORD", "")
        self._reddit = None
        if self.client_id and self.client_secret and self.username and self.password:
            try:
                import praw
            except ImportError:
                log.warning("praw not installed — Reddit handler disabled (pip install praw)")
                return
            try:
                self._reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    username=self.username,
                    password=self.password,
                    user_agent="Alii Agent v1.0",
                )
            except Exception as e:
                log.warning(f"Reddit auth failed — check REDDIT_* credentials: {e}")

    def post_content(self, content: str, subreddit: str = "selfhosted",
                     title: str = None, **kwargs) -> dict:
        if not self._reddit:
            return {"ok": False, "error": "Reddit not configured"}
        try:
            sub = self._reddit.subreddit(subreddit)
            post = sub.submit(title or content[:100], selftext=content)
            return {"ok": True, "url": post.url, "id": post.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_analytics(self) -> dict:
        if not self._reddit:
            return {}
        try:
            user = self._reddit.user.me()
            return {
                "karma_post":    user.link_karma,
                "karma_comment": user.comment_karma,
                "username":      str(user.name),
            }
        except Exception as e:
            log.debug(f"Reddit analytics error: {e}")
            return {}

    def get_revenue(self) -> float:
        return 0.0

    def respond_to_comments(self, comment_id: str, text: str) -> dict:
        if not self._reddit:
            return {"ok": False, "error": "Not configured"}
        try:
            comment = self._reddit.comment(id=comment_id)
            reply = comment.reply(text)
            return {"ok": True, "id": reply.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def follow(self, username: str) -> dict:
        if not self._reddit:
            return {"ok": False}
        try:
            self._reddit.redditor(username).follow()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_profile(self, **kwargs) -> dict:
        return {"ok": False, "note": "Reddit profile updated via dashboard"}

    def create_account(self) -> dict:
        return {"ok": False, "note": "Reddit account creation requires browser automation"}

    def verify_email(self, code: str = None) -> dict:
        return {"ok": False, "note": "Reddit email verification via email link"}


class DevToHandler:
    """Dev.to handler using their public REST API."""

    def __init__(self, creds: dict):
        self.api_key = creds.get("DEVTO_API_KEY") or get_secret("DEVTO_API_KEY", "")
        self._headers = {"api-key": self.api_key, "Content-Type": "application/json"} if self.api_key else {}

    def post_content(self, content: str, title: str = None, tags: list = None, **kwargs) -> dict:
        if not self.api_key:
            return {"ok": False, "error": "No Dev.to API key"}
        payload = {
            "article": {
                "title": title or content[:60].split("\n")[0].strip() or "New Post",
                "body_markdown": content,
                "published": True,
                "tags": tags or ["programming", "tutorial"],
            }
        }
        for attempt in range(2):
            try:
                r = requests.post("https://dev.to/api/articles",
                                  headers=self._headers, json=payload, timeout=15)
                if r.ok:
                    data = r.json()
                    return {"ok": True, "url": data.get("url"), "id": data.get("id")}
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 60))
                    log.warning(f"Dev.to rate-limited — waiting {retry_after}s before retry")
                    time.sleep(min(retry_after, 120))
                    continue
                return {"ok": False, "error": r.text[:200], "status": r.status_code}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": False, "error": "Dev.to rate-limited after retry"}

    def get_analytics(self) -> dict:
        if not self.api_key:
            return {}
        try:
            r = requests.get("https://dev.to/api/articles/me",
                             headers=self._headers, timeout=10)
            articles = r.json() if r.ok else []
            if not isinstance(articles, list):
                articles = []
            return {
                "articles": len(articles),
                "total_reactions": sum(a.get("positive_reactions_count", 0) for a in articles),
                "total_comments": sum(a.get("comments_count", 0) for a in articles),
            }
        except (requests.RequestException, ValueError, KeyError):
            return {}

    def get_revenue(self) -> float:
        return 0.0

    def respond_to_comments(self, comment_id: str, text: str) -> dict:
        return {"ok": False, "note": "Dev.to comment replies via dashboard"}

    def follow(self, username: str) -> dict:
        return {"ok": False, "note": "Dev.to follow via dashboard"}

    def update_profile(self, **kwargs) -> dict:
        return {"ok": False, "note": "Dev.to profile via dashboard"}

    def create_account(self) -> dict:
        return {"ok": False, "note": "Dev.to account creation via devto.to"}

    def verify_email(self, code: str = None) -> dict:
        return {"ok": False, "note": "Dev.to email verification via email link"}


# ===========================================================================
# SUBSYSTEM 6 (continued): PublisherEngine
# ===========================================================================
class PublisherEngine:
    def __init__(self, identity: IdentityManager, content: ContentEngine,
                 compliance: ComplianceEngine):
        self.identity   = identity
        self.content    = content
        self.compliance = compliance

    def post(self, platform: str, text: str, **kwargs) -> dict:
        """Post content to platform after compliance check."""
        safe_text = self.compliance.filter(text)
        handler = self._get_handler(platform)
        if handler:
            result = handler.post_content(safe_text, **kwargs)
            if not result.get("ok"):
                log.warning(f"PublisherEngine: post to {platform} failed: {result.get('error') or result.get('note')}")
            return result
        return {"ok": False, "error": f"No handler for {platform}"}

    def respond(self, platform: str, comment_id: str, text: str) -> dict:
        safe_text = self.compliance.filter(text)
        handler = self._get_handler(platform)
        if handler:
            return handler.respond_to_comments(comment_id, safe_text)
        return {"ok": False, "error": f"No handler for {platform}"}

    def _get_handler(self, platform: str):
        handlers = {
            "github":  GitHubHandler,
            "kofi":    KofiHandler,
            "gumroad": GumroadHandler,
            "reddit":  RedditHandler,
            "devto":   DevToHandler,
        }
        cls = handlers.get(platform)
        if cls:
            return cls(self.identity.get_credentials(platform))
        return None


# ===========================================================================
# SUBSYSTEM 7: AutonomyEngine
# ===========================================================================
class AutonomyEngine:
    REVENUE_CHECK_INTERVAL = 21600  # 6 hours

    def __init__(self, identity: IdentityManager, content: ContentEngine,
                 strategy: StrategyEngine, publisher: PublisherEngine,
                 analytics: AnalyticsEngine, compliance: ComplianceEngine):
        self.identity   = identity
        self.content    = content
        self.strategy   = strategy
        self.publisher  = publisher
        self.analytics  = analytics
        self.compliance = compliance
        self._last_revenue_check = self._load_revenue_ts()
        self._todo_agent = None

    def _load_revenue_ts(self) -> float:
        try:
            return float(_REVENUE_CHECK_TS_FILE.read_text().strip())
        except (OSError, ValueError):
            return 0.0

    def _save_revenue_ts(self, ts: float):
        try:
            _REVENUE_CHECK_TS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _REVENUE_CHECK_TS_FILE.write_text(str(ts))
        except OSError as e:
            log.debug(f"Could not persist revenue timestamp: {e}")

    def _get_todo_agent(self):
        if self._todo_agent is None:
            try:
                from agents.todo_agent import TodoAgent
                self._todo_agent = TodoAgent()
            except Exception as e:
                log.warning(f"TodoAgent init failed: {e}")
        return self._todo_agent

    def _add_todo(self, title: str, context: str, category: str = "action", priority: str = "medium"):
        """Add a todo via todo_agent per CLAUDE.md rules."""
        ta = self._get_todo_agent()
        if ta is None:
            log.error("TodoAgent unavailable — cannot track manual action")
            self.notify_owner(f"WARNING: Todo system offline. Manual action needed: {title}", "Todo System Error")
            return
        try:
            if hasattr(ta, "add_todo"):
                ta.add_todo(title=title, context=context, category=category, priority=priority)
                log.debug(f"Todo added: {title}")
        except Exception as e:
            log.warning(f"Could not add todo '{title}': {e}")

    def schedule_today_tasks(self):
        """Convert today's content calendar entries into queue items (idempotent — skips already-queued tasks)."""
        tasks = self.strategy.today_tasks()
        if not tasks:
            return
        queue = self.strategy.get_queue()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")  # UTC matches added_at timestamps
        already_queued = {t.get("source_task") for t in queue if t.get("added_at", "").startswith(today)}
        added = 0
        for task_name in tasks:
            entry = TASK_MAP.get(task_name)
            if entry is None:
                log.debug(f"schedule_today_tasks: '{task_name}' is a planning task — no publish action")
                continue
            if task_name in already_queued:
                log.debug(f"schedule_today_tasks: '{task_name}' already queued today")
                continue
            platform, topic, content_type = entry
            if self.publisher._get_handler(platform) is None:
                log.warning(f"schedule_today_tasks: no handler for '{platform}' — '{task_name}' skipped")
                self._add_todo(
                    title=f"Add handler for '{platform}' to publish '{task_name}'",
                    context=f"Task '{task_name}' is scheduled today but '{platform}' has no publisher handler. Add a handler class or remove the task from the schedule.",
                    category="config",
                    priority="low",
                )
                continue
            self.strategy.add_to_queue({
                "platform": platform,
                "topic": topic,
                "content_type": content_type,
                "source_task": task_name,
                "status": "pending",
            })
            added += 1
            log.info(f"Scheduled today's task: {task_name} → {platform}")
        if added:
            log.info(f"Queued {added} task(s) from today's content calendar")

    def notify_owner(self, message: str, title: str = "Alii Accounts"):
        """Notify via ntfy (local first, public fallback) and log."""
        log.info(f"NOTIFY: {message}")
        for url in ["http://localhost:8080/alii-accounts", "https://ntfy.sh/alii-precision"]:
            try:
                requests.post(url, data=message.encode(),
                              headers={"Title": title}, timeout=3)
                return
            except requests.RequestException as e:
                log.debug(f"notify_owner ntfy failed ({url}): {e}")

    def run_daily_cycle(self):
        """Called once daily at 08:00 by daemon."""
        log.info("Running daily autonomy cycle")
        self.content.refresh_model()
        today_tasks = self.strategy.today_tasks()
        log.info(f"Today's tasks: {today_tasks}")

        # Retry failed tasks from previous cycles before scheduling new ones
        retried = self.strategy.requeue_failed_tasks()
        if retried:
            log.info(f"Retried {retried} previously failed task(s)")

        # Schedule today's content calendar tasks into the queue
        self.schedule_today_tasks()

        # Revenue check every 6h
        now = time.time()
        if now - self._last_revenue_check > self.REVENUE_CHECK_INTERVAL:
            try:
                results = self.analytics.collect_all(self.identity)
                log.info(f"Revenue collected: {results}")
                self._last_revenue_check = now
                self._save_revenue_ts(now)
            except Exception as e:
                log.warning(f"Revenue collection error: {e}")

        # Health check all accounts
        health = self.identity.health_check_all()
        unhealthy = [p for p, h in health.items() if h.get("health") == "error"]
        if unhealthy:
            msg = f"Accounts needing attention: {', '.join(unhealthy)}"
            self.notify_owner(msg, "Account Health Alert")
            self._add_todo(
                title=f"Fix unhealthy accounts: {', '.join(unhealthy)}",
                context=f"Health check found errors on: {', '.join(unhealthy)}. Check credentials and platform status.",
                category="account",
                priority="high",
            )

        # Process content queue — scan all pending tasks, cap at 3 processed per cycle
        queue = self.strategy.get_queue()
        processed = []
        processed_count = 0
        for task in queue:
            if processed_count >= 3:
                break
            if task.get("status") == "pending":
                platform = task.get("platform", "")
                topic    = task.get("topic", "")
                if platform and topic:
                    content = self.content.generate(topic, platform,
                                                    task.get("content_type", "post"))
                    if ContentEngine.is_failure(content):
                        log.warning(f"Content generation failed for {platform} — Ollama unavailable, skipping post")
                        task["status"] = "failed"
                        task["result"] = {"ok": False, "error": "Ollama content generation unavailable"}
                        task["published_at"] = datetime.now(timezone.utc).isoformat()
                        processed.append(task)
                        processed_count += 1
                        self._add_todo(
                            title=f"Manual post needed on {platform} (Ollama down)",
                            context=f"Content generation failed for topic '{topic}' on {platform}. Ollama unreachable.",
                            category="account",
                            priority="low",
                        )
                        continue
                    safe, violations = self.compliance.is_safe(content)
                    if not safe:
                        log.warning(f"Content blocked for {platform}: {violations}")
                        content = self.compliance.filter(content)
                    result = self.publisher.post(platform, content)
                    task["status"] = "done" if result.get("ok") else "failed"
                    task["result"] = result
                    task["published_at"] = datetime.now(timezone.utc).isoformat()
                    processed.append(task)
                    processed_count += 1
                    if processed_count < 3:
                        time.sleep(1.5)  # rate-limit guard between sequential platform posts
                    if not result.get("ok"):
                        self._add_todo(
                            title=f"Manual post needed on {platform}",
                            context=f"Auto-publish failed for topic '{topic}' on {platform}: {result.get('error') or result.get('note', 'unknown error')}",
                            category="account",
                            priority="low",
                        )

        if processed:
            self.strategy.save()
            log.info(f"Processed {len(processed)} queued tasks")

        # Log deferred tasks so Pierre knows the queue isn't empty
        remaining_pending = sum(1 for t in queue if t.get("status") == "pending")
        if remaining_pending:
            log.info(f"{remaining_pending} pending task(s) deferred to next cycle")

        # Auto-clear old completed tasks weekly (Sunday)
        if datetime.now().strftime("%A").lower() == "sunday":
            self.strategy.clear_completed_tasks()

        # Daily summary notification to Pierre
        stats = self.strategy.get_queue_stats()
        mrr = self.analytics.data.get("total_mrr", 0)
        summary = (f"Daily cycle done. Queue: {stats['pending']} pending, "
                   f"{stats['done']} done, {stats['failed']} failed. MRR=${mrr:.2f}")
        self.notify_owner(summary, "Alii Daily Cycle")

    def request_approval(self, action: str, details: dict):
        """Request owner approval for sensitive actions."""
        msg = f"APPROVAL NEEDED: {action}\n{json.dumps(details, indent=2)[:300]}"
        self.notify_owner(msg, "Action Approval Required")
        log.info(f"Approval requested for: {action}")


# ===========================================================================
# AccountAgent — Main Orchestrator
# ===========================================================================
class AccountAgent:
    def __init__(self):
        self.identity   = IdentityManager()
        self.content    = ContentEngine()
        self.strategy   = StrategyEngine()
        self.compliance = ComplianceEngine()
        self.analytics  = AnalyticsEngine()
        self.publisher  = PublisherEngine(self.identity, self.content, self.compliance)
        self.autonomy   = AutonomyEngine(
            self.identity, self.content, self.strategy,
            self.publisher, self.analytics, self.compliance
        )

    def run_once(self):
        """Run one daily cycle."""
        log.info("AccountAgent daily cycle starting")
        self.autonomy.run_daily_cycle()
        log.info("AccountAgent daily cycle complete")

    def _drain_queue(self, max_tasks: int = 2):
        """Process up to max_tasks pending queue items immediately. Used by hourly drain."""
        queue = self.autonomy.strategy.get_queue()
        processed = 0
        for task in queue:
            if processed >= max_tasks:
                break
            if task.get("status") != "pending":
                continue
            platform = task.get("platform", "")
            topic    = task.get("topic", "")
            if not platform or not topic:
                continue
            content = self.content.generate(topic, platform, task.get("content_type", "post"))
            if ContentEngine.is_failure(content):
                log.debug(f"_drain_queue: Ollama unavailable for {platform}, leaving task pending")
                break  # Ollama is down — stop draining, leave tasks for later
            safe, violations = self.autonomy.compliance.is_safe(content)
            if not safe:
                content = self.autonomy.compliance.filter(content)
            result = self.autonomy.publisher.post(platform, content)
            task["status"] = "done" if result.get("ok") else "failed"
            task["result"] = result
            task["published_at"] = datetime.now(timezone.utc).isoformat()
            processed += 1
            if processed < max_tasks:
                time.sleep(1.5)
            if not result.get("ok"):
                self.autonomy._add_todo(
                    title=f"Manual post needed on {platform}",
                    context=f"Hourly drain: publish failed for '{topic}' on {platform}: {result.get('error') or result.get('note', 'unknown')}",
                    category="account",
                    priority="low",
                )
        if processed:
            self.autonomy.strategy.save()
            log.info(f"Hourly drain: processed {processed} queued task(s)")

    def run_daemon(self):
        """Run as daemon — daily cycle at 08:00, hourly queue drain, weekly health update."""
        log.info("AccountAgent daemon starting")
        last_run_date = None
        last_health_update_week = None
        last_drain_hour = -1
        while True:
            try:
                now = datetime.now()
                today = now.date()
                current_week = today.isocalendar()[:2]  # (year, week)

                # Daily cycle at 08:00
                if now.hour == 8 and now.minute < 2 and last_run_date != today:
                    try:
                        self.run_once()
                        last_run_date = today  # only mark as done on success
                    except Exception as e:
                        log.error(f"Daily cycle error: {e}")
                        self.autonomy.notify_owner(
                            f"Daily cycle FAILED: {e}", "Account Agent Error"
                        )
                        self.autonomy._add_todo(
                            title="Investigate AccountAgent daily cycle failure",
                            context=f"run_once() raised: {e}",
                            category="action",
                            priority="high",
                        )
                        # Consume the date slot to avoid hammering on repeated errors
                        last_run_date = today

                # Weekly health update on Monday at 09:00
                if (now.weekday() == 0 and now.hour == 9 and now.minute < 2
                        and last_health_update_week != current_week):
                    try:
                        results = self.update_health()
                        log.info(f"Weekly health update: {results}")
                        last_health_update_week = current_week
                    except Exception as e:
                        log.warning(f"Weekly health update error: {e}")

                # Hourly queue drain (outside of 8am window to avoid double-processing)
                if now.hour != 8 and now.hour != last_drain_hour:
                    try:
                        self._drain_queue(max_tasks=2)
                        last_drain_hour = now.hour
                    except Exception as e:
                        log.warning(f"Hourly queue drain error: {e}")

            except Exception as e:
                log.error(f"Daemon loop error: {e}")
            time.sleep(30)

    def status(self) -> dict:
        return {
            "accounts":      self.identity.health_check_all(),
            "revenue":       self.analytics.data,
            "strategy_today": self.strategy.today_tasks(),
            "content_model": self.content.model,
            "queue":         self.strategy.get_queue_stats(),
        }

    def enqueue_content(self, platform: str, topic: str, content_type: str = "post") -> dict:
        """Queue a content task for the next daily cycle."""
        if self.publisher._get_handler(platform) is None:
            supported = "github, kofi, gumroad, reddit, devto"
            return {"ok": False, "error": f"Platform '{platform}' has no handler. Supported: {supported}"}
        task = {"platform": platform, "topic": topic, "content_type": content_type, "status": "pending"}
        self.strategy.add_to_queue(task)
        log.info(f"Enqueued {content_type} for {platform}: {topic[:60]}")
        return {"ok": True, "task": task}

    def publish_now(self, platform: str, topic: str, content_type: str = "post") -> dict:
        """Generate and publish content immediately (bypasses queue)."""
        log.info(f"Immediate publish: {platform} / {topic}")
        content = self.content.generate(topic, platform, content_type)
        if ContentEngine.is_failure(content):
            log.warning(f"publish_now: content generation failed for {platform} — Ollama unavailable")
            return {"ok": False, "error": "Content generation failed — Ollama unavailable"}
        safe, violations = self.compliance.is_safe(content)
        if not safe:
            content = self.compliance.filter(content)
            log.info(f"Content filtered — violations: {violations}")
        result = self.publisher.post(platform, content)
        log.info(f"publish_now result for {platform}: {result}")
        if not result.get("ok"):
            self.autonomy._add_todo(
                title=f"Manual post needed on {platform}",
                context=f"publish_now failed for topic '{topic}' on {platform}: {result.get('error') or result.get('note', 'unknown error')}",
                category="account",
                priority="low",
            )
        return result

    def publish_direct(self, platform: str, content: str, **kwargs) -> dict:
        """Publish pre-written content directly without Ollama generation."""
        log.info(f"Direct publish to {platform}: {content[:60]!r}")
        safe, violations = self.compliance.is_safe(content)
        if not safe:
            content = self.compliance.filter(content)
            log.info(f"publish_direct: filtered violations {violations} for {platform}")
        result = self.publisher.post(platform, content, **kwargs)
        log.info(f"publish_direct result for {platform}: {result}")
        return result

    def respond_to_comment(self, platform: str, comment_id: str, text: str) -> dict:
        """Respond to a comment on a platform after compliance filtering."""
        log.info(f"Responding to comment {comment_id} on {platform}")
        result = self.publisher.respond(platform, comment_id, text)
        log.info(f"respond_to_comment result for {platform}: {result}")
        if not result.get("ok"):
            self.autonomy._add_todo(
                title=f"Manual comment reply needed on {platform}",
                context=f"Auto-reply to comment '{comment_id}' on {platform} failed: {result.get('error') or result.get('note', 'unknown')}",
                category="account",
                priority="low",
            )
        return result

    def get_strategy(self) -> dict:
        """Return full strategy snapshot: goal, focus, schedule, queue stats, A/B tests."""
        s = self.strategy.strategy
        return {
            "monthly_goal":    s.get("monthly_goal"),
            "weekly_focus":    s.get("weekly_focus", []),
            "content_schedule": s.get("content_schedule", {}),
            "today_tasks":     self.strategy.today_tasks(),
            "queue":           self.strategy.get_queue_stats(),
            "ab_tests":        s.get("ab_tests", []),
            "growth_playbook": s.get("growth_playbook", {}),
        }

    def schedule_today(self) -> dict:
        """Trigger scheduling of today's content calendar tasks into the queue."""
        before = self.strategy.get_queue_stats()
        self.autonomy.schedule_today_tasks()
        after = self.strategy.get_queue_stats()
        added = after["total"] - before["total"]
        log.info(f"schedule_today: {added} task(s) added to queue")
        return {"ok": True, "added": added, "queue": after}

    def get_queue_status(self) -> dict:
        return self.strategy.get_queue_stats()

    def clear_completed_tasks(self) -> int:
        return self.strategy.clear_completed_tasks()

    def retry_failed_tasks(self) -> int:
        return self.strategy.requeue_failed_tasks()

    def get_analytics(self) -> dict:
        """Collect analytics from all configured platforms."""
        results = {}
        for platform in ["github", "reddit", "gumroad", "devto"]:
            handler = self.publisher._get_handler(platform)
            if handler:
                try:
                    data = handler.get_analytics()
                    if data:
                        results[platform] = data
                except Exception as e:
                    log.debug(f"Analytics error for {platform}: {e}")
        return {
            "platforms": results,
            "revenue": self.analytics.data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def run_revenue_check(self) -> dict:
        """Trigger an immediate revenue collection from all platforms."""
        log.info("Running on-demand revenue check")
        try:
            results = self.analytics.collect_all(self.identity)
            self.autonomy._last_revenue_check = time.time()
            self.autonomy._save_revenue_ts(self.autonomy._last_revenue_check)
            log.info(f"Revenue check complete: {results}")
            return {"ok": True, "results": results, "total_mrr": self.analytics.data.get("total_mrr", 0)}
        except Exception as e:
            log.error(f"Revenue check error: {e}")
            return {"ok": False, "error": str(e)}

    def get_queue_detail(self) -> list:
        """Return full queue with all task fields for inspection (copy — safe to mutate)."""
        return list(self.strategy.get_queue())

    def preview_content(self, platform: str, topic: str, content_type: str = "post") -> dict:
        """Generate content preview without publishing."""
        content = self.content.generate(topic, platform, content_type)
        safe, violations = self.compliance.is_safe(content)
        if not safe:
            content = self.compliance.filter(content)
        return {
            "platform": platform,
            "topic": topic,
            "content_type": content_type,
            "content": content,
            "filtered": not safe,
            "violations": violations,
            "model": self.content.model,
            "char_count": len(content),
        }

    def credentials_status(self) -> dict:
        """Report which platforms have credentials configured (without revealing values)."""
        status = {}
        for platform in IdentityManager.PLATFORMS:
            creds = self.identity.get_credentials(platform)
            status[platform] = {
                "has_credentials": bool(creds),
                "keys_present": list(creds.keys()) if creds else [],
            }
        return status

    def remove_task(self, source_task: str) -> dict:
        """Cancel a pending task by source_task name."""
        removed = self.strategy.remove_task(source_task)
        return {"ok": removed, "removed": source_task if removed else None}

    def set_weekly_focus(self, items: list) -> dict:
        """Update the weekly focus list in strategy."""
        self.strategy.set_weekly_focus(items)
        log.info(f"Weekly focus updated: {items}")
        return {"ok": True, "weekly_focus": items}

    def set_monthly_goal(self, goal: str) -> dict:
        """Update the monthly goal in strategy."""
        self.strategy.set_monthly_goal(goal)
        log.info(f"Monthly goal updated: {goal!r}")
        return {"ok": True, "monthly_goal": goal}

    def record_ab_result(self, test_id: str, variant: str, value: float = 1.0) -> dict:
        """Record a measurement for an A/B test variant."""
        found = self.strategy.record_ab_result(test_id, variant, value)
        return {"ok": found, "test_id": test_id, "variant": variant}

    def add_ab_test(self, variant_a: str, variant_b: str, metric: str) -> dict:
        """Create a new A/B test between two content variants."""
        test_id = self.strategy.add_ab_test(variant_a, variant_b, metric)
        log.info(f"A/B test created: {test_id} ({metric})")
        return {"ok": True, "test_id": test_id, "variant_a": variant_a,
                "variant_b": variant_b, "metric": metric}

    def get_ab_tests(self) -> dict:
        """Return all A/B tests with their current results."""
        tests = self.strategy.strategy.get("ab_tests", [])
        return {"ok": True, "tests": tests, "count": len(tests)}

    def update_schedule(self, day: str, tasks: list) -> dict:
        """Replace a day's task list in the content schedule."""
        try:
            self.strategy.update_schedule(day, tasks)
            return {"ok": True, "day": day.lower(), "tasks": tasks}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    def update_account(self, platform: str, **kwargs) -> dict:
        """Update arbitrary fields on a platform account record (e.g. revenue_total for Ko-fi)."""
        if platform not in IdentityManager.PLATFORMS:
            return {"ok": False, "error": f"Unknown platform '{platform}'"}
        self.identity.update_account(platform, **kwargs)
        log.info(f"Account updated: {platform} {list(kwargs.keys())}")
        return {"ok": True, "platform": platform, "updated": list(kwargs.keys())}

    def kofi_revenue_update(self, amount: float) -> dict:
        """Manually record Ko-fi revenue (no API — update from dashboard value)."""
        self.identity.update_account("kofi", revenue_total=amount)
        self.analytics.update_revenue("kofi", amount)
        log.info(f"Ko-fi revenue updated: ${amount:.2f}")
        return {"ok": True, "platform": "kofi", "amount": amount,
                "total_mrr": self.analytics.data.get("total_mrr", 0)}

    def purge_exhausted_tasks(self, max_retries: int = 3) -> dict:
        """Permanently remove failed tasks that exceeded max_retries."""
        count = self.strategy.purge_exhausted_tasks(max_retries)
        return {"ok": True, "purged": count}

    def platform_summary(self) -> dict:
        """Combined health + analytics snapshot for all tracked platforms."""
        health = self.identity.health_check_all()
        analytics = {}
        for platform in ["github", "reddit", "gumroad", "devto"]:
            handler = self.publisher._get_handler(platform)
            if handler:
                try:
                    data = handler.get_analytics()
                    if data:
                        analytics[platform] = data
                except Exception as e:
                    log.debug(f"platform_summary analytics error {platform}: {e}")
        s = self.strategy.strategy
        return {
            "health": health,
            "analytics": analytics,
            "revenue": self.analytics.data,
            "queue": self.strategy.get_queue_stats(),
            "monthly_goal": s.get("monthly_goal"),
            "weekly_focus": s.get("weekly_focus", []),
            "today_tasks": self.strategy.today_tasks(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def update_health(self) -> dict:
        """Ping each platform API to refresh health status in the registry."""
        now_iso = datetime.now(timezone.utc).isoformat()
        results = {}
        # GitHub — verify token still valid
        gh = GitHubHandler(self.identity.get_credentials("github"))
        if gh.token:
            try:
                r = requests.get("https://api.github.com/user", headers=gh._headers, timeout=8)
                health = "ok" if r.ok else "error"
            except requests.RequestException:
                health = "error"
            self.identity.update_account("github", health=health, last_health_check=now_iso)
            results["github"] = health
        # Dev.to — verify API key
        devto = DevToHandler(self.identity.get_credentials("devto"))
        if devto.api_key:
            try:
                r = requests.get("https://dev.to/api/users/me", headers=devto._headers, timeout=8)
                health = "ok" if r.ok else "error"
            except requests.RequestException:
                health = "error"
            self.identity.update_account("devto", health=health, last_health_check=now_iso)
            results["devto"] = health
        # Reddit — verify credentials via RedditHandler
        reddit = RedditHandler(self.identity.get_credentials("reddit"))
        if reddit._reddit is not None:
            try:
                reddit._reddit.user.me()
                health = "ok"
            except Exception:
                health = "error"
            self.identity.update_account("reddit", health=health, last_health_check=now_iso)
            results["reddit"] = health
        elif get_secret("REDDIT_CLIENT_ID"):
            # Credentials present but praw not installed
            self.identity.update_account("reddit", health="unknown", last_health_check=now_iso)
            results["reddit"] = "unknown"
        # Gumroad — verify access token
        gumroad = GumroadHandler(self.identity.get_credentials("gumroad"))
        if gumroad.token:
            try:
                r = requests.get("https://api.gumroad.com/v2/user",
                                 headers={"Authorization": f"Bearer {gumroad.token}"}, timeout=8)
                health = "ok" if r.ok else "error"
            except requests.RequestException:
                health = "error"
            self.identity.update_account("gumroad", health=health, last_health_check=now_iso)
            results["gumroad"] = health
        else:
            self.identity.update_account("gumroad", health="no_credentials", last_health_check=now_iso)
            results["gumroad"] = "no_credentials"

        # Mark remaining platforms with no credentials
        for platform in ["kofi", "twitter", "linkedin", "producthunt",
                         "hackernews", "hashnode", "mastodon", "substack"]:
            if platform not in results:
                creds = self.identity.get_credentials(platform)
                health = "no_credentials" if not creds else "unknown"
                self.identity.update_account(platform, health=health, last_health_check=now_iso)
                results[platform] = health

        log.info(f"Health update complete: {results}")
        return results


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="daemon",
                    choices=["daemon", "once", "status", "health", "queue",
                             "publish", "publish-direct", "enqueue", "analytics", "revenue",
                             "update-health", "retry-failed", "clear-queue",
                             "preview", "credentials", "remove-task",
                             "platform-summary", "set-goal", "set-focus", "ab-result",
                             "ab-create", "ab-tests", "update-schedule", "update-account",
                             "purge-exhausted", "kofi-revenue",
                             "respond", "get-strategy", "schedule-today"])
    ap.add_argument("--platform", default=None)
    ap.add_argument("--topic", default=None)
    ap.add_argument("--type", dest="content_type", default="post",
                    help="Content type (post, article, thread)")
    ap.add_argument("--detail", action="store_true", help="Show full queue task details")
    ap.add_argument("--task", default=None, help="source_task name for remove-task")
    ap.add_argument("--content", default=None, help="Pre-written content for publish-direct")
    ap.add_argument("--goal", default=None, help="Monthly goal string for set-goal")
    ap.add_argument("--focus", nargs="+", default=None, help="Weekly focus items for set-focus")
    ap.add_argument("--test-id", default=None, help="A/B test ID for ab-result")
    ap.add_argument("--variant", default=None, help="A/B test variant ('a' or 'b') for ab-result")
    ap.add_argument("--value", type=float, default=1.0, help="Measurement value for ab-result")
    ap.add_argument("--variant-a", default=None, help="Variant A description for ab-create")
    ap.add_argument("--variant-b", default=None, help="Variant B description for ab-create")
    ap.add_argument("--metric", default=None, help="Metric to track for ab-create (e.g. clicks)")
    ap.add_argument("--day", default=None, help="Day of week for update-schedule")
    ap.add_argument("--tasks", nargs="+", default=None, help="Task names for update-schedule")
    ap.add_argument("--field", nargs="+", default=None,
                    help="key=value pairs for update-account (e.g. username=alii)")
    ap.add_argument("--amount", type=float, default=None, help="Revenue amount for kofi-revenue")
    ap.add_argument("--max-retries", type=int, default=3, help="Retry threshold for purge-exhausted")
    ap.add_argument("--comment-id", default=None, help="Comment ID for respond command")
    ap.add_argument("--text", default=None, help="Reply text for respond command")
    args = ap.parse_args()

    agent = AccountAgent()

    if args.cmd == "once":
        agent.run_once()
    elif args.cmd == "status":
        print(json.dumps(agent.status(), indent=2))
    elif args.cmd == "health":
        print(json.dumps(agent.identity.health_check_all(), indent=2))
    elif args.cmd == "update-health":
        print(json.dumps(agent.update_health(), indent=2))
    elif args.cmd == "queue":
        if args.detail:
            print(json.dumps(agent.get_queue_detail(), indent=2))
        else:
            print(json.dumps(agent.get_queue_status(), indent=2))
    elif args.cmd == "analytics":
        print(json.dumps(agent.get_analytics(), indent=2))
    elif args.cmd == "revenue":
        print(json.dumps(agent.run_revenue_check(), indent=2))
    elif args.cmd == "publish":
        if not args.platform or not args.topic:
            ap.error("--platform and --topic required for publish")
        print(json.dumps(agent.publish_now(args.platform, args.topic, args.content_type), indent=2))
    elif args.cmd == "enqueue":
        if not args.platform or not args.topic:
            ap.error("--platform and --topic required for enqueue")
        print(json.dumps(agent.enqueue_content(args.platform, args.topic, args.content_type), indent=2))
    elif args.cmd == "preview":
        if not args.platform or not args.topic:
            ap.error("--platform and --topic required for preview")
        print(json.dumps(agent.preview_content(args.platform, args.topic, args.content_type), indent=2))
    elif args.cmd == "credentials":
        print(json.dumps(agent.credentials_status(), indent=2))
    elif args.cmd == "remove-task":
        if not args.task:
            ap.error("--task required for remove-task")
        print(json.dumps(agent.remove_task(args.task), indent=2))
    elif args.cmd == "retry-failed":
        count = agent.retry_failed_tasks()
        print(json.dumps({"retried": count}, indent=2))
    elif args.cmd == "clear-queue":
        count = agent.clear_completed_tasks()
        print(json.dumps({"cleared": count}, indent=2))
    elif args.cmd == "publish-direct":
        if not args.platform or not args.content:
            ap.error("--platform and --content required for publish-direct")
        print(json.dumps(agent.publish_direct(args.platform, args.content), indent=2))
    elif args.cmd == "platform-summary":
        print(json.dumps(agent.platform_summary(), indent=2))
    elif args.cmd == "set-goal":
        if not args.goal:
            ap.error("--goal required for set-goal")
        print(json.dumps(agent.set_monthly_goal(args.goal), indent=2))
    elif args.cmd == "set-focus":
        if not args.focus:
            ap.error("--focus required for set-focus")
        print(json.dumps(agent.set_weekly_focus(args.focus), indent=2))
    elif args.cmd == "ab-result":
        if not args.test_id or not args.variant:
            ap.error("--test-id and --variant required for ab-result")
        print(json.dumps(agent.record_ab_result(args.test_id, args.variant, args.value), indent=2))
    elif args.cmd == "ab-create":
        if not args.variant_a or not args.variant_b or not args.metric:
            ap.error("--variant-a, --variant-b, and --metric required for ab-create")
        print(json.dumps(agent.add_ab_test(args.variant_a, args.variant_b, args.metric), indent=2))
    elif args.cmd == "ab-tests":
        print(json.dumps(agent.get_ab_tests(), indent=2))
    elif args.cmd == "update-schedule":
        if not args.day or not args.tasks:
            ap.error("--day and --tasks required for update-schedule")
        print(json.dumps(agent.update_schedule(args.day, args.tasks), indent=2))
    elif args.cmd == "update-account":
        if not args.platform or not args.field:
            ap.error("--platform and --field (key=value ...) required for update-account")
        kwargs = {}
        for item in args.field:
            if "=" not in item:
                ap.error(f"--field items must be key=value, got: {item!r}")
            k, v = item.split("=", 1)
            kwargs[k] = v
        print(json.dumps(agent.update_account(args.platform, **kwargs), indent=2))
    elif args.cmd == "purge-exhausted":
        print(json.dumps(agent.purge_exhausted_tasks(args.max_retries), indent=2))
    elif args.cmd == "kofi-revenue":
        if args.amount is None:
            ap.error("--amount required for kofi-revenue")
        print(json.dumps(agent.kofi_revenue_update(args.amount), indent=2))
    elif args.cmd == "respond":
        if not args.platform or not args.comment_id or not args.text:
            ap.error("--platform, --comment-id, and --text required for respond")
        print(json.dumps(agent.respond_to_comment(args.platform, args.comment_id, args.text), indent=2))
    elif args.cmd == "get-strategy":
        print(json.dumps(agent.get_strategy(), indent=2))
    elif args.cmd == "schedule-today":
        print(json.dumps(agent.schedule_today(), indent=2))
    else:
        agent.run_daemon()


if __name__ == "__main__":
    main()
