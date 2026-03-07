# Private Cloud Setup — Syncthing on Alii Precision

Replaces iCloud with a self-hosted, end-to-end encrypted file sync using Syncthing.
The Precision workstation (`aliirecision`, Tailscale `100.75.36.73`) acts as the hub.

---

## Precision (already configured)

Syncthing is installed at `~/.local/bin/syncthing` and running as a user systemd service.

```bash
# Check status
systemctl --user status syncthing.service

# View logs
journalctl --user -u syncthing.service -f

# Open Web UI (from within the machine or SSH tunnel)
# http://127.0.0.1:8384
```

**Device ID:**
```
LQZFL33-HKZUDGJ-5IUXGIY-AHMUYGY-3M5X7L3-KAGXHDJ-VSLHWPH-SLJUSAX
```

---

## Connect MacBook Pro (macOS)

1. Download Syncthing from https://syncthing.net/downloads/ (macOS app or Homebrew)
   ```bash
   brew install syncthing
   brew services start syncthing
   ```
2. Open the Web UI: http://127.0.0.1:8384
3. Click **Add Remote Device** and enter the Precision device ID above.
4. On the Precision Web UI (via SSH tunnel — see below), accept the MacBook connection.
5. Add a shared folder (e.g. `~/Sync`) on both devices and link them.

**SSH tunnel to Precision Web UI from MacBook:**
```bash
ssh -L 8385:127.0.0.1:8384 avalii@100.75.36.73
# Then open http://127.0.0.1:8385 in your browser
```

---

## Connect iPhone (iOS)

1. Install **Möbius Sync** or **Syncthing-iOS** from the App Store (Möbius Sync recommended).
2. Open the app and tap **Add Device**.
3. Enter the Precision device ID: `LQZFL33-HKZUDGJ-5IUXGIY-AHMUYGY-3M5X7L3-KAGXHDJ-VSLHWPH-SLJUSAX`
4. Accept the connection on the Precision Web UI.
5. Share a folder from the Precision side and accept it on the iPhone.

**Note:** The iPhone Tailscale IP is `100.111.40.78`. Make sure Tailscale is connected
on the iPhone for direct sync without opening ports on your router.

---

## Recommended Folder Structure

```
~/Sync/
├── documents/    # Replaces iCloud Documents
├── photos/       # Replaces iCloud Photos (manual backup)
├── notes/        # Plain-text notes (replaces iCloud Notes)
└── alii-data/    # Shared Alii memory exports
```

---

## Security Notes

- Syncthing traffic is TLS-encrypted with device certificates.
- The Web UI is bound to `127.0.0.1` only — not exposed externally.
- Access remotely only via SSH tunnel or Tailscale.
- All device IDs act as public keys — safe to share.
- No data leaves your devices or Tailscale network.

---

## Backup Recommendation

Add a cron job to snapshot the Sync folder daily:

```bash
0 3 * * * rsync -a ~/Sync/ ~/Sync_backup/$(date +\%Y-\%m-\%d)/ --delete
```
