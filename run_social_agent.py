#!/usr/bin/env python3
"""Daemon wrapper for SocialAgent — runs content flywheel and cross-platform sync."""

import sys, os, time, logging, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agents.social_agent import SocialAgent

LOG_FILE = Path("/home/avalii/moltbot/logs/social_agent.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [social_agent] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.social_agent_runner")

NTFY_URL  = "https://ntfy.sh/alii-precision"
INTERVAL  = 3600  # 1 hour — check for new content/posts


def _ntfy(title: str, msg: str, priority: str = "default"):
    try:
        req = urllib.request.Request(
            NTFY_URL, data=msg.encode(),
            headers={"Title": title, "Priority": priority}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("ntfy send failed: %s", e)


def run_once(agent: SocialAgent):
    sync = agent.cross_platform_sync()
    log.info("Cross-platform sync: %s", sync.get("flywheel_status"))


if __name__ == "__main__":
    log.info("Social Agent daemon started")
    agent = SocialAgent()
    # On start: ensure brand kit and content calendar exist
    try:
        agent.generate_brand_kit()
        agent.generate_content_calendar()
        _ntfy("Alii Social Agent", "Brand kit and content calendar ready.", "low")
    except Exception as exc:
        log.warning("Init error: %s", exc)

    while True:
        try:
            run_once(agent)
        except Exception as exc:
            log.exception("Social agent run error: %s", exc)
        log.info("Sleeping %dm until next run", INTERVAL // 60)
        time.sleep(INTERVAL)
