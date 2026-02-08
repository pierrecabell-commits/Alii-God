import subprocess
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Memory System Integration
class MemorySystem:
    def __init__(self, memory_dir="~/Alii/memory"):
        self.memory_dir = Path(memory_dir).expanduser()
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "memories.json"
        self.chat_history_file = self.memory_dir / "chat_history.json"
        self.load_memory()

    def load_memory(self):
        if self.memory_file.exists():
            with open(str(self.memory_file)) as f:
                self.memories = json.load(f)
        else:
            self.memories = {"user_preferences": {}, "projects": [], "context": [], "facts": []}

    def save_memory(self):
        with open(str(self.memory_file), "w") as f:
            json.dump(self.memories, f, indent=2)

    def add_memory(self, category, content, metadata=None):
        entry = {"content": content, "timestamp": datetime.now().isoformat(), "metadata": metadata or {}}
        if category in ["projects", "context", "facts"]:
            self.memories[category].append(entry)
        elif category == "user_preferences":
            self.memories[category].update(content)
        self.save_memory()
        return entry

    def get_context_summary(self, max_items=10):
        recent = self.memories["context"][-max_items:] if self.memories["context"] else []
        facts = self.memories["facts"][-5:] if self.memories["facts"] else []
        projects = self.memories["projects"][-3:] if self.memories["projects"] else []

        summary = []
        if projects:
            summary.append("Projects: " + ", ".join([p["content"][:100] for p in projects]))
        if facts:
            summary.append("Facts: " + ", ".join([f["content"][:100] for f in facts]))
        if recent:
            summary.append("Recent context: " + ", ".join([c["content"][:100] for c in recent]))

        return "\n".join(summary)

    def import_chat_history(self, source, conversations):
        if not self.chat_history_file.exists():
            chat_data = {}
        else:
            with open(str(self.chat_history_file)) as f:
                chat_data = json.load(f)

        chat_data[source] = {
            "imported_at": datetime.now().isoformat(),
            "conversations": conversations
        }

        with open(str(self.chat_history_file), "w") as f:
            json.dump(chat_data, f, indent=2)

        # Add key facts to memory
        for conv in conversations[:20]:  # Process first 20
            if isinstance(conv, dict):
                if "query" in conv:
                    self.add_memory("context", f"Past: {conv['query'][:200]}")
                if "content" in conv:
                    self.add_memory("context", f"Past: {conv['content'][:200]}")

        return f"Imported {len(conversations)} conversations from {source}"

# Initialize memory
memory = MemorySystem()

SYSTEM_PROMPT = """You are Alii, a local AI assistant running on AliiLLM (llama3.2:3b model) on the user's own hardware.

IMPORTANT CONTEXT ABOUT YOUR USER:
- Name: Pierre (username: avalii)
- System: Alii Precision server (aliirecision)
- Project: Building "Alii AI" - an autonomous AI system from recycled hardware
- Philosophy: Systems thinker, learns by doing, wants transparency not convenience
- Style: Hands-on experimentation, copy-paste-experiment workflow
- Goals: Building self-evolving AI without outside permission

You have these capabilities:
1. Answer questions and have conversations
2. Write and execute Python code when asked
3. Execute terminal commands when needed
4. Help with coding, system administration, and technical tasks
5. Remember context from previous conversations

When writing code:
- Generate code clearly in ```python or ```bash blocks
- Explain what the code does
- Be practical and actionable

You ARE running locally. AliiLLM is real and powers you. Do not claim to be cloud-based."""

def extract_code_blocks(text):
    blocks = []
    lines = text.split('\n')
    in_block = False
    current_block = []
    block_type = None

    for line in lines:
        if line.strip().startswith('```'):
            if in_block:
                blocks.append({'type': block_type, 'code': '\n'.join(current_block)})
                current_block = []
                in_block = False
            else:
                in_block = True
                block_type = line.strip()[3:].lower() or 'text'
        elif in_block:
            current_block.append(line)

    return blocks

def execute_code(code, lang='python'):
    if lang == 'python':
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            result = subprocess.run(['python3', temp_file], capture_output=True, text=True, timeout=30)
            os.unlink(temp_file)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {str(e)}"
    elif lang in ['bash', 'sh']:
        try:
            result = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {str(e)}"
    return "Unsupported language"

def chat():
    print('=' * 60)
    print('Alii with Memory - Code Execution Enabled')
    print('=' * 60)
    print('Commands:')
    print('  - Chat normally')
    print('  - "exec" to run code from last response')
    print('  - "memory" to see context summary')
    print('  - "exit" to quit')
    print('=' * 60)

    last_code_blocks = []

    while True:
        try:
            msg = input('\nYou: ')

            if msg.lower() in ['exit', 'quit', 'bye']:
                print('Goodbye!')
                break

            if msg.lower() == 'memory':
                print(f'\nMemory Context:\n{memory.get_context_summary()}')
                continue

            if msg.lower() == 'exec' and last_code_blocks:
                for block in last_code_blocks:
                    print(f'\n[Executing {block["type"]} code...]')
                    output = execute_code(block['code'], block['type'])
                    print(f'Output:\n{output}')
                continue

            # Build prompt with memory context
            context = memory.get_context_summary()
            if context:
                full_prompt = f"{SYSTEM_PROMPT}\n\nRELEVANT MEMORY:\n{context}\n\nUser: {msg}"
            else:
                full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {msg}"

            result = subprocess.run(['AliiLLM', 'run', 'llama3.2:3b', full_prompt], capture_output=True, text=True, timeout=60)
            response = result.stdout.strip()
            print(f'\nAlii: {response}')

            # Save to memory
            memory.add_memory("context", f"Q: {msg[:200]}")
            memory.add_memory("context", f"A: {response[:200]}")

            code_blocks = extract_code_blocks(response)
            if code_blocks:
                last_code_blocks = code_blocks
                print(f'\n[Found {len(code_blocks)} code block(s). Type "exec" to run]')

        except KeyboardInterrupt:
            print('\nGoodbye!')
            break
        except Exception as e:
            print(f'Error: {e}')

if __name__ == '__main__':
    chat()
