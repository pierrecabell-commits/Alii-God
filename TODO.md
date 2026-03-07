# Alii-God -- Task List

> Meticulous list of tasks required to make Alii-God production-ready and amazing.

---

## CRITICAL -- Must Fix Immediately

### 1. Security: Remove All Hardcoded Paths
- [ ] Replace every instance of `/home/avalii/moltbot` with environment-based config
- [ ] Affected files: `alii_core.py`, `alfred.py`, `memory_bridge.py`, `cluster_scan.py`, `security_agent.py`, `inventory_agent.py`, `revenue_agent.py`, `accounts_agent.py`, `agents/imessage_bridge.py`, `autoscale.py`
- [ ] Create a central `config.py` that resolves `ALII_WORKDIR` from environment or `Path(__file__).parent`
- [ ] Update all imports to use the central config

### 2. Security: Audit Git History for Leaked Secrets
- [ ] Scan full git history for API keys, tokens, and passwords
- [ ] Remove any committed `.env` files, private keys, or credentials from history using `git filter-repo`
- [ ] Verify `private.key`, `public.key`, `cluster_credentials.json`, and `wg0.conf` are not exposing real secrets
- [ ] Run `detect-secrets scan --all-files` and establish a baseline

### 3. Security: Fix Credential Management
- [ ] Move all credentials from `.env` to the Fernet-encrypted vault (`accounts_agent.py`)
- [ ] Remove plaintext passwords (Reddit username/password in `revenue_agent.py`)
- [ ] Implement credential rotation policy
- [ ] Fix vault key storage -- `VAULT_KEY` should not live in `.env`
- [ ] Add permission checks on `vault.json` (must be `0o600`)

### 4. Security: Fix SSH Host Key Verification
- [ ] Remove `paramiko.AutoAddPolicy()` from `cluster_scan.py`
- [ ] Load known hosts from `~/.ssh/known_hosts` instead
- [ ] Fix SSH `StrictHostKeyChecking` bypass in `alii_core.py`

### 5. Create Dependency Management
- [ ] Create `pyproject.toml` with all pinned dependencies
- [ ] Generate `requirements.txt` for pip compatibility
- [ ] Separate production vs development dependencies
- [ ] Add Python version constraint (`>=3.10`)
- [ ] Pin critical security dependencies (cryptography, paramiko, requests)

### 6. Add Test Suite
- [ ] Create `tests/` directory structure
- [ ] Write unit tests for `alii_sqlite_memory.py` (memory CRUD)
- [ ] Write unit tests for `accounts_agent.py` (vault encrypt/decrypt)
- [ ] Write unit tests for `security_agent.py` (secret scanning)
- [ ] Write unit tests for `alii_model_router.py` (model selection)
- [ ] Write unit tests for `memory_bridge.py` (memory sync)
- [ ] Write integration tests for `alfred.py` (service orchestration)
- [ ] Add `pytest.ini` or `pyproject.toml` test config
- [ ] Set up coverage reporting with `pytest-cov`
- [ ] Target: minimum 70% code coverage

---

## HIGH PRIORITY -- Before Production Use

### 7. Error Handling Overhaul
- [ ] Replace all bare `except Exception: pass` with specific exception handling
- [ ] Add retry logic with exponential backoff for HTTP calls in `alii_core.py`
- [ ] Add circuit breakers for external API calls (Anthropic, GitHub, Reddit)
- [ ] Add proper error responses in all HTTP endpoints (`alfred.py`, `revenue_agent.py`)
- [ ] Log all exceptions with stack traces, not just messages

### 8. Graceful Shutdown
- [ ] Add SIGTERM/SIGINT handlers to `alii_core.py`
- [ ] Add SIGTERM/SIGINT handlers to `alfred.py`
- [ ] Ensure all threads are daemon threads or properly joined on shutdown
- [ ] Close database connections on shutdown
- [ ] Close HTTP servers gracefully
- [ ] Save in-flight state before exit

### 9. Unified Logging System
- [ ] Replace all `print()` statements with `logging` module calls
- [ ] Standardize log format across all agents (JSON structured logging)
- [ ] Add log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) consistently
- [ ] Add request/correlation IDs for distributed tracing
- [ ] Configure log rotation for all log files
- [ ] Remove `alii_core.py` custom `log()` function -- use stdlib

### 10. Fix Memory System Fragmentation
- [ ] Create a unified `UnifiedMemory` abstract interface
- [ ] Consolidate SQLite backends (`alii_sqlite_memory.py` + `alii_core.py` SQLite)
- [ ] Remove duplicate JSON memory system (`memory_system.py` vs SQLite)
- [ ] Implement proper thread-safe file locking for JSON memory
- [ ] Fix race condition in `memory_system.py` `load_memory()`/`save_memory()`
- [ ] Complete the `query_points()` method in `memory_bridge.py`

