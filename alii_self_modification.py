from datetime import timezone
#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
print("[ALII] Self-modification initiated")
config = json.loads(Path("/home/avalii/.openclaw/openclaw.json").read_text())
config.setdefault("agents", {}).setdefault("defaults", {})["ollama_tools_enabled"] = True
Path("/home/avalii/.openclaw/openclaw.json").write_text(json.dumps(config, indent=2))
print("Done")
