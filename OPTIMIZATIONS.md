# Alii-God -- Optimizations and Improvements

> Separate from the task list, this document covers performance optimizations, architectural improvements, and enhancements that would take Alii-God from functional to exceptional.

---

## Performance Optimizations

### 1. LLM Routing Intelligence
- **Current**: `alii_model_router.py` uses static heuristic mapping (task type to model)
- **Improvement**: Track response quality + latency per model per task type in SQLite; use historical performance data to dynamically route requests to the best-performing model
- **Impact**: Better response quality, lower latency, reduced token costs
- **Effort**: Medium

### 2. Memory Query Performance
- **Current**: `memory_bridge.py` uses hash-based 768D vectors (deterministic, not semantic)
- **Improvement**: Replace with actual sentence-transformer embeddings (`nomic-embed-text` via Ollama or `all-MiniLM-L6-v2` locally); add embedding cache to avoid re-computing
- **Impact**: Dramatically better semantic recall; agents can actually find relevant past context
- **Effort**: Medium

### 3. SQLite Connection Pooling
- **Current**: Each memory instance creates its own `sqlite3.connect()` call
- **Improvement**: Implement connection pool with max connections; use WAL mode consistently; add prepared statement caching
- **Impact**: Reduced connection overhead, better concurrent performance
- **Effort**: Low

### 4. Batch LLM Requests
- **Current**: Each agent makes individual LLM calls synchronously
- **Improvement**: Queue non-urgent LLM requests and batch them; use async/await for concurrent calls; implement request deduplication
- **Impact**: Higher throughput, better GPU utilization on Ollama
- **Effort**: Medium

### 5. Memory Compaction
- **Current**: Episodic memory grows unbounded
- **Improvement**: Implement periodic compaction -- summarize old conversations into key facts, archive raw data, keep working set small
- **Impact**: Faster memory queries, reduced storage, better context relevance
- **Effort**: High

### 6. Agent Startup Time
- **Current**: All agents start sequentially via `alfred.py`
- **Improvement**: Parallel agent initialization with dependency graph; lazy-load agents that aren't immediately needed
- **Impact**: Faster system boot (currently 20+ seconds grace period per service)
- **Effort**: Medium

---

## Architectural Improvements

### 7. Event-Driven Architecture
- **Current**: Agents poll or run on fixed intervals (e.g., `autoscale.py` every 30s, `optimizer.py` every 3600s)
- **Improvement**: Implement an event bus (Redis Pub/Sub or ZeroMQ) so agents react to events rather than polling; events: `memory.updated`, `cluster.node.down`, `security.alert`, `revenue.opportunity`
- **Impact**: Lower resource usage, faster response to system changes, cleaner agent coordination
- **Effort**: High

### 8. Agent SDK / Plugin Framework
- **Current**: Each agent is a standalone script with its own patterns
- **Improvement**: Create a base `Agent` class with lifecycle hooks (`on_start`, `on_message`, `on_shutdown`, `on_health_check`), standardized config loading, and automatic registration with Alfred
- **Impact**: Easier to add new agents, consistent behavior, reduced boilerplate
- **Effort**: High

### 9. Service Mesh with Health Contracts
- **Current**: Alfred manages services with basic process monitoring
- **Improvement**: Define formal health contracts per service (HTTP health endpoint, startup/readiness/liveness probes); implement circuit breakers for inter-service calls; add service discovery
- **Impact**: Better reliability, faster failure detection, automatic recovery
- **Effort**: Medium

### 10. Unified API Gateway
- **Current**: Each agent exposes its own HTTP endpoints on different ports
- **Improvement**: Route all external traffic through a single gateway (FastAPI or nginx) with authentication, rate limiting, and request logging; internal agents communicate via direct calls or message bus
- **Impact**: Single entry point, centralized auth, easier security auditing
- **Effort**: Medium

### 11. State Machine for Agent Lifecycle
- **Current**: Agent states are loosely tracked as strings ("stopped", "starting", "running", "failed")
- **Improvement**: Implement proper state machine with transitions, guards, and hooks; prevent invalid state transitions; add state history for debugging
- **Impact**: Fewer bugs from invalid states, better debugging, clearer lifecycle
- **Effort**: Low

---

## Security Improvements

### 12. Zero-Trust Inter-Agent Communication
- **Current**: Agents communicate over localhost HTTP without authentication
- **Improvement**: Add mTLS or signed JWT tokens for inter-agent calls; each agent gets its own identity; Alfred acts as certificate authority
- **Impact**: Even if one agent is compromised, lateral movement is prevented
- **Effort**: High

### 13. Secrets Management with HashiCorp Vault
- **Current**: Fernet-encrypted vault file with key in `.env`
- **Improvement**: Integrate with HashiCorp Vault (or similar) for proper secrets management with audit logging, automatic rotation, and access policies
- **Impact**: Enterprise-grade secret management, compliance-ready
- **Effort**: High

### 14. Sandboxed Agent Execution
- **Current**: All agents run with full system access
- **Improvement**: Run each agent in its own container or namespace with minimal permissions; use Linux capabilities to restrict filesystem and network access
- **Impact**: Blast radius reduction -- a bug in one agent can't affect others
- **Effort**: High

