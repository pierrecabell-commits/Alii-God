#!/bin/bash
cd /home/avalii/Alii
nohup python3 alii_autonomous_system.py > autonomous_system.log 2>&1 &
echo $! > autonomous.pid
echo "Alii Autonomous System started (PID: $(cat autonomous.pid))"
