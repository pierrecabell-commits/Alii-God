#!/bin/bash
cd /home/avalii/Alii
nohup python3 alii_protection_agent.py > protection.log 2>&1 &
echo $! > protection.pid
echo "Protection Agent started (PID: $(cat protection.pid))"