### 15. Audit Logging
- **Current**: Basic logging to files, no structured audit trail
- **Improvement**: Log all privileged operations (credential access, config changes, agent restarts, cluster operations) to an append-only audit log with timestamps, actor, and action
- **Impact**: Full accountability, incident investigation capability
- **Effort**: Medium

---

## Intelligence Improvements

### 16. Agent Self-Optimization Loop
- **Current**: `alii_self_modification.py` exists but approach is unclear
- **Improvement**: Implement a structured improvement cycle: (1) collect metrics, (2) identify bottlenecks, (3) generate improvement hypotheses, (4) test in sandbox, (5) apply if metrics improve, (6) rollback if not
- **Impact**: System gets genuinely smarter over time with guardrails
- **Effort**: Very High

### 17. Multi-Agent Collaboration Protocol
- **Current**: Agents are mostly independent; coordination is through shared memory
- **Improvement**: Define a formal collaboration protocol -- agents can request help from other agents, delegate sub-tasks, and report results; implement a task decomposition engine
- **Impact**: Complex tasks get broken down and handled by the right specialist
- **Effort**: High

### 18. Context Window Management
- **Current**: Conversation history is trimmed by count
- **Improvement**: Implement intelligent context management -- summarize older messages, keep recent ones verbatim; inject relevant semantic memories as system context; track token usage per conversation
- **Impact**: Better conversation quality, fewer "forgotten" context issues
- **Effort**: Medium

### 19. Model Fallback Chains
- **Current**: Model router picks one model
- **Improvement**: Define fallback chains (e.g., try `qwen2.5-coder:32b` -> `qwen2.5-coder:7b` -> `claude-3.5-sonnet` via API); automatically fall back on timeout, rate limit, or quality threshold
- **Impact**: Higher availability, graceful degradation
- **Effort**: Low

---

## Developer Experience Improvements

### 20. Hot-Reload for Agent Development
- **Current**: Must restart entire system to test agent changes
- **Improvement**: Implement file watcher that detects changes to agent files and hot-reloads them without restarting the full stack; preserve agent state across reloads
- **Impact**: Much faster development iteration
- **Effort**: Medium

### 21. Agent Development CLI
- **Current**: No tooling for creating new agents
- **Improvement**: `alii new-agent <name>` scaffolds a new agent with boilerplate, tests, config, and registers it with Alfred
- **Impact**: Lower barrier to creating new agents
- **Effort**: Low

### 22. System Dashboard
- **Current**: Monitoring through log files and Grafana
- **Improvement**: Build a real-time web dashboard showing: agent status, memory usage, LLM request queue, cluster health, recent errors, task progress; accessible from any device on Tailscale
- **Impact**: At-a-glance system health, easier debugging
- **Effort**: High

### 23. Replay and Debug Mode
- **Current**: No way to replay past interactions or debug issues
- **Improvement**: Record all agent inputs/outputs; allow replaying a specific interaction with modified parameters; add step-through debugging for agent decision chains
- **Impact**: Much easier to debug issues and test fixes
- **Effort**: High

---

## Infrastructure Improvements

### 24. Automated Cluster Provisioning
- **Current**: Manual setup of each cluster node
- **Improvement**: Ansible playbooks or Terraform configs to provision new nodes; automated Tailscale enrollment, Docker installation, and agent deployment
- **Impact**: Add new compute nodes in minutes instead of hours
- **Effort**: Medium

### 25. Backup and Disaster Recovery
- **Current**: No backup strategy visible
- **Improvement**: Automated daily backups of SQLite databases, vault, and config to MinIO with encryption; tested restore procedure; backup verification
- **Impact**: Data safety, ability to recover from failures
- **Effort**: Medium

### 26. Resource Quotas and Limits
- **Current**: `autoscale.py` is minimal (21 lines)
- **Improvement**: Implement proper resource management -- CPU/memory limits per agent, GPU time slicing for Ollama, disk quota monitoring, automatic cleanup when thresholds are hit
- **Impact**: Prevent resource exhaustion, fair sharing across agents
- **Effort**: Medium

---

## Quality of Life

### 27. Natural Language System Control
- **Current**: System control via CLI commands and HTTP API
- **Improvement**: Allow natural language commands via iMessage or any channel ("Hey Alii, restart the security agent", "Show me cluster health", "What's your memory usage?")
- **Impact**: More intuitive system management
- **Effort**: Medium (much of the infrastructure exists already)

### 28. Weekly System Reports
- **Current**: `OVERNIGHT_REPORT.md` exists but generation is unclear
- **Improvement**: Automated weekly digest: uptime stats, errors encountered, memory growth, LLM usage/costs, revenue generated, security events, tasks completed
- **Impact**: Clear visibility into system performance over time
- **Effort**: Low

### 29. Notification Escalation
- **Current**: Notifications go to iMessage/ntfy but no escalation
- **Improvement**: Implement escalation tiers -- INFO goes to log only, WARNING goes to ntfy, ERROR goes to iMessage, CRITICAL goes to iMessage + email + phone call
- **Impact**: Never miss critical issues, reduce notification fatigue
- **Effort**: Low

---

*Last updated: 2026-03-07*
