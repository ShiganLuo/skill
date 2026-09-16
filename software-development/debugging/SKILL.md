---
name: debugging
description: "Debugging workflows — systematic root cause methodology, Python debugging (pdb, debugpy), and Node.js debugging (node inspect, CDP). Language-agnostic process plus language-specific tooling."
tags: [debugging, troubleshooting, root-cause, pdb, debugpy, node-inspect, cdp, breakpoints]
triggers:
  - "Debug this code"
  - "Why is this failing"
  - "Investigate this bug"
  - "Set a breakpoint"
  - "Debug Python code"
  - "Debug Node.js code"
  - "Post-mortem analysis"
  - "Attach to running process"
  - "Root cause analysis"
---

# Debugging

Class-level skill for all debugging workflows. Covers three layers:

1. **Systematic methodology** (Section A) — 4-phase root cause investigation process
2. **Python debugging** (Section B) — pdb REPL + debugpy remote (DAP)
3. **Node.js debugging** (Section C) — node inspect + Chrome DevTools Protocol

---

## Section A: Systematic Debugging (Methodology)

### Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

### When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

### The Four Phases

You MUST complete each phase before proceeding to the next.

#### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully** — Don't skip past errors or warnings. They often contain the exact solution. Read stack traces completely.

2. **Reproduce Consistently** — Can you trigger it reliably? What are the exact steps? If not reproducible → gather more data, don't guess.

3. **Check Recent Changes** — What changed that could cause this? Git diff, recent commits, new dependencies, config changes.

4. **Gather Evidence in Multi-Component Systems** — For EACH component boundary: log what data enters/exits, verify environment/config propagation, check state at each layer.

5. **Trace Data Flow** — Where does the bad value originate? What called this function with the bad value? Keep tracing upstream until you find the source.

**Phase 1 Completion Checklist:**
- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

#### Phase 2: Pattern Analysis

1. **Find Working Examples** — Locate similar working code in the same codebase
2. **Compare Against References** — If implementing a pattern, read the reference implementation COMPLETELY
3. **Identify Differences** — What's different between working and broken? List every difference.
4. **Understand Dependencies** — What other components does this need? What settings, config, environment?

#### Phase 3: Hypothesis and Testing

1. **Form a Single Hypothesis** — State clearly: "I think X is the root cause because Y"
2. **Test Minimally** — Make the SMALLEST possible change to test the hypothesis
3. **Verify Before Continuing** — Did it work? → Phase 4. Didn't work? → Form NEW hypothesis.
4. **When You Don't Know** — Say "I don't understand X". Don't pretend to know.

#### Phase 4: Implementation

1. **Create Failing Test Case** — Simplest possible reproduction. MUST have before fixing.
2. **Implement Single Fix** — Address the root cause identified. ONE change at a time.
3. **Verify Fix** — Run the specific regression test + full suite.
4. **If Fix Doesn't Work — The Rule of Three** — If ≥ 3 fixes failed: STOP and question the architecture.

### Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- **"One more fix attempt" (when already tried 2+)**

**ALL of these mean: STOP. Return to Phase 1.**

### Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| **"One more fix attempt" (after 2+ failures)** | 3+ failures = architectural problem. Question the pattern, don't fix again. |

### Pitfalls

#### Absence of expected diagnostic output is itself a signal

When a process dies, the FIRST thing to check is whether the expected death-notification is present or absent in the log. For example:
- Bash prints `Killed` to stderr when a child receives SIGKILL (OOM killer, `kill -9`, etc.). If stderr is redirected to a log file and "Killed" is NOT in the log, the process was NOT killed by an external signal — something else happened.
- JVM crashes produce `hs_err_pid*.log` files. Absence rules out JVM-level crashes.
- Segfaults produce `Segmentation fault` on stderr. Absence rules out SIGSEGV.

Do NOT jump to "it was killed by OOM" without checking that the expected diagnostic (`Killed`) is present. The absence of expected diagnostics is a first-class clue that narrows the hypothesis space.

#### Scope discipline: debug the immediate failure, not the orchestration

When a command/script fails in standalone execution, focus on the failure evidence (logs, exit codes, output files). Do NOT start by examining the pipeline/workflow/orchestration code that wraps it — if the unit test fails, the pipeline is irrelevant until the unit works. The user's framing ("单独执行会失败" / "standalone execution fails") is a hint to look at the command itself first.

#### Visual / external-rendering bugs: get the screenshot first, theorize second

