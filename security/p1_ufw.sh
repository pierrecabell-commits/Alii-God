#!/bin/bash
set -e
LOG=/home/avalii/moltbot/logs/hardening.log
echo "[$(date)] P1 UFW START" | tee -a $LOG
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
for port in 22; do
  sudo ufw allow from 192.168.1.0/24 to any port $port
  sudo ufw allow from 100.64.0.0/10  to any port $port
done
for port in 3000 5678 8888 8001; do
  sudo ufw allow from 192.168.1.0/24 to any port $port
  sudo ufw allow from 100.64.0.0/10  to any port $port
done
for port in 4000 8000 7000 8080 9000 9001 6333 6334 9090 9100 6379 8076 8077 10001 8265 16443 25000; do
  sudo ufw allow from 100.64.0.0/10 to any port $port
done
sudo ufw allow from 192.168.1.183 to any port 2049
sudo ufw allow from 192.168.1.183 to any port 111
sudo ufw --force enable
sudo ufw status verbose | tee -a $LOG
echo "[$(date)] P1 UFW DONE" | tee -a $LOG
