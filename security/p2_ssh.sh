#!/bin/bash
set -e
LOG=/home/avalii/moltbot/logs/hardening.log
echo "[$(date)] P2 FAIL2BAN+SSH START" | tee -a $LOG
sudo tee /etc/fail2ban/jail.local > /dev/null << JEOF
[DEFAULT]
bantime=1h
findtime=10m
maxretry=5
backend=systemd
ignoreip=127.0.0.1/8 192.168.1.0/24 100.64.0.0/10
[sshd]
enabled=true
port=ssh
logpath=%(sshd_log)s
maxretry=4
bantime=2h
[sshd-ddos]
enabled=true
port=ssh
logpath=%(sshd_log)s
maxretry=10
findtime=1m
bantime=24h
JEOF
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
echo "[$(date)] fail2ban ACTIVE" | tee -a $LOG
sudo mkdir -p /etc/ssh/sshd_config.d
sudo tee /etc/ssh/sshd_config.d/99-alii-hardened.conf > /dev/null << SEOF
PermitRootLogin no
PasswordAuthentication no
X11Forwarding no
MaxAuthTries 3
MaxSessions 10
AllowUsers avalii
ClientAliveInterval 300
ClientAliveCountMax 3
LoginGraceTime 30
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UseDNS no
SEOF
sudo sshd -t && sudo systemctl reload ssh
echo "[$(date)] P2 SSH DONE" | tee -a $LOG
fail2ban-client status | tee -a $LOG
