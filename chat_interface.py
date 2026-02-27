from datetime import timezone
import sys
from Alii_enhanced import EnhancedAlii

bot = EnhancedAlii()

print("\n" + "="*60)
print("Alii INTERACTIVE CHAT")
print("="*60)
print("Type your messages in natural language. Type exit to quit.\n")

while True:
    try:
        user_input = input("You: ").strip()
        if user_input.lower() in [exit, quit, bye]:
            print("Alii: Goodbye!")
            break
        if not user_input:
            continue

        # Basic command parsing
        if process in user_input.lower() or cpu in user_input.lower():
            procs = bot.get_process_list()
            print("\nAlii: Here are the top processes:")
            for i, proc in enumerate(procs[:5], 1):
                print(f"  {i}. {proc[name]} (PID: {proc[pid]}) - CPU: {proc[cpu_percent]}%")
        elif system in user_input.lower() or stats in user_input.lower():
            stats = bot.get_system_stats()
            print("\nAlii: System stats:")
            for key, val in stats.items():
                print(f"  {key}: {val}")
        elif network in user_input.lower():
            net = bot.get_network_info()
            print("\nAlii: Network info:")
            for key, val in net.items():
                print(f"  {key}: {val}")
        else:
            print("\nAlii: I can help with:")
            print("  - Show processes/CPU usage")
            print("  - Display system stats")
            print("  - Network information")
            print("  Ask me about any of these!")
        print()
    except KeyboardInterrupt:
        print("\nAlii: Interrupted. Goodbye!")
        break
    except Exception as e:
        print(f"\nAlii: Error - {e}")
