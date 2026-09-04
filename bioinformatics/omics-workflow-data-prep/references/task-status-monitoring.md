# Monitoring & Resuming Snakemake Pipeline Status

When a user asks "how did the pipeline run go?" or "is the snakemake task done?",
and the snakemake process is no longer running (crashed, rebooted, tmux lost),
use this systematic approach to determine completion status and plan a resume.

## Step 1: Check if snakemake is still running

```bash
ps aux | grep -E "snakemake|apptainer|singularity|STAR|trimmomatic|stringtie" | grep -v grep
```

Also check for tmux/screen sessions:
```bash
tmux ls 2>/dev/null
screen -ls 2>/dev/null
```

If no processes found, the run has ended (either completed or crashed).

## Step 2: Check system uptime (reboot detection)

```bash
uptime
```

If uptime is short (minutes) relative to when the pipeline was launched, a system
reboot likely killed the snakemake process. This is the most common cause of
silent pipeline death.

## Step 3: Read the main workflow log

The orchestrator (`run.py`) writes to `<project>/log/<workflow_name>.log`.
Read the tail to find the snakemake command that was launched:

```bash
tail -100 <project>/log/<workflow_name>.log
```

The last lines should show the snakemake command with `--configfile`, `--cores`,
`--sdm apptainer`, `--singularity-args`, etc. If the log ends at the command
launch without a completion/error message, the process was killed externally.

## Step 4: Parse the config JSON to get expected outputs

```python
import json, os
with open('<output_dir>/raw.json') as f:
    cfg = json.load(f)
outfiles = cfg.get('outfiles', [])
existing = [f for f in outfiles if os.path.exists(f)]
missing = [f for f in outfiles if not os.path.exists(f)]
print(f'Total: {len(outfiles)}, Existing: {len(existing)}, Missing: {len(missing)}')
for m in missing:
    print(m)
```

This is the definitive way to know what's done and what's not. The `outfiles`
array in `raw.json` is the `rule all` target list.

## Step 5: Check output directory structure

The RNAseq pipeline produces these stages (each under `common/`):

| Stage | Directory | Content |
|-------|-----------|---------|
| 1 | `common/1_raw_fastq/` | Symlinked input fastq per sample |
| 2 | `common/2_trimmed_fastq/` | Trimmed fastq per sample |
| 3 | `common/3_raw_bam/` | STAR genome index + alignment BAMs |
| 4 | `common/4_stringtie_bam/` | STAR alignment BAMs for StringTie |
| 6 | `common/6_fusion_bam/` | STAR fusion index + alignment BAMs |

Final outputs outside `common/`:
- `transcripts/raw/<sample>/<sample>.gtf` - StringTie per-sample GTF
- `transcripts/raw/<sample>/<sample>_TE_chimeric_transcripts.txt` - TE chimeric
- `transcripts/stringtie_merged.gtf` - merged GTF
- `transcripts/TE_chimeric/` - TE chimeric visualization (PNG + TSV)
- `fusion/<sample>/<sample>_passed_fusions.tsv` - Arriba fusion calls
- `fusion/arriba_report/arriba_fusion_report.html` - fusion summary
- `RNAseq_report.pptx` - final report

## Step 6: Check .snakemake internal state

```bash
# Incomplete jobs (base64-encoded paths of in-progress files)
ls .snakemake/incomplete/ | wc -l

# Locks (stale locks prevent re-running)
ls .snakemake/locks/

# Last file modifications (shows when activity stopped)
find <output_dir>/ -type f -not -path "*/.snakemake/*" -printf "%T+ %p\n" | sort -r | head -20
```

## Step 7: Check for errors in the log

```bash
grep -i "error\|fail\|exception\|traceback" <project>/log/<workflow_name>.log | tail -30
```

Common errors:
- `PULP_CBC_CMD: Not Available` - ILP solver missing, falls back to greedy
  scheduler. Not fatal by itself but may indicate incomplete snakemake install.
- `CalledProcessError` in a rule - check that rule's log file
- `WorkflowError` / `RuleException` - rule-level failure, look at the named log

## Step 8: Check per-sample logs for the failing rule

Each sample has its own log directory: `<output_dir>/log/<sample>/`
containing per-tool logs like `trimming.txt`, `hisat2_align.log`,
`stringTie.log`, `TEChimericTranscripts.log`.

```bash
tail -30 <output_dir>/log/<sample>/<rule_log>
```

## Forensic crash diagnosis

