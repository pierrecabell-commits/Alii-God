#!/bin/bash
# =============================================================
# Alii Cloud — Mac Media Sync Setup
# Run this on the MacBook to configure Syncthing + rsync
# =============================================================

set -e

PRECISION_IP="100.75.36.73"
PRECISION_DEVICE_ID="LQZFL33-HKZUDGJ-5IUXGIY-AHMUYGY-3M5X7L3-KAGXHDJ-VSLHWPH-SLJUSAX"

echo "========================================="
echo "  Alii Cloud — Mac Media Sync Setup"
echo "========================================="

# --- Step 1: Install Syncthing if not present ---
if ! command -v syncthing &>/dev/null; then
    echo "[1/5] Installing Syncthing via Homebrew..."
    brew install syncthing
else
    echo "[1/5] Syncthing already installed: $(syncthing --version | head -1)"
fi

# --- Step 2: Start Syncthing service ---
echo "[2/5] Starting Syncthing service..."
brew services start syncthing 2>/dev/null || true
sleep 3

# Get Mac's Syncthing API key
MAC_ST_CONFIG="$HOME/Library/Application Support/Syncthing/config.xml"
if [ -f "$MAC_ST_CONFIG" ]; then
    MAC_API_KEY=$(grep -oP '(?<=<apikey>)[^<]+' "$MAC_ST_CONFIG" 2>/dev/null || \
                  sed -n 's/.*<apikey>\(.*\)<\/apikey>.*/\1/p' "$MAC_ST_CONFIG")
    MAC_DEVICE_ID=$(curl -s -H "X-API-Key: $MAC_API_KEY" "http://127.0.0.1:8384/rest/system/status" | python3 -c "import json,sys; print(json.load(sys.stdin)['myID'])")
    echo "    Mac Device ID: $MAC_DEVICE_ID"
    echo ""
    echo "    *** IMPORTANT: Copy this Device ID ***"
    echo "    You'll need it to pair with Precision."
else
    echo "    WARNING: Syncthing config not found. Start Syncthing first, then re-run."
    echo "    Try: open http://127.0.0.1:8384"
fi

# --- Step 3: Create local photo/video directories ---
echo "[3/5] Creating local sync directories..."
mkdir -p ~/Photos/AliiCloud
mkdir -p ~/Movies/AliiCloud

# --- Step 4: Add Precision as remote device ---
echo "[4/5] Adding Precision as remote device..."
if [ -n "$MAC_API_KEY" ]; then
    curl -s -X POST -H "X-API-Key: $MAC_API_KEY" -H "Content-Type: application/json" \
      "http://127.0.0.1:8384/rest/config/devices" -d '{
      "deviceID": "'"$PRECISION_DEVICE_ID"'",
      "name": "Precision",
      "addresses": ["tcp://'"$PRECISION_IP"':22000"],
      "compression": "metadata",
      "paused": false
    }' && echo "    Precision device added"

    # Add photos folder (send-only from Mac)
    curl -s -X POST -H "X-API-Key: $MAC_API_KEY" -H "Content-Type: application/json" \
      "http://127.0.0.1:8384/rest/config/folders" -d '{
      "id": "mac-photos",
      "label": "Mac Photos",
      "path": "'"$HOME"'/Photos/AliiCloud",
      "type": "sendonly",
      "rescanIntervalS": 3600,
      "fsWatcherEnabled": true,
      "devices": [
        {"deviceID": "'"$(curl -s -H "X-API-Key: $MAC_API_KEY" "http://127.0.0.1:8384/rest/system/status" | python3 -c "import json,sys; print(json.load(sys.stdin)['myID'])")"'"},
        {"deviceID": "'"$PRECISION_DEVICE_ID"'"}
      ]
    }' && echo "    Photos folder configured (send-only)"

    # Add videos folder (send-only from Mac)
    curl -s -X POST -H "X-API-Key: $MAC_API_KEY" -H "Content-Type: application/json" \
      "http://127.0.0.1:8384/rest/config/folders" -d '{
      "id": "mac-videos",
      "label": "Mac Videos",
      "path": "'"$HOME"'/Movies/AliiCloud",
      "type": "sendonly",
      "rescanIntervalS": 3600,
      "fsWatcherEnabled": true,
      "devices": [
        {"deviceID": "'"$(curl -s -H "X-API-Key: $MAC_API_KEY" "http://127.0.0.1:8384/rest/system/status" | python3 -c "import json,sys; print(json.load(sys.stdin)['myID'])")"'"},
        {"deviceID": "'"$PRECISION_DEVICE_ID"'"}
      ]
    }' && echo "    Videos folder configured (send-only)"
else
    echo "    Skipped — run manually after Syncthing starts."
fi

# --- Step 5: Install rsync script ---
echo "[5/5] Installing rsync-to-cloud script..."
cat > ~/bin/alii-cloud-sync <<'RSYNC_SCRIPT'
#!/bin/bash
# Alii Cloud — Manual rsync push to Precision
# Usage: alii-cloud-sync [photos|videos|all]

PRECISION="avalii@100.75.36.73"
PHOTOS_SRC="$HOME/Photos/AliiCloud/"
VIDEOS_SRC="$HOME/Movies/AliiCloud/"
PHOTOS_DST="/mnt/storage2/media/photos/"
VIDEOS_DST="/mnt/storage2/media/videos/"

sync_photos() {
    echo "Syncing photos to Precision..."
    rsync -avz --progress --exclude='.DS_Store' --exclude='._*' \
        "$PHOTOS_SRC" "$PRECISION:$PHOTOS_DST"
    echo "Photos sync complete."
}

sync_videos() {
    echo "Syncing videos to Precision..."
    rsync -avz --progress --exclude='.DS_Store' --exclude='._*' \
        "$VIDEOS_SRC" "$PRECISION:$VIDEOS_DST"
    echo "Videos sync complete."
}

case "${1:-all}" in
    photos) sync_photos ;;
    videos) sync_videos ;;
    all)    sync_photos; sync_videos ;;
    *)      echo "Usage: alii-cloud-sync [photos|videos|all]" ;;
esac
RSYNC_SCRIPT
chmod +x ~/bin/alii-cloud-sync

# --- Step 6: Add cron for nightly rsync ---
echo "[+] Adding nightly rsync cron (2 AM)..."
CRON_LINE="0 2 * * * $HOME/bin/alii-cloud-sync all >> $HOME/.alii-cloud-sync.log 2>&1"
(crontab -l 2>/dev/null | grep -v "alii-cloud-sync"; echo "$CRON_LINE") | crontab -

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "  Syncthing folders:"
echo "    Photos: ~/Photos/AliiCloud/ → Precision:/mnt/storage2/media/photos/"
echo "    Videos: ~/Movies/AliiCloud/ → Precision:/mnt/storage2/media/videos/"
echo ""
echo "  Drop photos/videos into those folders and they'll auto-sync."
echo ""
echo "  Manual rsync (for bulk transfers):"
echo "    alii-cloud-sync          # sync everything"
echo "    alii-cloud-sync photos   # photos only"
echo "    alii-cloud-sync videos   # videos only"
echo ""
echo "  Nightly rsync cron installed (2 AM backup)."
echo ""
echo "  NEXT STEP: Accept the MacBook on Precision's Syncthing."
echo "  SSH tunnel: ssh -L 8385:127.0.0.1:8384 avalii@100.75.36.73"
echo "  Then open: http://127.0.0.1:8385"
echo "========================================="
