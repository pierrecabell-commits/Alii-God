#!/bin/bash
# Safe ordered cluster shutdown for hardware maintenance
# Run: bash /home/avalii/moltbot/scripts/cluster_shutdown.sh
set -e
LOG=/home/avalii/moltbot/logs/cluster_shutdown.log

stamp() { date +"%Y-%m-%d %H:%M:%S"; }
log()   { echo "[$(stamp)] $*" | tee -a $LOG; }

log "=== CLUSTER SHUTDOWN INITIATED ==="

# 1. Check backup is done
BACKUP_PID=$(cat /tmp/sdc_backup.pid 2>/dev/null)
if kill -0 $BACKUP_PID 2>/dev/null; then
    COPIED=$(du -sh /mnt/storage3/root_backup/ 2>/dev/null | cut -f1)
    log "WARNING: Backup still running ($COPIED copied). Consider waiting."
    log "Proceeding anyway - data so far is safe."
fi

# 2. Stop Ray workers on NUC and XPS first
log "Stopping Ray workers on NUC and XPS..."
ssh -o ConnectTimeout=5 100.126.57.22 "systemctl --user stop ray-worker.service 2>/dev/null; /home/avalii/.local/bin/ray stop --force 2>/dev/null; echo NUC_RAY_STOPPED" || true
ssh -o ConnectTimeout=5 100.91.78.55 "systemctl --user stop ray-worker.service 2>/dev/null; /home/avalii/.local/bin/ray stop --force 2>/dev/null; echo XPS_RAY_STOPPED" || true

# 3. Unmount NFS mounts on NUC and XPS
log "Unmounting NFS on NUC/XPS..."
ssh -o ConnectTimeout=5 100.126.57.22 "sudo umount -l /mnt/precision-storage1 /mnt/precision-storage2 /mnt/precision-storage3 2>/dev/null; echo NUC_NFS_UNMOUNTED" || true
ssh -o ConnectTimeout=5 100.91.78.55 "sudo umount -l /mnt/precision-storage1 /mnt/precision-storage2 /mnt/precision-storage3 2>/dev/null; echo XPS_NFS_UNMOUNTED" || true

# 4. Shutdown NUC and XPS
log "Shutting down NUC..."
ssh -o ConnectTimeout=5 100.126.57.22 "sudo shutdown -h now" || true
log "Shutting down XPS..."
ssh -o ConnectTimeout=5 100.91.78.55 "sudo shutdown -h now" || true

# 5. Stop Alii services on precision
log "Stopping Alii services on precision..."
systemctl --user stop alii-ui.service || true
sudo systemctl stop ray-head.service || true
sudo systemctl stop ollama.service || true
sudo systemctl stop docker || true
sudo systemctl stop nfs-server || true

# 6. Sync all filesystems
log "Syncing filesystems..."
sync && sync

# 7. Final backup sync (if still running, let it finish)
if kill -0 $BACKUP_PID 2>/dev/null; then
    log "Waiting for backup to finish..."
    wait $BACKUP_PID
fi

log "=== READY FOR HARDWARE MAINTENANCE ==="
log "All services stopped. Filesystems synced."
log ""
log "HARDWARE CHECKLIST:"
log "  [ ] Replace /dev/sdc (Seagate ST2000DM001, 2TB HDD) - failing boot drive"
log "  [ ] Check M.2 slot - no NVMe detected (may be empty or needs BIOS AHCI mode)"
log "  [ ] NUC M.2 slot: takes M.2 2242 SATA SSD only (NOT standard 2280 NVMe)"
log ""
log "After hardware changes, run: sudo reboot"
