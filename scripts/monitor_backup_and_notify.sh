#!/bin/bash
# Monitors sdc backup and sends ntfy when complete
BACKUP_PID=$(cat /tmp/sdc_backup.pid 2>/dev/null)
LOG=/home/avalii/moltbot/logs/sdc_backup.log

if [ -z "$BACKUP_PID" ]; then
    echo "No backup PID found"
    exit 1
fi

echo "Monitoring backup PID $BACKUP_PID..."
while kill -0 $BACKUP_PID 2>/dev/null; do
    sleep 30
done

RESULT=$(tail -3 $LOG)
COPIED=$(du -sh /mnt/storage3/root_backup/ 2>/dev/null | cut -f1)

curl -s \
  -H "Title: Alii Backup Complete" \
  -H "Priority: high" \
  -H "Tags: white_check_mark,hard_drive" \
  -d "sdc root backup COMPLETE. $COPIED copied to /mnt/storage3/root_backup/. Safe to proceed with hardware maintenance and shutdown." \
  https://ntfy.sh/alii-precision

echo "[$(date)] Backup complete. $COPIED copied." >> $LOG
