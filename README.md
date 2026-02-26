## Moltbot – Autonomous Agent Orchestrator (Python)

`moltbot/` contains a **Python-based orchestration layer** for autonomous agents that can monitor systems, optimize resources, and run money-making or protection workflows.

### High-Level Purpose

- Coordinate one or more long‑running agents (autonomous system, optimizer, protection).
- Persist and reload system state and memories across runs.
- Interact with external systems (servers, clusters, wallets, etc.) via scripts and services.

### Key Components

- `moltbot_master_base.py`, `moltbot_master_unified*.py` – core orchestration “master” scripts (various iterations and backups).
- `src/` – shell launchers for the autonomous system, optimizer, and protection agents:
  - `start_autonomous.sh`
  - `start_optimizer.sh`
  - `start_protection.sh`
- `memory/` – JSON files for enhanced memory and system state.
- `agents/` – separate optimizer/protection agent scripts and logs.
- `money_maker/` – experimental money‑making agent logic.
- `deleted_archive/`, `*_backup.py` – historical backups and experimental variants; useful for reference, not for active development.

### Status & Usage

- This project is **ad hoc and script‑driven**: there is no formal Python package or test suite.
- **Active entrypoints** (used by systemd/cron or manual shell):
  - `src/start_autonomous.sh`, `src/start_optimizer.sh`, `src/start_protection.sh` – start Alii‑flavored agents and write PID/log files into the top‑level `Alii/` directory.
  - `moltbot_with_memory.py` – interactive CLI for chatting with AliiLLM, with persistent memory and optional code execution via an explicit `exec` command.
  - `moltbot_master_base.py`, `moltbot_master_unified_fixed.py` – older “master” orchestrators (others under `deleted_archive/` or with `backup`/`old`/`corrupted` in the name are legacy).
- **Legacy / archival content**:
  - Files under `deleted_archive/`, `*_backup.py`, and older `moltbot_master_*.py` variants – keep for reference only.
  - Experimental helpers like `final_fix.py`, `ultimate_fix.py`, `correct_fix.py`, etc. are snapshots from previous repair attempts.
- Before using or extending Moltbot, you should:
  - Prefer `moltbot_with_memory.py` for manual interactive use.
  - Confirm which `moltbot_master_*.py` (if any) is actually launched by your services.
  - Review `TODO.md` (archive backups, unify masters, push to GitHub) and plan a consolidation pass.
- Long‑term, consider:
  - Consolidating the “master” scripts into a single maintained entrypoint.
  - Moving deprecated scripts fully into an `archive/` folder.
  - Adding basic tests and configuration management (e.g. `config.yaml`).

