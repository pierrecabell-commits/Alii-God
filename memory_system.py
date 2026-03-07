from datetime import timezone
import json
from datetime import datetime
from pathlib import Path

class MemorySystem:
    def __init__(self, memory_dir="~/Alii/memory"):
        self.memory_dir = Path(memory_dir).expanduser()
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "memories.json"
        self.chat_history_file = self.memory_dir / "chat_history.json"
        self.load_memory()

    def load_memory(self):
        if self.memory_file.exists():
            with open(self.memory_file, r) as f:
                self.memories = json.load(f)
        else:
            self.memories = {"user_preferences": {}, "projects": [], "context": [], "facts": []}

    def save_memory(self):
        with open(self.memory_file, w) as f:
            json.dump(self.memories, f, indent=2)

    def add_memory(self, category, content, metadata=None):
        entry = {"content": content, "timestamp": datetime.now().isoformat(), "metadata": metadata or {}}
        if category in ["projects", "context", "facts"]:
            self.memories[category].append(entry)
        elif category == "user_preferences":
            self.memories[category].update(content)
        self.save_memory()
        return entry

    def import_chat_history(self, source, data):
        if not self.chat_history_file.exists():
            chat_data = {}
        else:
            with open(self.chat_history_file, r) as f:
                chat_data = json.load(f)
        chat_data[source] = {"imported_at": datetime.now().isoformat(), "conversations": data}
        with open(self.chat_history_file, w) as f:
            json.dump(chat_data, f, indent=2)
        return f"Imported {len(data)} conversations from {source}"

    def search_memory(self, query):
        results = []
        query_lower = query.lower()
        for category, items in self.memories.items():
            if isinstance(items, list):
                for item in items:
                    if query_lower in str(item).lower():
                        results.append({"category": category, "data": item})
        return results

    def get_context_summary(self):
        recent_context = self.memories["context"][-5:] if self.memories["context"] else []
        return "\n".join([c["content"] for c in recent_context])

if __name__ == "__main__":
    mem = MemorySystem()
    print(f"Memory system initialized: {mem.memory_file}")
    mem.add_memory("projects", "Alii AI - Building autonomous AI system")
    mem.add_memory("user_preferences", {"learning_style": "hands-on", "focus": "systems"})
    mem.add_memory("facts", "Using AliiLLM with Llama3.2:3b and Qwen2.5:3b")
    print(f"Projects: {len(mem.memories[projects])}, Facts: {len(mem.memories[facts])}")