### 11. Fix Broken/Incomplete Agents
- [ ] **autoscale.py**: Rewrite from scratch -- use `kubernetes` Python client instead of shell kubectl
- [ ] **agents/optimizer.py**: Expand beyond just `docker system prune`; add disk monitoring, log rotation, temp cleanup
- [ ] **start_alii_system.py**: Replace `pexpect` hack with proper subprocess management
- [ ] **memory_bridge.py**: Implement real semantic embeddings (sentence-transformers or Ollama embeddings) instead of hash vectors

### 12. Input Validation
- [ ] Add Pydantic models for all API request/response schemas
- [ ] Validate platform names in `accounts_agent.py` against allowed list
- [ ] Sanitize user inputs before passing to LLMs in `alii_core.py`
- [ ] Validate form data in `revenue_agent.py` contact form endpoint
- [ ] Add request size limits to all HTTP endpoints

### 13. Fix accounts_agent.py Bugs
- [ ] Fix `chmod` ordering bug -- `chmod` before `rename` in `_atomic_write_json()`
- [ ] Add rate limiting for platform API calls
- [ ] Fix `.tmp` file permissions (created with default umask)
- [ ] Add content validation for vault entries

---

## MEDIUM PRIORITY -- Quality and Reliability

### 14. Centralize Configuration
- [ ] Create `config.py` with all configurable parameters
- [ ] Support environment variable overrides for everything
- [ ] Move hardcoded port numbers from source code to config
- [ ] Move hardcoded URLs (Ollama, LiteLLM, etc.) to config
- [ ] Support config file reloading without restart

### 15. Add Type Hints Throughout
- [ ] Run `mypy` on all Python files and fix errors
- [ ] Add type annotations to all function signatures
- [ ] Add type annotations to all class attributes
- [ ] Create custom type aliases for complex types (e.g., `AgentResponse`, `MemoryEntry`)
- [ ] Add `py.typed` marker file for downstream consumers

### 16. Add API Documentation
- [ ] Document all HTTP endpoints in Alfred (`/status`, `/heal`, `/restart`, etc.)
- [ ] Document iMessage bridge API
- [ ] Document revenue agent contact form API
- [ ] Consider migrating to FastAPI for automatic OpenAPI spec generation
- [ ] Add API versioning

### 17. Clean Up Dead Code
- [ ] Remove unused imports in all files
- [ ] Remove `deleted_archive/` directory of backup files
- [ ] Remove `add_method_2.py` through `add_method_5.py` if no longer needed
- [ ] Remove `moltbot.py` and other legacy files from pre-rebrand
- [ ] Run `vulture` to identify all dead code

### 18. Add CI/CD Pipeline
- [ ] Create GitHub Actions workflow for:
  - [ ] Linting (`ruff` or `flake8`)
  - [ ] Type checking (`mypy`)
  - [ ] Unit tests (`pytest`)
  - [ ] Coverage reporting
  - [ ] Secret scanning (`detect-secrets`)
- [ ] Add pre-commit hooks config (`.pre-commit-config.yaml`)
- [ ] Add branch protection rules

### 19. Dockerize
- [ ] Create `Dockerfile` for the Alii-God system
- [ ] Create `docker-compose.yml` for local development (with Ollama, Qdrant, MinIO, n8n)
- [ ] Add health check endpoints compatible with Docker/Kubernetes
- [ ] Create Kubernetes manifests for production deployment

### 20. Documentation
- [ ] Create `ARCHITECTURE.md` with detailed system design docs
- [ ] Create `CONTRIBUTING.md` with development guidelines
- [ ] Add inline docstrings to all public functions and classes
- [ ] Document the memory architecture in detail
- [ ] Document the agent communication protocol
- [ ] Create deployment guide with step-by-step instructions

---

## LOW PRIORITY -- Polish

### 21. Code Formatting and Style
- [ ] Add `ruff` configuration (`.ruff.toml`)
- [ ] Format all files consistently
- [ ] Enforce import ordering
- [ ] Add EditorConfig (`.editorconfig`)

### 22. Monitoring and Observability
- [ ] Add Prometheus metrics for all agents (latency, error rates, throughput)
- [ ] Add health check endpoints to every agent
- [ ] Set up Grafana dashboards for system monitoring
- [ ] Add alerting rules for critical failures
- [ ] Add distributed tracing with OpenTelemetry

### 23. Developer Experience
- [ ] Create `Makefile` with common commands (install, test, lint, run, docker)
- [ ] Add VS Code workspace config (`.vscode/settings.json`)
- [ ] Add development environment setup script
- [ ] Create example `.env.example` with all required variables documented

---

*Last updated: 2026-03-07*