When you need to determine WHY the pipeline died (not just what's missing),
use these techniques:

### Boot gap analysis

```bash
journalctl --list-boots | tail -5
```

Each line shows a boot ID with start/end timestamps. A gap between the end of
one boot and the start of the next = machine was powered off. Compare against
the last file modification time in the output directory to confirm the pipeline
was running during the gap.

```bash
# Last pipeline activity
find <output_dir>/ -type f -not -path "*/.snakemake/*" -printf "%T+ %p\n" | sort -r | head -5
# Previous boot logs
journalctl -b -1 | tail -30
```

Note: `journalctl -b -1` (previous boot) may have very sparse entries if
journald stopped logging before the system went down. The last journald entry
timestamp may be earlier than the last file write timestamp.

### Null bytes in STAR Log.out = hard kill

When STAR is killed mid-write (SIGKILL, power loss, OOM), its `Log.out` file
contains trailing null bytes (`\x00`) where the write buffer was not flushed.

```python
with open('<star_index_dir>/Log.out', 'rb') as f:
    data = f.read()
content = data.rstrip(b'\x00')
null_count = len(data) - len(content)
if null_count > 0:
    print(f"STAR was hard-killed: {null_count} null bytes at end")
```

This distinguishes a hard kill from a graceful error exit. A clean STAR
completion has no null bytes and ends with `... done` on the last SA file.

### Kernel upgrade pending

Check if an unattended-upgrade installed a new kernel that was activated on
reboot (common reason for unexpected reboots):

```bash
# Current kernel
uname -r
# When was it installed?
grep "<kernel-version>" /var/log/dpkg.log* | head -5
# apt history for unattended-upgrade triggers
grep "unattended-upgrade" /var/log/apt/history.log | tail -10
```

The kernel may have been installed days/weeks ago but only activated on the
reboot that killed the pipeline.

### OOM check

```bash
# systemd-oomd status (Ubuntu 22.04+)
systemctl status systemd-oomd
# Check previous boot for OOM kills
journalctl -b -1 | grep -i "oom\|killed process\|out of memory"
# Memory + swap (no swap = OOM kills happen faster)
free -h
swapon --show
```

Note: With 1TB+ RAM and no swap, OOM is unlikely for typical RNAseq runs
(36 samples x 48 cores). More likely causes are manual shutdown or power loss.

## Resuming after a crash

Snakemake is designed for resumption. Re-run the **same snakemake command** from
the log. Already-completed files are skipped (checked via metadata + mtime with
`--rerun-triggers mtime`).

**Before resuming**, clear stale locks if the process was killed:

```bash
# Only if no snakemake process is running
rm -rf <output_dir>/.snakemake/locks/
```

**Clean up incomplete STAR indices**: If STAR was killed during `genomeGenerate`
(detected via null bytes in Log.out), the index directory will have partial SA
files. Snakemake may not detect this as incomplete (the output file exists but
is corrupt). Remove the entire index directory so the rule re-runs:

```bash
rm -rf <output_dir>/common/3_raw_bam/index/ <output_dir>/common/3_raw_bam/tmp_star/
rm -rf <output_dir>/common/6_fusion_bam/index/ <output_dir>/common/6_fusion_bam/tmp_star/
```

The original command can be found in the main log file (grep for `Running: snakemake`).

## Pitfalls

- **Stale locks after crash**: If snakemake was killed (OOM, reboot), the lock
  files remain and block re-runs with "Error: Directory is locked". Remove
  `.snakemake/locks/` when certain no snakemake is running.
- **Incomplete files**: `.snakemake/incomplete/` contains base64-encoded paths
  of files that were being written when the process died. Snakemake will detect
  these and re-run the corresponding rules.
- **First-run errors may not appear in second run**: The log file is append-only.
  Errors from a first failed run (e.g., trim_galore failures) may appear in the
  log even though the second run succeeded for those samples. Always check the
  timestamp context of errors.
- **MetaUtil "Invalid design format" warnings**: These appear when the `design`
  column in meta.tsv uses a plain group name (mode A) but the MetaUtil code
  expects `ctrl_`/`exp_` prefix format (mode B). This is non-fatal for RNAseq
  (no comparison pairs needed) but means `group_pairs` and `sample_pairs` will
  be empty, which may affect downstream DESeq2 or visualization steps that
  rely on group information.
- **Corrupt STAR index after hard kill**: If STAR was killed during
  `genomeGenerate`, the index directory has partial SA files + null bytes in
  Log.out. Snakemake's mtime-based rerun may NOT detect this (files exist with
  correct mtime). Manually delete the index directory before resuming.
- **Sparse journald for previous boot**: `journalctl -b -1` may show very few
  entries (e.g., only sshd disconnects). Don't conclude "no kernel errors" from
  silence - the journal may simply not have captured them. Use file modification
  timestamps and STAR Log.out null bytes as primary evidence.
