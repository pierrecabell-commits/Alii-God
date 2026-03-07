#!/bin/bash
# ALII AI INFRASTRUCTURE STARTUP & PERSISTENCE

echo "=== INITIALIZING ALII INFRASTRUCTURE ==="

# 1. MOUNT STORAGE
echo "[1] Checking Storage Mounts..."
# sda (Renamed to old_storage_sda)
if ! mountpoint -q /mnt/storage1; then
    echo "Mounting storage1..."
    sudo vgchange -ay old_storage_sda
    sudo mount /dev/old_storage_sda/ubuntu-lv /mnt/storage1
else
    echo "storage1 already mounted."
fi

# sdb (Raw 931GB)
if ! mountpoint -q /mnt/storage2; then
    echo "Mounting storage2..."
    sudo mount /dev/sdb /mnt/storage2 || (echo "Formatting sdb..." && sudo mkfs.ext4 -F /dev/sdb && sudo mount /dev/sdb /mnt/storage2)
else
    echo "storage2 already mounted."
fi

# 2. DOCKER & GPU
echo "[2] Enabling Hardware Access..."
sudo systemctl start docker
sudo chmod 666 /var/run/docker.sock
nvidia-smi > /dev/null 2>&1 && echo "GPU Access: CONFIRMED" || echo "GPU Access: FAILED/NO GPU"

echo "=== INFRASTRUCTURE READY ==="
