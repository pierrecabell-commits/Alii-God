#!/usr/bin/env python3
"""
Account Agent — Autonomous platform account management + content publishing.
7 subsystems: Identity, Content, Strategy, Publisher, Analytics, Compliance, Autonomy.
Platforms: GitHub, Ko-fi, Gumroad, Reddit (full); Twitter, LinkedIn, ProductHunt (partial).
"""

import asyncio, json, logging, os, re, subprocess, sys, time, hashlib, secrets, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import requests

# ---------------------------------------------------------------------------
# Vault integration
# ---------------------------------------------------------------------------
sys.path.insert(0, "/home/avalii/moltbot")
try:
    from vault.vault_client import get_secret
except ImportError:
    def get_secret(k, d=None): return os.getenv(k, d)

# ---------------------------------------------------------------------------
# Constants — file paths
# ---------------------------------------------------------------------------
WORKDIR         = Path("/home/avalii/moltbot")
ACCOUNTS_FILE   = WORKDIR / "data" / "accounts_registry.json"
REVENUE_FILE    = WORKDIR / "data" / "revenue_live.json"
PERSONAL_INFO   = WORKDIR / "data" / "personal_info_patterns.json"
CONTENT_QUEUE   = WORKDIR / "data" / "content_queue.json"
STRATEGY_FILE   = WORKDIR / "data" / "growth_strategy.json"
LOG_FILE        = WORKDIR / "logs" / "accounts_status.log"

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
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps(self.registry, indent=2))
        ACCOUNTS_FILE.chmod(0o600)

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
                    if any(preferred in m for m in models):
                        return preferred
                if models:
                    return models[0]
        except (requests.RequestException, ValueError, KeyError):
            pass
        return "llama3.2:3b"

    def generate(self, topic: str, platform: str, content_type: str = "post") -> str:
        voice = PLATFORM_VOICES.get(platform, "clear, professional, authentic")
        prompt = (f"Write a {content_type} for {platform} about: {topic}\n"
                  f"Voice: {voice}\n"
                  f"Platform: {platform}\n"
                  f"Be genuine, helpful, not promotional. Max 500 words.")
        try:
            r = requests.post("http://localhost:11434/api/generate",
                              json={"model": self.model, "prompt": prompt, "stream": False},
                              timeout=60)
            if r.ok:
                return r.json().get("response", "").strip()
        except Exception as e:
            log.warning(f"ContentEngine generate error: {e}")
        return f"[Content generation failed for {platform}: {topic}]"

    def generate_response(self, platform: str, original_comment: str, context: str = "") -> str:
        voice = PLATFORM_VOICES.get(platform, "helpful, authentic")
        prompt = (f"Write a reply on {platform} to this comment:\n\"{original_comment}\"\n"
                  f"Context: {context}\nVoice: {voice}\nBe genuine, add value. Max 200 words.")
        try:
            r = requests.post("http://localhost:11434/api/generate",
                              json={"model": self.model, "prompt": prompt, "stream": False},
                              timeout=45)
            if r.ok:
                return r.json().get("response", "").strip()
        except (requests.RequestException, ValueError, KeyError):
            pass
        return ""

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
        STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
        STRATEGY_FILE.write_text(json.dumps(self.strategy, indent=2))

    def today_tasks(self) -> list:
        day = datetime.now().strftime("%A").lower()
        return self.strategy.get("content_schedule", {}).get(day, [])

    def add_ab_test(self, variant_a: str, variant_b: str, metric: str):
        test = {"id": secrets.token_hex(4), "variant_a": variant_a,
                "variant_b": variant_b, "metric": metric,
                "started": datetime.now(timezone.utc).isoformat(),
                "results": {"a": 0, "b": 0}}
        self.strategy["ab_tests"].append(test)
        self.save()
        return test["id"]

    def add_to_queue(self, task: dict):
        queue = self.strategy.get("daily_queue", [])
        queue.append({**task, "added_at": datetime.now(timezone.utc).isoformat()})
        self.strategy["daily_queue"] = queue[-50:]  # keep last 50
        self.save()

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
        REVENUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        REVENUE_FILE.write_text(json.dumps(self.data, indent=2))

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
                milestones_file.write_text(json.dumps(reached))
                msg = f"MILESTONE: {name} reached! MRR=${mrr:.2f}"
                log.info(msg)
                self._ntfy(msg, title="Revenue Milestone!")

    def _ntfy(self, msg: str, title: str = "Alii Analytics"):
        try:
            requests.post("http://localhost:8080/alii-revenue",
                          data=msg.encode(), headers={"Title": title}, timeout=3)
        except requests.RequestException:
            pass

    def collect_all(self, identity: 'IdentityManager') -> dict:
        """Pull revenue from all platforms. Called every 6h."""
        results = {}

        # GitHub Sponsors
        gh_token = get_secret("GITHUB_TOKEN")
        if gh_token:
            try:
                r = requests.get("https://api.github.com/user/sponsorships/as_maintainer",
                                 headers={"Authorization": f"token {gh_token}",
                                          "Accept": "application/vnd.github+json"}, timeout=10)
                if r.ok:
                    sponsors = r.json()
                    monthly = sum(s.get("tier", {}).get("monthly_price_in_dollars", 0)
                                  for s in sponsors if isinstance(sponsors, list))
                    self.update_revenue("github_sponsors", monthly)
                    results["github_sponsors"] = monthly
            except Exception as e:
                log.warning(f"GitHub Sponsors fetch error: {e}")

        # Ko-fi (read from accounts registry — no public API)
        kofi_total = identity.get_account("kofi").get("revenue_total", 0)
        if kofi_total:
            self.update_revenue("kofi", kofi_total)
            results["kofi"] = kofi_total

        # Gumroad
        gumroad_token = get_secret("GUMROAD_ACCESS_TOKEN")
        if gumroad_token:
            try:
                r = requests.get("https://api.gumroad.com/v2/sales",
                                 params={"access_token": gumroad_token}, timeout=10)
                if r.ok:
                    sales = r.json().get("sales", [])
                    total = sum(float(s.get("price", 0)) / 100 for s in sales)
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
        PERSONAL_INFO.parent.mkdir(parents=True, exist_ok=True)
        PERSONAL_INFO.write_text(json.dumps(self.patterns, indent=2))

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
        """Create a GitHub issue or gist as a post."""
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
                             headers={**self._headers,
                                      "Accept": "application/vnd.github.v3+json"},
                             timeout=10)
            if r.ok and isinstance(r.json(), list):
                return sum(s.get("tier", {}).get("monthly_price_in_dollars", 0)
                           for s in r.json())
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
        """Ko-fi posts done via API if token available."""
        if not self.token:
            return {"ok": False, "error": "Ko-fi API not available — post manually at ko-fi.com"}
        return {"ok": False, "error": "Ko-fi REST API not publicly available"}

    def get_analytics(self) -> dict:
        return {"username": self.username, "note": "Ko-fi analytics via dashboard only"}

    def get_revenue(self) -> float:
        return 0.0  # Pulled from Ko-fi webhook or manual entry

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

    def post_content(self, content: str, title: str = "New Post", price: int = 0, **kwargs) -> dict:
        """Create a Gumroad product/post."""
        if not self.token:
            return {"ok": False, "error": "No Gumroad token"}
        try:
            r = requests.post("https://api.gumroad.com/v2/products",
                              data={"access_token": self.token, "name": title,
                                    "description": content, "price": price * 100},
                              timeout=10)
            d = r.json()
            return {"ok": d.get("success"), "url": d.get("product", {}).get("url")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_analytics(self) -> dict:
        if not self.token:
            return {}
        try:
            r = requests.get("https://api.gumroad.com/v2/products",
                             params={"access_token": self.token}, timeout=10)
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
        self.client_id     = get_secret("REDDIT_CLIENT_ID", "")
        self.client_secret = get_secret("REDDIT_CLIENT_SECRET", "")
        self.username      = get_secret("REDDIT_USERNAME", "")
        self.password      = get_secret("REDDIT_PASSWORD", "")
        self._reddit = None
        if self.client_id and self.client_secret and self.username and self.password:
            try:
                import praw
                self._reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    username=self.username,
                    password=self.password,
                    user_agent="Alii Agent v1.0",
                )
            except Exception as e:
                log.warning(f"Reddit init error: {e}")

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
        return 0.0  # Reddit has no direct monetization

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
            return handler.post_content(safe_text, **kwargs)
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
        }
        cls = handlers.get(platform)
        if cls:
            return cls(self.identity.get_credentials(platform))
        return None

