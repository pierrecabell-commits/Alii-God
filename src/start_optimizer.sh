#!/bin/bash
cd /home/avalii/Alii
nohup python3 alii_optimizer.py > optimizer.log 2>&1 &
echo $! > optimizer.pid
echo "Alii Optimizer started (PID: $(cat optimizer.pid))"
