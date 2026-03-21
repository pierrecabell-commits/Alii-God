#!/usr/bin/env python3
"""Daemon wrapper for MoneyAgent — runs daily revenue reports and ntfy notifications."""

import sys, os, time, logging, urllib.request, urllib.error, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agents.money_agent import MoneyAgent

LOG_FILE = Path("/home/avalii/moltbot/logs/money_agent.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [money_agent] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.money_agent_runner")

NTFY_URL  = "https://ntfy.sh/alii-precision"
INTERVAL  = 86400  # 24 hours


def _ntfy(title: str, msg: str, priority: str = "default"):
    try:
        req = urllib.request.Request(
            NTFY_URL,
            data=msg.encode(),
            headers={"Title": title, "Priority": priority},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("ntfy send failed: %s", e)


def run_once():
    agent = MoneyAgent()
    report = agent.generate_daily_report()
    log.info("Daily report generated")
    _ntfy("Alii Money Report", report[:500], "default")
    # Generate OSS monetization guide if not done
    try:
        agent.write_oss_monetization_guide()
    except Exception:
        pass


if __name__ == "__main__":
    log.info("Money Agent daemon started")
    _ntfy("Alii Money Agent", "Revenue tracking daemon started.", "low")
    while True:
        try:
            run_once()
        except Exception as exc:
            log.exception("Money agent run error: %s", exc)
            _ntfy("Alii Money Agent ERROR", str(exc)[:200], "high")
        log.info("Sleeping %dh until next run", INTERVAL // 3600)
        time.sleep(INTERVAL)