# ===========================================================================
# SUBSYSTEM 7: AutonomyEngine
# ===========================================================================
class AutonomyEngine:
    def __init__(self, identity: IdentityManager, content: ContentEngine,
                 strategy: StrategyEngine, publisher: PublisherEngine,
                 analytics: AnalyticsEngine, compliance: ComplianceEngine):
        self.identity   = identity
        self.content    = content
        self.strategy   = strategy
        self.publisher  = publisher
        self.analytics  = analytics
        self.compliance = compliance
        self._last_revenue_check = 0

    def notify_owner(self, message: str, title: str = "Alii Accounts"):
        """Notify via ntfy and log."""
        log.info(f"NOTIFY: {message}")
        try:
            requests.post("http://localhost:8080/alii-accounts",
                          data=message.encode(),
                          headers={"Title": title}, timeout=3)
        except requests.RequestException:
            pass

    def run_daily_cycle(self):
        """Called once daily at 08:00 by timer."""
        log.info("Running daily autonomy cycle")
        today_tasks = self.strategy.today_tasks()
        log.info(f"Today's tasks: {today_tasks}")

        # Revenue check every 6h
        now = time.time()
        if now - self._last_revenue_check > 21600:
            try:
                results = self.analytics.collect_all(self.identity)
                log.info(f"Revenue collected: {results}")
                self._last_revenue_check = now
            except Exception as e:
                log.warning(f"Revenue collection error: {e}")

        # Health check all accounts
        health = self.identity.health_check_all()
        unhealthy = [p for p, h in health.items() if h.get("health") == "error"]
        if unhealthy:
            self.notify_owner(f"Accounts needing attention: {', '.join(unhealthy)}",
                              "Account Health Alert")

        # Process content queue
        queue = self.strategy.strategy.get("daily_queue", [])
        processed = []
        for task in queue[:3]:  # max 3 tasks per day
            if task.get("status") == "pending":
                platform = task.get("platform", "")
                topic    = task.get("topic", "")
                if platform and topic:
                    content = self.content.generate(topic, platform)
                    safe, violations = self.compliance.is_safe(content)
                    if not safe:
                        log.warning(f"Content blocked for {platform}: {violations}")
                        content = self.compliance.filter(content)
                    result = self.publisher.post(platform, content)
                    task["status"] = "done" if result.get("ok") else "failed"
                    task["result"] = result
                    processed.append(task)

        if processed:
            self.strategy.save()
            log.info(f"Processed {len(processed)} queued tasks")

    def request_approval(self, action: str, details: dict):
        """Request owner approval for sensitive actions (new accounts, first posts)."""
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

    def run_daemon(self):
        """Run as daemon — daily cycle at 08:00."""
        log.info("AccountAgent daemon starting")
        while True:
            now = datetime.now()
            # Run at 08:00 daily
            if now.hour == 8 and now.minute == 0:
                try:
                    self.run_once()
                except Exception as e:
                    log.error(f"Daily cycle error: {e}")
                time.sleep(60)  # avoid double-trigger
            time.sleep(30)

    def status(self) -> dict:
        return {
            "accounts": self.identity.health_check_all(),
            "revenue": self.analytics.data,
            "strategy_today": self.strategy.today_tasks(),
            "content_model": self.content.model,
            "queue_size": len(self.strategy.strategy.get("daily_queue", [])),
        }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="daemon",
                    choices=["daemon", "once", "status", "health"])
    args = ap.parse_args()

    agent = AccountAgent()

    if args.cmd == "once":
        agent.run_once()
    elif args.cmd == "status":
        print(json.dumps(agent.status(), indent=2))
    elif args.cmd == "health":
        print(json.dumps(agent.identity.health_check_all(), indent=2))
    else:
        agent.run_daemon()


if __name__ == "__main__":
    main()
