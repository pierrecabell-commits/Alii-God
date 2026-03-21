#!/usr/bin/env python3
"""
VisionClaw Bridge — Flask API on port 7030.

Routes image frames from the VisionClaw iOS app (Ray-Ban Meta glasses)
to the OpenClaw gateway at ws://127.0.0.1:18789.

Endpoints:
  POST /api/v1/vision/analyze  — analyze a single image frame
  GET  /api/v1/vision/health   — health check
"""

import os, sys, json, base64, logging, urllib.request, urllib.error, asyncio, time
from pathlib import Path
from datetime import datetime, timezone

WORKDIR   = Path("/home/avalii/moltbot")
LOG_FILE  = WORKDIR / "logs" / "visionclaw_bridge.log"
PORT      = 7030

OPENCLAW_WS_URL    = "ws://127.0.0.1:18789"
OPENCLAW_HTTP_URL  = "http://127.0.0.1:18789"
GATEWAY_TOKEN_FILE = Path("/home/avalii/Alii/alii_infrastructure.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [visionclaw] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("alii.visionclaw")


def _load_gateway_token() -> str:
    try:
        data = json.loads(GATEWAY_TOKEN_FILE.read_text())
        return data.get("gateway_token", "")
    except Exception:
        return os.environ.get("GATEWAY_TOKEN", "")


def _ntfy(title: str, msg: str, priority: str = "default"):
    try:
        req = urllib.request.Request(
            "https://ntfy.sh/alii-precision", data=msg.encode(),
            headers={"Title": title, "Priority": priority}, method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _analyze_via_openclaw(image_b64: str, prompt: str, context: str = "") -> dict:
    """
    Send image + prompt to OpenClaw gateway HTTP endpoint.
    OpenClaw accepts multimodal messages with base64 image content.
    """
    gateway_token = _load_gateway_token()

    messages = []
    if context:
        messages.append({"role": "user", "content": context})

    # Multimodal message with image
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_b64,
                }
            },
            {
                "type": "text",
                "text": prompt or "Describe what you see in this image. Be concise and focus on actionable details."
            }
        ]
    })

    payload = json.dumps({
        "messages": messages,
        "stream": False,
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gateway_token}",
    }

    try:
        req = urllib.request.Request(
            f"{OPENCLAW_HTTP_URL}/api/chat",
            data=payload, headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return {
                "success": True,
                "response": result.get("content") or result.get("message", {}).get("content", ""),
                "model": result.get("model", "openclaw"),
                "tokens_used": result.get("usage", {}).get("total_tokens", 0),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log.warning("OpenClaw HTTP %d: %s", e.code, body[:200])
        return {"success": False, "error": f"OpenClaw HTTP {e.code}: {body[:200]}"}
    except Exception as exc:
        log.error("OpenClaw request failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ── Flask app ──────────────────────────────────────────────────────────────────

try:
    from flask import Flask, request, jsonify
except ImportError:
    log.error("Flask not installed — run: pip install flask")
    sys.exit(1)

app = Flask("visionclaw_bridge")
_start_time = time.time()


@app.route("/api/v1/vision/health", methods=["GET"])
def health():
    uptime_s = int(time.time() - _start_time)
    return jsonify({
        "status": "ok",
        "service": "visionclaw-bridge",
        "uptime_seconds": uptime_s,
        "openclaw_url": OPENCLAW_HTTP_URL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/v1/vision/analyze", methods=["POST"])
def analyze():
    """
    Accept image frame from VisionClaw iOS app, forward to OpenClaw.

    Expected JSON body:
    {
        "image": "<base64-encoded JPEG>",
        "prompt": "What is happening here?",   // optional
        "context": "I am walking near...",     // optional conversation context
    }

    Or multipart form with 'image' file + optional 'prompt' field.
    """
    started = time.time()

    # Parse input — JSON or multipart
    image_b64 = None
    prompt = ""
    context = ""

    if request.is_json:
        data = request.get_json(silent=True) or {}
        image_b64 = data.get("image", "")
        prompt    = data.get("prompt", "")
        context   = data.get("context", "")
    else:
        # Multipart form upload
        if "image" in request.files:
            img_bytes = request.files["image"].read()
            image_b64 = base64.b64encode(img_bytes).decode()
        elif "image" in request.form:
            image_b64 = request.form["image"]
        prompt  = request.form.get("prompt", "")
        context = request.form.get("context", "")

    if not image_b64:
        return jsonify({"success": False, "error": "No image provided"}), 400

    # Strip data URI prefix if present (data:image/jpeg;base64,...)
    if "," in image_b64 and image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]

    log.info("Vision analyze — prompt=%r image_bytes=%d",
             prompt[:60] if prompt else "(none)",
             len(image_b64) * 3 // 4)

    result = _analyze_via_openclaw(image_b64, prompt, context)
    result["latency_ms"] = int((time.time() - started) * 1000)

    status_code = 200 if result.get("success") else 502
    return jsonify(result), status_code


@app.route("/api/v1/vision/stream", methods=["POST"])
def stream():
    """
    Accept continuous stream of frames (from wearable), process latest only.
    VisionClaw may POST multiple frames; we deduplicate by keeping latest.
    Returns same format as /analyze.
    """
    return analyze()


if __name__ == "__main__":
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log.info("VisionClaw bridge starting on port %d", PORT)
    _ntfy("VisionClaw Bridge", f"Starting on port {PORT} → OpenClaw at {OPENCLAW_HTTP_URL}", "low")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
