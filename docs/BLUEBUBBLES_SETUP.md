# BlueBubbles Setup Guide

BlueBubbles is a macOS app that exposes iMessage via REST API.

## Installation (on macOS host)

1. Download BlueBubbles from: https://bluebubbles.app
2. Install and open BlueBubbles Server
3. In BlueBubbles: Settings → Server → Port (default: 1234)
4. Set a strong password in Settings → Security → Server Password
5. Enable "Start on Login"

## Tailscale Access

Ensure Tailscale is running on macOS. Add to vault:
```
BLUEBUBBLES_URL=http://<macbook-tailscale-ip>:1234
BLUEBUBBLES_PASSWORD=<your-password>
MACBOOK_TAILSCALE_IP=<tailscale-ip>
MACBOOK_LOCAL_IP=<local-lan-ip>
MACBOOK_SSH_USER=pierre
ALII_PHONE_NUMBER=+1XXXXXXXXXX
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/server/info | GET | Server health |
| /api/v1/message/count | GET | Total message count |
| /api/v1/chat/query | GET | List chats |
| /api/v1/message/query | GET | Messages in chat |
| /api/v1/message/text | POST | Send message |

## Testing

```bash
curl "http://localhost:1234/api/v1/server/info?password=YOUR_PASS"
```
