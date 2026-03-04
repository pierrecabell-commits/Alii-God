#!/usr/bin/env python3
"""
moltbot.py — thin shim, delegates to alii_core
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alii_core import main

if __name__ == "__main__":
    main()
