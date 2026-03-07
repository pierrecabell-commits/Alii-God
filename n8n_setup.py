#!/usr/bin/env python3
"""
Create n8n starter workflows via REST API.
Workflows:
  1. Daily software scout (GitHub trending AI repos)
  2. Health monitor (ping all services every 15 min)
  3. Security agent trigger (daily run)
"""
import json
import time
import urllib.request
import urllib.error

N8N_BASE = "http://localhost:5678/api/v1"


def _get_api_key() -> str:
    import os
    key = os.environ.get("N8N_API_KEY", "")
    if not key:
        try:
            with open("/home/avalii/moltbot/.env") as f:
                for line in f:
                    if line.startswith("N8N_API_KEY="):
                        key = line.strip().split("=", 1)[1]
        except Exception:
            pass
    return key


def n8n_request(method: str, path: str, data: dict = None) -> dict:
    url = f"{N8N_BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    api_key = _get_api_key()
    if api_key:
        req.add_header("X-N8N-API-KEY", api_key)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code} for {method} {path}: {body[:200]}")
        return {}


# ── Workflow 1: Daily Software Scout ─────────────────────────────────────────

SOFTWARE_SCOUT_WORKFLOW = {
    "name": "Alii Daily Software Scout",
    "active": True,
    "nodes": [
        {
            "id": "schedule1",
            "name": "Daily Schedule",
            "type": "n8n-nodes-base.scheduleTrigger",
            "position": [240, 300],
            "parameters": {
                "rule": {"interval": [{"field": "hours", "minutesInterval": 24}]}
            },
            "typeVersion": 1.2,
        },
        {
            "id": "github1",
            "name": "GitHub Trending AI Repos",
            "type": "n8n-nodes-base.httpRequest",
            "position": [460, 300],
            "parameters": {
                "method": "GET",
                "url": "https://api.github.com/search/repositories",
                "sendQuery": True,
                "queryParameters": {
                    "parameters": [
                        {"name": "q", "value": "topic:ai topic:agent pushed:>2026-02-20 stars:>100"},
                        {"name": "sort", "value": "stars"},
                        {"name": "per_page", "value": "10"},
                    ]
                },
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Accept", "value": "application/vnd.github.v3+json"},
                        {"name": "User-Agent", "value": "AliiBot/1.0"},
                    ]
                },
            },
            "typeVersion": 4.2,
        },
        {
            "id": "ntfy1",
            "name": "Send ntfy Digest",
            "type": "n8n-nodes-base.httpRequest",
            "position": [680, 300],
            "parameters": {
                "method": "POST",
                "url": "http://host.docker.internal:8080/alii-alerts",
                "sendBody": True,
                "bodyParameters": {
                    "parameters": [
                        {"name": "Title", "value": "Alii Software Scout"},
                    ]
                },
                "body": "=={{ $json.items.slice(0,3).map(r => r.full_name + ' ⭐' + r.stargazers_count).join('\\n') }}",
            },
            "typeVersion": 4.2,
        },
    ],
    "connections": {
        "Daily Schedule": {"main": [[{"node": "GitHub Trending AI Repos", "type": "main", "index": 0}]]},
        "GitHub Trending AI Repos": {"main": [[{"node": "Send ntfy Digest", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"},
}

# ── Workflow 2: Service Health Monitor ───────────────────────────────────────

HEALTH_MONITOR_WORKFLOW = {
    "name": "Alii Service Health Monitor",
    "active": True,
    "nodes": [
        {
            "id": "schedule2",
            "name": "Every 15 Minutes",
            "type": "n8n-nodes-base.scheduleTrigger",
            "position": [240, 300],
            "parameters": {
                "rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}
            },
            "typeVersion": 1.2,
        },
        {
            "id": "qdrant_check",
            "name": "Check Qdrant",
            "type": "n8n-nodes-base.httpRequest",
            "position": [460, 200],
            "parameters": {
                "method": "GET",
                "url": "http://host.docker.internal:6333/healthz",
                "options": {"timeout": 5000},
            },
            "typeVersion": 4.2,
        },
        {
            "id": "litellm_check",
            "name": "Check LiteLLM",
            "type": "n8n-nodes-base.httpRequest",
            "position": [460, 300],
            "parameters": {
                "method": "GET",
                "url": "http://host.docker.internal:4000/health",
                "options": {"timeout": 5000, "allowUnauthorizedCerts": True},
            },
            "typeVersion": 4.2,
        },
        {
            "id": "ollama_check",
            "name": "Check Ollama",
            "type": "n8n-nodes-base.httpRequest",
            "position": [460, 400],
            "parameters": {
                "method": "GET",
                "url": "http://host.docker.internal:11434/api/tags",
                "options": {"timeout": 5000},
            },
            "typeVersion": 4.2,
        },
    ],
    "connections": {
        "Every 15 Minutes": {
            "main": [[
                {"node": "Check Qdrant", "type": "main", "index": 0},
                {"node": "Check LiteLLM", "type": "main", "index": 0},
                {"node": "Check Ollama", "type": "main", "index": 0},
            ]]
        },
    },
    "settings": {"executionOrder": "v1"},
}

# ── Workflow 3: Security Agent Trigger ────────────────────────────────────────

SECURITY_TRIGGER_WORKFLOW = {
    "name": "Alii Security Agent Trigger",
    "active": True,
    "nodes": [
        {
            "id": "schedule3",
            "name": "Daily 03:00",
            "type": "n8n-nodes-base.scheduleTrigger",
            "position": [240, 300],
            "parameters": {
                "rule": {
                    "interval": [{"field": "cronExpression", "expression": "0 3 * * *"}]
                }
            },
            "typeVersion": 1.2,
        },
        {
            "id": "security_run",
            "name": "Run Security Agent",
            "type": "n8n-nodes-base.executeCommand",
            "position": [460, 300],
            "parameters": {
                "command": "python3 /home/avalii/moltbot/security_agent.py --mode full 2>&1 | tail -5"
            },
            "typeVersion": 1,
        },
    ],
    "connections": {
        "Daily 03:00": {"main": [[{"node": "Run Security Agent", "type": "main", "index": 0}]]},
    },
    "settings": {"executionOrder": "v1"},
}


def create_workflow(workflow: dict) -> bool:
    print(f"Creating workflow: {workflow['name']}...")
    result = n8n_request("POST", "/workflows", workflow)
    if result.get("id"):
        print(f"  Created: {result['name']} (id={result['id']})")
        return True
    print(f"  Failed: {result}")
    return False


def list_workflows() -> list:
    result = n8n_request("GET", "/workflows")
    return result.get("data", [])


def main():
    print("=== n8n Workflow Setup ===")
    # Wait for n8n to be fully ready
    for _ in range(5):
        try:
            urllib.request.urlopen("http://localhost:5678/healthz", timeout=3)
            break
        except Exception:
            time.sleep(2)

    # Check existing workflows
    existing = {w["name"] for w in list_workflows()}
    print(f"Existing workflows: {existing}")

    workflows = [
        SOFTWARE_SCOUT_WORKFLOW,
        HEALTH_MONITOR_WORKFLOW,
        SECURITY_TRIGGER_WORKFLOW,
    ]

    created = 0
    for wf in workflows:
        if wf["name"] in existing:
            print(f"  Skipping (already exists): {wf['name']}")
        else:
            if create_workflow(wf):
                created += 1

    print(f"=== Created {created} workflow(s) ===")


if __name__ == "__main__":
    main()
