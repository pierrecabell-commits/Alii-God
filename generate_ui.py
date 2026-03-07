code = """import chainlit as cl
import json
import aiohttp
import time
from alii_model_router import AliiModelRouter

router = AliiModelRouter()

WELCOME = \"\"\"**Alii OS // System Online**
_Distributed Intelligence Mesh Active_

My neural pathways are optimized for the cluster. I am ready to begin.

How can we change the world today?\"\"\"

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
    cl.user_session.set("router", router)
    await cl.Message(content=WELCOME, author="Alii").send()

@cl.on_message
async def main(message: cl.Message):
    router = cl.user_session.get("router")

    task_type = classify_task(message.content)

    async with cl.Step(name="Neural Router", type="tool") as step:
        step.input = f"Task Analysis: {task_type}"
        model = router.select_model(task_type)
        step.output = f"Selected optimal inference node: {model}"

    msg = cl.Message(content="", author="Alii")
    await msg.send()

    payload = {
        "model": model,
        "prompt": message.content,
        "stream": True,
    }

    start_time = time.time()
    token_chunks = 0

    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{router.base_url}/api/generate", json=payload) as response:
                if response.status != 200:
                    await msg.stream_token(f"\n_Neural connection failed. Node {model} unresponsive._")
                    return

                async for raw in response.content:
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "response" in 
                        token_chunks += 1
                        await msg.stream_token(data["response"])

                    if data.get("done"):
                        break

    except Exception as e:
        await msg.stream_token(f"\n_[System Fault: {str(e)}]_")

    elapsed = max(time.time() - start_time, 1e-6)
    tps = token_chunks / elapsed
    msg.content += f"\n\n---\n[Node: {model} // {token_chunks} chunks // {tps:.1f} c/s]"
    await msg.update()
"""
with open("/home/avalii/moltbot/alii_ui.py", "w", encoding="utf-8") as f:
    f.write(code)
