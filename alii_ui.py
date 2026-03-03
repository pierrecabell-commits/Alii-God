import chainlit as cl
import json
import aiohttp
import time
import logging

logger = logging.getLogger(__name__)

try:
    from alii_model_router import AliiModelRouter
    router = AliiModelRouter()
except Exception as _e:
    logger.error("AliiModelRouter init failed: %s", _e)
    router = None

WELCOME_MSG = (
    "**Alii OS // System Online**\n"
    "_Distributed Intelligence Mesh Active_\n\n"
    "Alii is ready.\n"
)

def classify_task(prompt: str) -> str:
    p = (prompt or "").lower()
    if any(k in p for k in ["code", "python", "script", "build", "refactor"]):
        return "code"
    if any(k in p for k in ["analyze", "data", "why", "how"]):
        return "analysis"
    if any(k in p for k in ["plan", "future", "strategy", "architecture"]):
        return "planning"
    if len(prompt) < 50 and "?" not in prompt:
        return "quick_reply"
    return "default"

@cl.on_chat_start
async def start_chat():
    try:
        cl.user_session.set("router", router)
        await cl.Message(content=WELCOME_MSG, author="Alii").send()
    except Exception as e:
        logger.error("start_chat error: %s", e)

@cl.on_message
async def main(message: cl.Message):
    router_obj = cl.user_session.get("router") or router
    if router_obj is None:
        await cl.Message(content="_[System Error: Router unavailable. Check Ollama.]_", author="Alii").send()
        return
    task_type = classify_task(message.content)

    async with cl.Step(name="Neural Router", type="tool") as step:
        step.input = "Task Analysis: " + task_type
        model = router_obj.select_model(task_type)
        step.output = "Selected node: " + str(model)

    msg = cl.Message(content="", author="Alii")
    await msg.send()

    payload = {"model": model, "prompt": message.content, "stream": True}

    start_time = time.time()
    chunks = 0

    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(router_obj.base_url + "/api/generate", json=payload) as resp:
                if resp.status != 200:
                    await msg.stream_token("\n_Neural connection failed._")
                    await msg.update()
                    return

                async for raw in resp.content:
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "response" in data:
                        chunks += 1
                        await msg.stream_token(data["response"])

                    if data.get("done"):
                        break

    except Exception as e:
        await msg.stream_token("\n_[System Fault: " + str(e) + "]_")

    elapsed = max(time.time() - start_time, 1e-6)
    cps = chunks / elapsed
    footer = "\n\n---\n[Node: " + str(model) + " // " + str(chunks) + " chunks // " + str(round(cps, 1)) + " c/s]"
    await msg.stream_token(footer)
    await msg.update()
