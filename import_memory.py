from datetime import timezone
#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

CONVERSATION_DATA = {
  "source": "Perplexity_AI_Session",
  "date": "2026-02-03",
  "topic": "Building Alii Local AI System",
  "key_achievements": [
    "Installed AliiLLM 0.15.4 on Alii Precision server",
    "Downloaded llama3.2:3b and qwen2.5:3b models",
    "Created memory system at ~/Alii/memory/",
    "Built chat.py basic interface",
    "Built chat_advanced.py with code execution",
    "Built Alii_with_memory.py with full memory integration",
    "Overcame iTerm2 MCP tool limitations using base64 encoding",
    "System now operational with persistent memory"
  ],
  "technical_details": [
    "Server: aliirecision (Alii Precision)",
    "User: avalii (Pierre)",
    "Python virtual environment: ~/Alii/venv",
    "AliiLLM models: llama3.2:3b (primary), qwen2.5:3b (backup)",
    "Memory storage: JSON files in ~/Alii/memory/",
    "Code execution: Python and bash support with tempfile",
    "System prompt: Includes user context and philosophy"
  ],
  "user_philosophy": [
    "Systems thinker who needs to understand how things connect",
    "Learns by doing - copy, paste, experiment workflow",
    "Values transparency over convenience",
    "Building Alii AI as self-evolving system",
    "Creating autonomous AI without outside permission",
    "Using recycled hardware to build powerful systems"
  ],
  "conversation_highlights": [
    {
      "query": "install AliiLLM",
      "result": "Successfully installed AliiLLM 0.15.4 using official script"
    },
    {
      "query": "download llama model",
      "result": "Downloaded llama3.2:3b (2.0GB) and qwen2.5:3b (1.9GB)"
    },
    {
      "query": "create memory system",
      "result": "Built JSON-based memory with categories: projects, context, facts, preferences"
    },
    {
      "query": "build chat interface",
      "result": "Created progressive versions: basic -> advanced -> memory-enabled"
    },
    {
      "query": "fix iTerm2 issues",
      "result": "Used base64 encoding to bypass shell escaping limitations"
    },
    {
      "query": "give Alii our chat history",
      "result": "Created memory import system with conversation summary"
    }
  ],
  "project_context": {
    "name": "Alii AI",
    "goal": "Build autonomous AI system from recycled hardware",
    "current_phase": "Local AI foundation with AliiLLM + Alii",
    "next_steps": "Expand capabilities, add web search, integrate with other systems",
    "philosophy": "Self-evolving AI that learns without external permission"
  }
}

def import_to_memory():
    memory_dir = Path("~/Alii/memory").expanduser()
    memory_file = memory_dir / "memories.json"

    if memory_file.exists():
        with open(memory_file) as f:
            memories = json.load(f)
    else:
        memories = {"user_preferences": {}, "projects": [], "context": [], "facts": []}

    memories["projects"].append({
        "content": f"Project: {CONVERSATION_DATA['project_context']['name']} - {CONVERSATION_DATA['project_context']['goal']}",
        "timestamp": datetime.now().isoformat(),
        "metadata": {"source": "perplexity_import", "phase": CONVERSATION_DATA['project_context']['current_phase']}
    })

    for philosophy in CONVERSATION_DATA["user_philosophy"]:
        memories["facts"].append({
            "content": f"User belief: {philosophy}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"category": "philosophy", "source": "perplexity_import"}
        })

    for detail in CONVERSATION_DATA["technical_details"]:
        memories["facts"].append({
            "content": f"System: {detail}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"category": "technical", "source": "perplexity_import"}
        })

    for highlight in CONVERSATION_DATA["conversation_highlights"]:
        memories["context"].append({
            "content": f"Past session - Q: {highlight['query']} | Result: {highlight['result']}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"source": "perplexity_import"}
        })

    for achievement in CONVERSATION_DATA["key_achievements"]:
        memories["context"].append({
            "content": f"Achievement: {achievement}",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"source": "perplexity_import"}
        })

    with open(memory_file, "w") as f:
        json.dump(memories, f, indent=2)

    print(f"✓ Imported {len(CONVERSATION_DATA['key_achievements'])} achievements")
    print(f"✓ Imported {len(CONVERSATION_DATA['conversation_highlights'])} conversation highlights")
    print(f"✓ Imported {len(CONVERSATION_DATA['user_philosophy'])} philosophy points")
    print(f"✓ Imported {len(CONVERSATION_DATA['technical_details'])} technical details")
    print(f"\nMemory file updated: {memory_file}")
    print("\nAlii now has full context from our Perplexity session!")

if __name__ == "__main__":
    import_to_memory()
