#!/usr/bin/env python3
"""
CryptoAgent — Local Ethereum wallet generator and manager for Alii AI.

SECURITY RULES (never violate):
- Private key and seed phrase stored ONLY encrypted in vault via AccountsAgent
- Private key and seed phrase NEVER logged, NEVER printed, NEVER sent over ntfy
- Only the PUBLIC wallet address is ever shared, sent, or displayed
- Wallet generated locally using eth_account — no external service involved
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("alii.crypto_agent")

WORKDIR    = Path(os.environ.get("ALII_WORKDIR", str(Path(__file__).resolve().parent.parent)))
README     = WORKDIR / "README.md"
ETH_RPC    = "https://eth.llamarpc.com"   # free public RPC, no API key


class CryptoAgent:
    """
    Local Ethereum wallet management using eth_account.
    Private key and seed phrase encrypted in AccountsAgent vault.
    Only public address is ever exposed.
    """

    def __init__(self):
        sys.path.insert(0, str(WORKDIR))
        log.info("CryptoAgent initialised.")

    def _get_accounts_agent(self):
        from agents.accounts_agent import AccountsAgent
        return AccountsAgent()

    # ── Wallet Generation ─────────────────────────────────────────────────────

    def generate_wallet(self) -> str:
        """
        Generate a new Ethereum wallet locally using eth_account.
        Stores encrypted private key + mnemonic in AccountsAgent vault.
        Returns ONLY the public wallet address.
        NEVER logs or prints the private key or seed phrase.
        """
        from eth_account import Account
        Account.enable_unaudited_hdwallet_features()

        # Check if wallet already exists
        agent = self._get_accounts_agent()
        existing = agent.get_account("eth_wallet_address")
        if existing:
            addr = existing["username"]  # stored as username field
            log.info("generate_wallet: wallet already exists at %s", addr)
            return addr

        # Generate new wallet with mnemonic
        acct, mnemonic = Account.create_with_mnemonic()
        address    = acct.address
        private_key = acct.key.hex()   # NEVER log this

        # Store encrypted in vault — private key as password field, mnemonic in notes
        agent.store_account(
            service="eth_wallet_address",
            username=address,
            password="",              # address is not secret — stored for easy retrieval
            url="https://etherscan.io/address/" + address,
            notes="Public address only. See eth_wallet_private for private key.",
        )
        # Store private key separately (encrypted at rest inside Fernet)
        agent.store_account(
            service="eth_wallet_private",
            username=address,
            password=private_key,    # encrypted inside vault
            url="https://etherscan.io/address/" + address,
            notes="PRIVATE KEY — never share, never log, never send. Encrypted in vault.",
        )
        # Store mnemonic separately
        agent.store_account(
            service="eth_wallet_mnemonic",
            username=address,
            password=mnemonic,       # encrypted inside vault
            url="",
            notes="SEED PHRASE — write on paper, store offline. Encrypted in vault.",
        )

        log.info("generate_wallet: new wallet created. Address=%s", address)
        log.info("generate_wallet: private key and mnemonic stored encrypted in vault ONLY.")
        log.info("generate_wallet: *** PRIVATE KEY AND SEED PHRASE NOT LOGGED ***")

        # Clear from memory as best-effort (Python GC doesn't guarantee this)
        del private_key
        del mnemonic

        return address

    def get_wallet_address(self) -> str | None:
        """Return the public wallet address only. Never returns private key."""
        agent = self._get_accounts_agent()
        entry = agent.get_account("eth_wallet_address")
        if entry:
            return entry["username"]
        log.warning("get_wallet_address: no wallet found. Run generate_wallet() first.")
        return None

    # ── Balance Check ─────────────────────────────────────────────────────────

    def check_balance(self, address: str | None = None) -> dict:
        """
        Check ETH balance using free public RPC (eth.llamarpc.com).
        No API key needed. Returns balance in ETH and wei.
        """
        if address is None:
            address = self.get_wallet_address()
        if not address:
            return {"error": "No wallet address available"}

        # eth_getBalance JSON-RPC call
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1,
        })

        try:
            r = subprocess.run(
                ["curl", "-s", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", payload,
                 "--max-time", "10",
                 ETH_RPC],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(r.stdout)
            if "result" in data:
                wei = int(data["result"], 16)
                eth = wei / 1e18
                log.info("check_balance: %s → %.6f ETH (%d wei)", address, eth, wei)
                return {
                    "address": address,
                    "balance_eth": round(eth, 6),
                    "balance_wei": wei,
                    "rpc": ETH_RPC,
                }
            else:
                return {"address": address, "error": data.get("error", "unknown")}
        except Exception as exc:
            log.warning("check_balance error: %s", exc)
            return {"address": address, "error": str(exc)}

    # ── Donation Info ─────────────────────────────────────────────────────────

    def generate_donation_qr_info(self) -> dict:
        """
        Return wallet address formatted for README donation section and QR code.
        """
        address = self.get_wallet_address()
        if not address:
            return {"error": "No wallet. Run generate_wallet() first."}

        return {
            "eth_address": address,
            "ethereum_uri": f"ethereum:{address}",
            "polygon_uri":  f"ethereum:{address}@137",   # chain ID 137 = Polygon
            "qr_code_text": address,
            "readme_badge": f"[![ETH](https://img.shields.io/badge/ETH-{address[:6]}...{address[-4:]}-blue)](https://etherscan.io/address/{address})",
            "readme_section": (
                f"**ETH / USDC / MATIC:** `{address}`\n"
                f"*(Polygon network preferred for near-zero gas fees)*\n"
                f"[View on Etherscan](https://etherscan.io/address/{address})"
            ),
        }

    def add_to_readme(self) -> bool:
        """
        Read README.md and add/update a Crypto Donations section with the
        wallet address. Only inserts if section not already present.
        """
        address = self.get_wallet_address()
        if not address:
            log.warning("add_to_readme: no wallet address found.")
            return False

        if not README.exists():
            log.warning("add_to_readme: README.md not found at %s", README)
            return False

        content = README.read_text()

        crypto_section = f"""
