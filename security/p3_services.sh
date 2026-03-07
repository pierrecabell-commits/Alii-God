#!/bin/bash
set -e
LOG=/home/avalii/moltbot/logs/hardening.log
TS=100.75.36.73
echo "[$(date)] P3 SERVICES START" | tee -a $LOG
if grep -q '^LITELLM_MASTER_KEY=sk-' /home/avalii/moltbot/.env 2>/dev/null; then
  echo "[OK] LiteLLM key exists" | tee -a $LOG
else
  KEY=$(python3 -c "import secrets; print('sk-alii-'+secrets.token_hex(32))")
  echo "LITELLM_MASTER_KEY=$KEY" >> /home/avalii/moltbot/.env
  echo "[GENERATED KEY] $KEY" | tee -a $LOG
fi
sed -i "s/--host 0.0.0.0/--host $TS/g" /home/avalii/.config/systemd/user/alii-ui.service 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user restart alii-ui 2>/dev/null && echo "[OK] alii-ui->$TS" | tee -a $LOG || true
echo "[$(date)] P3 DONE" | tee -a $LOG