When the bug is "X doesn't display correctly in tool/browser/IDE/dashboard", the most common failure mode is **rotating through text-only hypotheses (auto-scale, viewLimits, file format, assembly mismatch, URL expiry…) without ever actually looking at the rendered output**. Each hypothesis is plausible on paper and unverifiable without seeing the pixels.

Symptoms you're in this trap:
- User says "doesn't display" or "track invisible" or "blank"
- You propose a fix, user says "still doesn't work", you propose another
- You've never looked at what the user is actually seeing
- Each new theory addresses the *symptom description*, not an observed artifact

What "Phase 1 reproduction" means here:

1. **Get the rendered output.** Screenshot (browser tool, headless capture), export to a local viewer (IGV, matplotlib), or have the user paste an image. If the artifact is a file on disk, render it locally and look at it — don't trust your tool's interpretation of its contents.
2. **Local equivalent of the renderer.** If the bug is "UCSC doesn't show this bigwig region", open the bigwig in IGV/pyGenomeTracks/your-own matplotlib script on the same coordinates. If the local render matches the user's bad view, the file is the problem. If the local render is fine, the rendering tool is the problem.
3. **Observe the specific symptom, don't paraphrase.** "轨道看不见" (track invisible) is not the same as "values rendered as a flat line" (auto-scale too small) is not the same as "wrong region entirely" (coordinate bug). Each demands a different fix. A short multiple-choice question to the user — "is it (A) blank, (B) flat line, or (C) wrong content?" — beats three rounds of speculation.
4. **Stop theorizing once you've failed twice.** Two wrong hypotheses in a row with no new evidence means you're not investigating, you're guessing. Take a step back: ask the user for the actual rendered image, or render it yourself in a tool you control.

If you genuinely cannot get the rendered output (bot wall, missing tool, the user has gone offline), say so explicitly and stop. Do not produce a parade of untested "could it be X? or Y?" theories — the user will try each one, watch each fail, and lose trust.

---

## Section B: Python Debugger (pdb + debugpy)

### Overview

Three tools, picked by situation:

| Tool | When |
|---|---|
| **`breakpoint()` + pdb** | Local, interactive, simplest. Add `breakpoint()` in the source, run normally, get a REPL at that line. |
| **`python -m pdb`** | Launch an existing script under pdb with no source edits. Useful for quick poking. |
| **`debugpy`** | Remote / headless / "attach to already-running process." Talks DAP, scriptable from terminal, works for long-lived processes. |

**Start with `breakpoint()`.** It's the cheapest thing that works.

### When to Use

- A test fails and the traceback doesn't reveal why a value is wrong
- You need to step through a function and watch a collection mutate
- A long-running process misbehaves and you can't restart it
- Post-mortem: an exception fired and you want to inspect locals at the crash site

**Don't use for:** things `print()` / `logging.debug` solve in under a minute.

### pdb Quick Reference

Inside any pdb prompt (`(Pdb)`):

| Command | Action |
|---|---|
| `h` / `h cmd` | help |
| `n` | next line (step over) |
| `s` | step into |
| `r` | return from current function |
| `c` | continue |
| `unt N` | continue until line N |
| `j N` | jump to line N (same function only) |
| `l` / `ll` | list source around current line / full function |
| `w` | where (stack trace) |
| `u` / `d` | move up / down in the stack |
| `a` | print args of the current function |
| `p expr` / `pp expr` | print / pretty-print expression |
| `display expr` | auto-print expr on every stop |
| `b file:line` | set breakpoint |
| `b func` | break on function entry |
| `b file:line, cond` | conditional breakpoint |
| `cl N` | clear breakpoint N |
| `tbreak file:line` | one-shot breakpoint |
| `!stmt` | execute arbitrary Python (assignments included) |
| `interact` | drop into full Python REPL in current scope (Ctrl+D to exit) |
| `q` | quit |

The `interact` command is the most powerful — you can import anything, inspect complex objects, even call methods that mutate state.

### Recipe 1: Local breakpoint

Easiest. Edit the file:

```python
def compute(x, y):
    result = some_helper(x)
    breakpoint()           # <-- drops into pdb here
    return result + y
```

Run the code normally. You land at the `breakpoint()` line with full access to locals.

**Don't forget to remove `breakpoint()` before committing.**

### Recipe 2: Launch a script under pdb (no source edits)

```bash
python -m pdb path/to/script.py arg1 arg2
# Lands at first line of script
(Pdb) b path/to/script.py:42
(Pdb) c
```

### Recipe 3: Debug a pytest test

