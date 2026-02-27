from datetime import timezone
import subprocess
import sys

def chat():
    print("Alii Interactive Chat - Type your message, or exit to quit")
    while True:
        msg = input("You: ")
        if msg.lower() in ["exit", "quit", "bye"]:
            break
        result = subprocess.run(["AliiLLM", "run", "llama3.2:3b", msg], capture_output=True, text=True)
        print(f"Alii: {result.stdout.strip()}")

if __name__ == "__main__":
    chat()
