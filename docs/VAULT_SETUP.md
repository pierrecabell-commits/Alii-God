# Vault Setup Guide

The Alii Vault stores credentials encrypted with Fernet + PBKDF2HMAC + argon2.

## Initialize

```bash
python3 vault/vault_manager.py init
```

You will be prompted for a master password. **Save it somewhere safe** — there is no recovery mechanism.

## Commands

```bash
python3 vault/vault_manager.py set KEY value    # Store a secret
python3 vault/vault_manager.py get KEY          # Retrieve a secret
python3 vault/vault_manager.py list             # List all keys (masked)
python3 vault/vault_manager.py import-env .env  # Import from .env file
python3 vault/vault_manager.py backup           # Create encrypted backup
python3 vault/vault_manager.py audit            # Show vault statistics
python3 vault/vault_manager.py rotate           # Change master password
```

## Daemon Mode (for agents)

```bash
python3 vault/vault_manager.py daemon
```

The daemon listens on `/tmp/alii_vault.sock` and serves secrets to agents via Unix socket. Agents use `vault/vault_client.py` to connect.

## Storage

```
~/.alii_vault/
├── vault.enc      — Encrypted secrets (Fernet)
├── vault.salt     — PBKDF2 salt (32 bytes)
├── vault.hash     — argon2 hash of master password
└── vault_pass.env — Daemon password (chmod 600, not for version control)
```

## Security Notes

- All files in `~/.alii_vault/` are chmod 600
- The vault directory is chmod 700
- Master password is hashed with argon2 (memory-hard)
- Encryption uses PBKDF2HMAC with 600,000 iterations
- Never commit `~/.alii_vault/` or `.env` to git