```bash
# Drop to pdb on failure:
pytest tests/path/to/test_file.py::test_name --pdb -p no:xdist

# Drop to pdb at the START of the test:
pytest tests/path/to/test_file.py::test_name --trace -p no:xdist

# Show locals in tracebacks without pdb:
pytest tests/path/to/test_file.py --showlocals --tb=long
```

Note: pdb does NOT work under xdist. Always use `-p no:xdist` or `-n 0`.

### Recipe 4: Post-mortem on any exception

```python
import pdb, sys
try:
    run_the_thing()
except Exception:
    pdb.post_mortem(sys.exc_info()[2])
```

Or wrap a whole script:
```bash
python -m pdb -c continue script.py
# When it crashes, pdb catches it and you're in the frame of the exception
```

### Recipe 5: Remote debug with debugpy (attach to running process)

For long-lived processes that can't be restarted.

#### Setup

```bash
pip install debugpy
```

#### Pattern A: Source-edit — process waits for debugger at launch

```python
import debugpy
debugpy.listen(("127.0.0.1", 5678))
print("debugpy listening on 5678, waiting for client...", flush=True)
debugpy.wait_for_client()
debugpy.breakpoint()       # optional: pause immediately once attached
```

#### Pattern B: No source edit — launch with `-m debugpy`

```bash
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client your_script.py arg1
```

#### Pattern C: Attach to an already-running process

```bash
python -m debugpy --listen 127.0.0.1:5678 --pid <pid>
```

Some kernels block ptrace-based injection. Fix with:
```bash
echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
```

#### Connecting a client from the terminal

**Option 1: `remote-pdb`** — usually what you actually want from a terminal agent:

```bash
pip install remote-pdb
```

In your code:
```python
from remote_pdb import set_trace
set_trace(host="127.0.0.1", port=4444)   # blocks until connection
```

Then from the terminal:
```bash
nc 127.0.0.1 4444
# You get a (Pdb) prompt exactly as if debugging locally.
```

**Option 2: Attach from VS Code / Cursor / Zed** — add a `launch.json`:

```json
{
  "name": "Attach to Process",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "127.0.0.1", "port": 5678 },
  "justMyCode": false
}
```

### Common Python Debugging Pitfalls

1. **pdb under pytest-xdist silently does nothing.** Always use `-p no:xdist` or `-n 0`.
2. **`breakpoint()` in CI / non-TTY contexts hangs the process.** Never commit it.
3. **`PYTHONBREAKPOINT=0`** disables all `breakpoint()` calls. Check the env if breakpoint isn't hitting.
4. **`debugpy.listen` blocks only if you also call `wait_for_client()`.** Without it, execution continues.
5. **Attach to PID fails on hardened kernels.** `ptrace_scope=1` (Ubuntu default). Workaround: `echo 0 > /proc/sys/kernel/yama/ptrace_scope`.
6. **Threads.** `pdb` only debugs the current thread. For multithreaded code, use `debugpy`.
7. **asyncio.** `pdb` works in coroutines but `await` inside pdb requires Python 3.13+ or workarounds.

---

## Section C: Node.js Inspect Debugger

### Overview

When `console.log` isn't enough, drive Node's built-in V8 inspector programmatically from the terminal.

Two tools, pick one:

- **`node inspect`** — built-in, zero install, CLI REPL. Best for quick poking.
- **CDP via `chrome-remote-interface`** — scriptable from Node/Python; best for automation.

**Prefer `node inspect` first.** It's always available and the REPL is fast.

### When to Use

- A Node test fails and you need to see intermediate state
- UI/TUI crashes or behaves wrong and you want to inspect React/Ink state
- You need to inspect a value in a closure that `console.log` can't reach

### Quick Reference: `node inspect` REPL

Launch paused on first line:

```bash
node inspect path/to/script.js
# or with tsx
node --inspect-brk $(which tsx) path/to/script.ts
```

The `debug>` prompt accepts:

| Command | Action |
|---|---|
| `c` or `cont` | continue |
| `n` or `next` | step over |
| `s` or `step` | step into |
| `o` or `out` | step out |
| `pause` | pause running code |
| `sb('file.js', 42)` | set breakpoint at file.js line 42 |
| `sb(42)` | set breakpoint at line 42 of current file |
| `sb('functionName')` | break when function is called |
| `cb('file.js', 42)` | clear breakpoint |
| `breakpoints` | list all breakpoints |
| `bt` | backtrace (call stack) |
| `list(5)` | show 5 lines of source around current position |
| `watch('expr')` | evaluate expr on every pause |
| `repl` | drop into REPL in current scope (Ctrl+C to exit REPL) |
| `exec expr` | evaluate expression once |
| `restart` | restart script |
| `kill` | kill the script |
| `.exit` | quit debugger |

