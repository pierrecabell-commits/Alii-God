from datetime import timezone
import pexpect
import sys
import time

child = pexpect.spawn("python3 moltbot_master_unified.py.bak")
child.logfile = sys.stdout.buffer
child.expect("You: ", timeout=10)
child.sendline("system_status")
child.expect("You: ", timeout=10)
child.sendline("start_cluster")
child.expect("You: ", timeout=10)
child.sendline("start_vllm")
time.sleep(2)
