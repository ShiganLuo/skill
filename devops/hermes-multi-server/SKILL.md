---
name: hermes-multi-server
description: "Deploy Hermes across multiple servers with shared state — memory sync, skills sync, and independent session isolation."
version: 1.0.0
author: luoshg
metadata:
  hermes:
    tags: [hermes, multi-server, distributed, honcho, sync]
---

# Hermes Multi-Server Deployment

Deploy Hermes across multiple servers that need shared memory/skills but independent session state. Use when servers have different data, different owners, or cannot use shared storage (NFS/SMB).

## Architecture Overview

```
               ┌─────────────┐
               │    Honcho    │  (self-hosted, public server)
               │   Memory DB  │
               └──────┬──────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───┴───┐       ┌─────┴─────┐      ┌────┴────┐
│Server A│      │  Server B  │      │Server C │
│ Gateway│      │  Gateway   │      │ Gateway │
│state.db│      │  state.db  │      │state.db │
└────────┘      └───────────┘      └─────────┘
    │                 │                 │
    └─────────────────┼─────────────────┘
                      │
               ┌──────┴──────┐
               │  Skills Git │  (private repo)
               └─────────────┘
```

**What syncs:**
- Memory (via Honcho) — real-time across all servers
- Skills (via git) — pull on demand or cron

**What stays local:**
- Sessions (state.db) — each server has independent conversation history
- Data — never leaves the server

## Step 1: Deploy Honcho (Self-Hosted)

Honcho is the **only** Hermes memory backend that supports self-hosted via `base_url`. Mem0 plugin does NOT support self-hosted (SaaS-only).

```bash
# On your public server
git clone https://github.com/nousresearch/honcho.git
cd honcho

# Docker deployment
docker-compose up -d

# Or with custom port
docker run -d -p 8000:8000 honcho:latest
```

Verify Honcho is running:
```bash
curl http://your-server:8000/health
```

## Step 2: Configure Each Server

On each server that needs shared memory:

```bash
# Option A: Interactive setup
hermes memory setup
# Select Honcho, enter your server URL

# Option B: Manual config
cat > ~/.hermes/honcho.json << EOF
{
  "api_key": "your-api-key",
  "baseUrl": "http://your-public-server:8000"
}
EOF

# Option C: Environment variables
echo 'HONCHO_API_KEY=your-api-key' >> ~/.hermes/.env
echo 'HONCHO_BASE_URL=http://your-public-server:8000' >> ~/.hermes/.env
```

Verify:
```bash
hermes memory status
```

## Step 3: Skills Sync via Git

```bash
# Initialize skills repo (once, on any server)
cd ~/.hermes/skills
git init
git remote add origin <your-private-repo>
git add .
git commit -m "Initial skills"
git push -u origin main

# On other servers
cd ~/.hermes/skills
git init
git remote add origin <your-private-repo>
git pull origin main

# Update skills (run on each server periodically)
cd ~/.hermes/skills && git pull
```

## Step 4: Workspace Isolation (Optional)

Use different workspace IDs to separate memory by server:

```bash
# In honcho.json
{
  "api_key": "your-api-key",
  "baseUrl": "http://your-public-server:8000",
  "workspaceId": "server-a"  # or server-b, server-c
}
```

Or via environment:
```bash
HONCHO_WORKSPACE_ID=server-a
```

## Key Facts

### Memory Backends Comparison

| Backend | Self-Hosted | base_url Support | Notes |
|---------|-------------|------------------|-------|
| Honcho | ✅ Yes | ✅ Yes | Nous Research, best for self-hosted |
| Mem0 | ❌ No | ❌ No | SaaS-only (mem0.ai) |
| Supermemory | ❌ No | ❌ No | Check plugin for details |

### Config Resolution Order

Honcho config resolves from:
1. `$HERMES_HOME/honcho.json` (profile-local)
2. `~/.hermes/honcho.json` (default profile)
3. `~/.honcho/config.json` (global)
4. Environment variables (`HONCHO_API_KEY`, `HONCHO_BASE_URL`)

### Session Isolation

Sessions (state.db) are intentionally NOT synced:
- Each server maintains independent conversation history
- Prevents SQLite lock conflicts
- Allows different users/data per server

## Pitfalls

1. **Mem0 cannot self-host**: Don't attempt — use Honcho instead
2. **SQLite on NFS**: state.db on NFS causes lock corruption
3. **Skills conflict**: If two servers edit same skill, git merge conflicts occur
4. **Honcho version**: Ensure Honcho server >= 3.x for full feature support (peer cards, dialectic)
5. **Token limits**: Honcho context injection has token budget; configure `contextTokens` if needed

## Verification

```bash
# Check Honcho connection
hermes memory status

# Test memory read/write
hermes chat -q "Remember that my favorite color is blue"
hermes chat -q "What is my favorite color?"

# Check skills sync
hermes skills list
```

## References

- Honcho source: https://github.com/nousresearch/honcho
- Hermes memory plugin code: `~/.hermes/hermes-agent/plugins/memory/honcho/`
- Mem0 plugin (SaaS-only): `~/.hermes/hermes-agent/plugins/memory/mem0/`
