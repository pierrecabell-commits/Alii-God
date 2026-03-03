#!/bin/bash
S=/home/avalii/moltbot/security
L=/home/avalii/moltbot/logs/hardening.log
echo "[$(date)] ===== ALII HARDENING START =====" | tee -a $L
python3 $S/fix_brain.py 2>&1 | tee -a $L
bash $S/p1_ufw.sh        2>&1 | tee -a $L && echo "[DONE] P1 UFW" | tee -a $L || echo "[FAIL] P1" | tee -a $L
bash $S/p2_ssh.sh        2>&1 | tee -a $L && echo "[DONE] P2 SSH" | tee -a $L || echo "[FAIL] P2" | tee -a $L
bash $S/p3_services.sh   2>&1 | tee -a $L && echo "[DONE] P3 SVC" | tee -a $L || echo "[FAIL] P3" | tee -a $L
echo "" | tee -a $L
echo "[$(date)] ===== HARDENING COMPLETE =====" | tee -a $L
echo ""
echo "=== UFW ==="
sudo ufw status verbose
echo "=== FAIL2BAN ==="
fail2ban-client status
echo "=== ALFRED ==="
curl -s http://127.0.0.1:7000/status