## Crypto Donations

**ETH / USDC / MATIC:** `{address}`

Send USDC on Polygon network for near-zero gas fees (~$0.01).

[View wallet on Etherscan](https://etherscan.io/address/{address})

*Also accepting: ETH (mainnet), USDC (Polygon/Ethereum), MATIC*
"""

        if "## Crypto Donations" in content:
            log.info("add_to_readme: Crypto Donations section already present.")
            return True

        # Append crypto section before the final line or at end
        if "## Support" in content:
            # Insert after Support section
            content = content.replace(
                "## Support",
                crypto_section.strip() + "\n\n## Support",
                1
            )
        else:
            content = content.rstrip() + "\n" + crypto_section

        README.write_text(content)
        log.info("add_to_readme: crypto donations section added for %s", address)
        return True


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(WORKDIR))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    agent = CryptoAgent()

    print("\n=== generate_wallet() ===")
    address = agent.generate_wallet()
    print(f"  Public address: {address}")

    print("\n=== get_wallet_address() ===")
    addr2 = agent.get_wallet_address()
    print(f"  Address: {addr2}")

    print("\n=== add_to_readme() ===")
    ok = agent.add_to_readme()
    print(f"  README updated: {ok}")

    print("\n=== generate_donation_qr_info() ===")
    qr = agent.generate_donation_qr_info()
    print(f"  ETH address : {qr.get('eth_address', 'N/A')}")
    print(f"  README badge: {qr.get('readme_badge', 'N/A')}")

    print("\n=== check_balance() ===")
    bal = agent.check_balance()
    print(f"  Balance: {bal.get('balance_eth', 'N/A')} ETH")

    # Send ntfy with PUBLIC address ONLY
    pub_addr = addr2 or address
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             "-H", "Title: Alii Crypto Wallet Ready",
             "-H", "Priority: default",
             "-d", f"ETH wallet created. Public address: {pub_addr}. Added to README. Private key encrypted in vault only.",
             "https://ntfy.sh/alii-precision"],
            capture_output=True, timeout=8
        )
        print(f"\n  ntfy sent: public address {pub_addr}")
    except Exception as e:
        print(f"\n  ntfy error: {e}")

    print("\n=== DONE ===")
