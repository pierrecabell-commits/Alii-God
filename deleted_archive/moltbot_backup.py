import subprocess
import json
import sys

class Alii:
    def __init__(self, model="llama3.2:3b"):
        self.model = model
        print(f"[Alii] Initialized with model: {self.model}")

    def query(self, prompt, stream=True):
        """Send query to AliiLLM and get response"""
        try:
            cmd = ["AliiLLM", "run", self.model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def list_models(self):
        """List available models"""
        result = subprocess.run(["AliiLLM", "list"], capture_output=True, text=True)
        return result.stdout

if __name__ == "__main__":
    bot = Alii()
    print(bot.list_models())
    print("\n[Test Query]")
    response = bot.query("Say hello and introduce yourself as Alii, an AI assistant for the Alii AI project.")
    print(response)
