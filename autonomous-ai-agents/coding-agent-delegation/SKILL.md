---
name: coding-agent-delegation
description: "Delegate coding tasks to external AI agent CLIs: Claude Code, Codex, OpenCode."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Delegation, Claude-Code, Codex, OpenCode, Automation, CLI]
---

# Coding Agent Delegation

Delegate coding tasks to external autonomous AI coding agent CLIs orchestrated from Hermes. All three supported agents follow the same fundamental pattern: authenticate, delegate a task, monitor progress, collect results.

## Choosing an Agent

| Agent | Provider | Install | Best for |
|-------|----------|---------|----------|
| **Claude Code** | Anthropic | `npm install -g @anthropic-ai/claude-code` | Complex multi-step coding, deep reasoning, code review |
| **Codex** | OpenAI | `npm install -g @openai/codex` | Fast one-shot tasks, batch issue fixing, parallel worktrees |
| **OpenCode** | Open-source (multi-provider) | `npm i -g opencode-ai@latest` | Provider-agnostic work, long sessions, flexible model choice |

All three require a git repository for code tasks (Codex refuses to run outside one; others recommend it).

## Common Orchestration Patterns

### Pattern 1: One-Shot Task (Non-Interactive)

The cleanest path. Agent runs a bounded task, returns result, exits. No PTY needed.

```
# Claude Code (print mode — preferred)
terminal(command="claude -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10", workdir="/path/to/project", timeout=120)

# Codex
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)

# OpenCode
terminal(command="opencode run 'Add retry logic to API calls and update tests'", workdir="~/project")
```

### Pattern 2: Interactive Session (Background)

For iterative work requiring multiple exchanges. Start in background, send prompts, monitor progress.

```
# Claude Code — tmux-based orchestration
terminal(command="tmux new-session -d -s claude-work -x 140 -y 40")
terminal(command="tmux send-keys -t claude-work 'cd /path/to/project && claude' Enter")
terminal(command="sleep 5 && tmux send-keys -t claude-work 'Refactor the auth module' Enter")
terminal(command="sleep 15 && tmux capture-pane -t claude-work -p -S -50")

# Codex / OpenCode — background process
terminal(command="opencode", workdir="~/project", background=true, pty=true)
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow")
process(action="poll", session_id="<id>")
```

### Pattern 3: Parallel Tasks

Run multiple independent tasks simultaneously using separate workdirs or worktrees.

```
# Create isolated worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")

# Launch agents in parallel
terminal(command="codex --yolo exec 'Fix issue #78'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="opencode run 'Fix issue #99'", workdir="/tmp/issue-99", background=true, pty=true)
```

### Pattern 4: PR Review

```
# Claude Code (print mode)
terminal(command="git diff main...feature-branch | claude -p 'Review this diff for bugs and security issues' --max-turns 1", timeout=60)

# Claude Code (from PR number)
terminal(command="claude -p 'Review this PR thoroughly' --from-pr 42 --max-turns 10", workdir="/path/to/repo", timeout=120)

# Codex
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)

# OpenCode
terminal(command="opencode pr 42", workdir="~/project", pty=true)
```

## Agent-Specific Details

For detailed CLI flags, configuration, hooks, MCP integration, and pitfalls specific to each agent, load the dedicated subskill:

- **Claude Code**: `skill_view(name="claude-code")` — print mode deep dive, tmux orchestration, PTY dialog handling, JSON schema output, session continuation, hooks, MCP, CLAUDE.md
- **Codex**: `skill_view(name="codex")` — full-auto/yolo modes, batch PR reviews, worktree patterns
- **OpenCode**: `skill_view(name="opencode")` — multi-provider auth, session management, TUI keybindings, stats

## General Rules for All Agents

1. **Prefer one-shot mode for single tasks** — cleaner, no dialog handling, structured output
2. **Use background mode for long tasks** — monitor with `process(action="poll"|"log")`
3. **Always set `workdir`** — keep the agent focused on the right project directory
4. **Set limits** — use `--max-turns` (Claude Code) or timeouts to prevent runaway loops and costs
5. **Monitor progress** — check periodically, look for completion indicators
6. **Clean up** — kill tmux sessions and background processes when done
7. **Report results** — summarize what the agent did and what changed
8. **Use permission restrictions** — limit capabilities to what the task needs (`--allowedTools`, `--full-auto`, etc.)
