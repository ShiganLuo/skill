# Apptainer stdout buffering — empty log files in long-running tools

## Problem

A tool (pbmm2, minimap2, STAR, etc.) runs successfully inside an Apptainer SIF
for hours, the wrapper script redirects stdout/stderr to a log file:

```bash
bash .../wrapper.sh > .../log/run.log 2>&1
```

But the log file stays at **0 bytes** the entire time. The user assumes the
tool never started, then wastes time investigating the rule file.

## Root cause

Inside an Apptainer SIF, **stdout/stderr are block-buffered by default**, not
line-buffered. This is standard POSIX behavior: when stdout is not a TTY (it
is a pipe/file here), libc uses full buffering (4KB–64KB blocks).

Consequence: 5 hours × 100,000 lines of progress → data sits in the libc
buffer until the buffer fills up or the process exits. For long alignments
(7700+ CPU-minutes on PacBio CCS vs ~3GB reference), the buffer NEVER fills
up enough to flush, and the log file stays at 0 bytes until the process exits.

`set -x` in the wrapper does NOT force line-buffering — it just adds trace
output, which itself goes through the same buffered stdout.

## Quick diagnostic — is the tool actually running?

Before assuming the rule failed, **check the live process**:

```bash
ps auxf | grep -E "pbmm2|snakemake" | grep -v grep
```

What you should see:
- `snakemake` parent → `Apptainer runtime parent: <tool>.sif` → bash wrapper
  → `<tool>` process (CPU >100%, accumulating CPU time)
- Multiple samples running in parallel = multiple wrapper processes

If the tool process exists with high CPU% and growing CPU time, **it IS
running and producing output — the output is just not in the file system yet
because of stdout buffering.**

## Verification

Three signals together prove "tool running, log buffered":

1. `ls -la <logfile>` shows size=0 but Birth/Modify time = process start time
2. `ps auxf | grep <tool>` shows the tool process with growing CPU time
3. The wrapper script file exists (rule created it successfully)

## Fix

Force line-buffering on stdout/stderr from inside the wrapper script:

```bash
stdbuf -oL -eL pbmm2 align ... 2>&1 | tee -a <logfile>
```

Or wrap the whole wrapper:

```bash
#!/bin/bash
exec stdbuf -oL -eE bash "$@"
```

For tools that ignore `stdbuf` (some tools reset buffering themselves), use
`script` or `unbuffer`:

```bash
unbuffer pbmm2 align ... 2>&1 | tee <logfile>
```

## User preference — always check ps first

When the user asks "why is the log empty / is the tool running?", the FIRST
diagnostic is `ps aux | grep <tool>` — never analyze the rule's source code
or speculate about file paths until you've confirmed the process is (or isn't)
alive. The user has explicitly corrected: "你太蠢了，直接查看pbmm2进程状态就行".

Pitfall chain:
1. User reports "log is empty"
3. (Excerpted from session at 2026-09-22, Fiberseq 5hr alignment)