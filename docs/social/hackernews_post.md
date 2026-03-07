# HackerNews Show HN Post — Alii AI
*One viral HN post has funded entire startups. This costs nothing.*

---

## POSTING INSTRUCTIONS

- URL: https://news.ycombinator.com/submit
- Title MUST start with: "Show HN:"
- Post at: 9-10am Eastern on a Tuesday, Wednesday, or Thursday
- Do NOT pay for upvotes (instant ban)
- DO respond to every single comment within the first 2 hours

---

## THE POST (copy-paste ready)

**Title (80 chars max):**
```
Show HN: Alii – an open-source autonomous AI agent platform that runs locally
```

**Text (optional but strongly recommended for Show HN):**
```
I've been building Alii for the past few months — a self-hosted AI agent
platform designed to run entirely on your own hardware with no cloud
dependencies.

The core idea: you shouldn't need to send your data to OpenAI to get
serious AI-assisted workflows.

What it does:
- Alfred orchestrator: manages multiple AI agents with self-healing
  (restarts failed services automatically via systemd)
- Multi-model router: routes tasks to the best local Ollama model
  (fast model for quick questions, powerful model for reasoning tasks)
- Persistent SQLite memory: every conversation is saved and searchable
- Specialized agents: law (LLC formation, contracts), business (financial
  models, competitor analysis), media (release notes, changelogs),
  security (port audits, hardening), money (revenue tracking)
- Two-way mobile control: send commands from your phone via ntfy.sh

Hardware requirements: Linux, 8GB+ RAM, any modern CPU. No GPU required
(though it helps). I'm running this on a 12-core workstation with 32GB RAM.

The whole stack: Python + asyncio + aiohttp + Ollama + SQLite + Chainlit

GitHub: [link]

Happy to answer questions about the architecture, the self-healing design,
or why I chose local LLMs over API calls.
```

---

## EXPECTED HN COMMENT QUESTIONS (prepare answers now)

**"Why not just use AutoGPT/LangChain/CrewAI?"**
```
AutoGPT is unreliable in production — it hallucinates tool calls and has no
self-healing. LangChain is a framework, not a product; you still have to build
everything yourself. CrewAI has no memory persistence or production orchestration.

Alii is production-grade: Alfred has been running for [X] days with zero manual
restarts. The watchdog automatically recovers failed services.
```

**"What models does it use?"**
```
Currently Ollama-based: Mistral 7B for fast tasks, Qwen 2.5 14B for reasoning,
neural-chat for conversation, dolphin-phi for lightweight. The router uses
keyword classification to pick the right model automatically.

You can swap in any Ollama-compatible model — llama3, gemma, mixtral, etc.
```

**"How is this different from Open WebUI?"**
```
Open WebUI is a chat interface for Ollama. Alii is an agent platform — it
takes autonomous actions, manages scheduled tasks, writes documents, monitors
your system, and coordinates specialized agents. Think of Open WebUI as a
keyboard; Alii is the whole autonomous system.
```

**"What's the licensing?"**
```
AGPL-3.0 for the core platform. This means you can self-host freely,
but if you build a SaaS on top of it, you need to open-source your changes
or get a commercial license. Same model as Grafana, MongoDB, etc.
```

**"Is this production-ready?"**
```
It's running in my personal production environment. I wouldn't call it
enterprise-ready yet — there's no multi-user auth, no encrypted memory,
no horizontal scaling. Those are on the roadmap. It's solid for solo use
and small teams with a Linux server.
```

**"What's your monetization plan?"**
```
Open core: free to self-host. Paid hosted tier coming (managed instance,
no server required). GitHub Sponsors for community support.
Long-term: enterprise on-premises licenses for regulated industries
that can't use cloud AI (healthcare, legal, finance).
```

---

## AFTER YOU POST

1. Set a 2-hour timer — respond to every comment within 2 hours
2. Never be defensive — "that's a great point, here's how I'm thinking about it"
3. If someone says something harsh: "Fair criticism, adding to the roadmap"
4. Share on Twitter/LinkedIn ONLY AFTER you have 10+ comments (creates social proof)
5. Screenshot the thread for your Product Hunt launch

---

## REALISTIC HN OUTCOMES

| Result | Front Page? | Traffic | Stars | Sponsors |
|--------|-----------|---------|-------|----------|
| <10 points | No | 50 | 0-2 | 0 |
| 10-50 points | Maybe | 500 | 10-30 | 0-2 |
| 50-200 points | Yes | 3,000 | 50-200 | 2-10 |
| 200+ points | Top 5 | 15,000+ | 500+ | 20-50 |
| 500+ points | #1 | 50,000+ | 2000+ | 100+ |

Tarsnap launched from HN. Hacker News has directly funded dozens of startups.
The cost to try: $0.