### Attaching to a Running Process

```bash
# 1. Send SIGUSR1 to enable the inspector on an existing process
kill -SIGUSR1 <pid>
# Node prints: Debugger listening on ws://127.0.0.1:9229/<uuid>

# 2. Attach the debugger CLI
node inspect -p <pid>
# or by URL
node inspect ws://127.0.0.1:9229/<uuid>
```

To start a process with the inspector from the beginning:

```bash
node --inspect script.js           # listen on 127.0.0.1:9229, keep running
node --inspect-brk script.js       # listen AND pause on first line
node --inspect=0.0.0.0:9230 script.js   # custom host:port
```

For TypeScript via tsx:

```bash
node --inspect-brk --import tsx script.ts
```

### Programmatic CDP (scripting from terminal)

When you want to automate — set many breakpoints, capture scope state, script a repro — use `chrome-remote-interface`:

```bash
npm i -g chrome-remote-interface
node --inspect-brk=9229 target.js &
```

Driver script (save as `/tmp/cdp-debug.js`):

```javascript
const CDP = require('chrome-remote-interface');

(async () => {
  const client = await CDP({ port: 9229 });
  const { Debugger, Runtime } = client;

  Debugger.paused(async ({ callFrames, reason }) => {
    const top = callFrames[0];
    console.log(`PAUSED: ${reason} @ ${top.url}:${top.location.lineNumber + 1}`);

    // Walk scopes for locals
    for (const scope of top.scopeChain) {
      if (scope.type === 'local' || scope.type === 'closure') {
        const { result } = await Runtime.getProperties({
          objectId: scope.object.objectId,
          ownProperties: true,
        });
        for (const p of result) {
          console.log(`  ${scope.type}.${p.name} =`, p.value?.value ?? p.value?.description);
        }
      }
    }

    // Evaluate an expression in the paused frame
    const { result } = await Debugger.evaluateOnCallFrame({
      callFrameId: top.callFrameId,
      expression: 'typeof state !== "undefined" ? JSON.stringify(state) : "n/a"',
    });
    console.log('state =', result.value ?? result.description);

    await Debugger.resume();
  });

  await Runtime.enable();
  await Debugger.enable();

  // Set a breakpoint by URL regex + line
  await Debugger.setBreakpointByUrl({
    urlRegex: '.*app\\.tsx$',
    lineNumber: 119,       // 0-indexed
    columnNumber: 0,
  });

  await Runtime.runIfWaitingForDebugger();
})();
```

### Running Vitest Tests Under the Debugger

```bash
cd /path/to/project
node --inspect-brk ./node_modules/vitest/vitest.mjs run --no-file-parallelism src/app/foo.test.tsx
```

In another terminal: `node inspect -p <pid>`, then `sb('src/app/foo.tsx', 42)`, `cont`.

Use `--no-file-parallelism` (vitest) or `--runInBand` (jest) so only one worker exists.

### Common Node.js Debugging Pitfalls

1. **Wrong line numbers in TS source.** Breakpoints hit the emitted JS, not the `.ts`. Either break in the built `dist/*.js`, or enable sourcemaps (`node --enable-source-maps`).
2. **`--inspect` vs `--inspect-brk`.** `--inspect` starts the inspector but doesn't pause; your script races past your first breakpoint. Use `--inspect-brk` when you need to set breakpoints before any code runs.
3. **Port collisions.** Default is `9229`. If multiple Node processes are inspecting, pass `--inspect=0` (random port) and read the actual URL from `/json/list`.
4. **Child processes.** `--inspect` on a parent does NOT inspect its children. Use `NODE_OPTIONS='--inspect-brk'` to propagate.
5. **Background kills.** If you `Ctrl+C` out of `node inspect` while the target is paused, the target stays paused. Either `cont` first, or `kill` the target explicitly.
6. **Security.** `--inspect=0.0.0.0:9229` exposes arbitrary code execution. Always bind to `127.0.0.1` (the default).

### One-Shot Recipes

**"Why is this variable undefined at line X?"**
```bash
node --inspect-brk script.js &
node inspect -p $!
# debug>
sb('script.js', X)
cont
# paused. Now:
repl
> myVariable
> Object.keys(this)
```

**"What's the call path into this function?"**
```
debug> sb('suspectFn')
debug> cont
# paused on entry
debug> bt
```

**"This async chain hangs — where?"**
```
# Start with --inspect (no -brk), let it run to the hang, then:
debug> pause
debug> bt
# Now you see the stuck frame
```
