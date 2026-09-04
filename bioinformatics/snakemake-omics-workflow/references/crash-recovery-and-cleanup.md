# Crash recovery and cleanup for interrupted Snakemake runs

Use this when a Snakemake workflow was interrupted by a system reboot, power loss,
or SIGKILL -- NOT by a snakemake-level error. The workflow can be safely resumed
after cleaning up partial outputs.

## Diagnosing the kill cause

### System reboot / power loss indicators

1. **`last reboot` / `who -b`** shows a reboot timestamp between the last file
   write and the current time.
2. **`journalctl --list-boots`** shows a gap between boot -1 end and boot 0 start
   (machine was offline for hours).
3. **`ps aux | grep snakemake`** returns nothing -- process is gone.
4. **STAR Log.out has trailing null bytes** (`\x00`): STAR was killed mid-write,
   its stdio buffer flushed null bytes to disk. Check with:
   ```python
   with open('index/Log.out', 'rb') as f:
       data = f.read()
   null_count = len(data) - len(data.rstrip(b'\x00'))
   ```
5. **0-byte SA files** in STAR index directory: `find index/ -name "SA_*" -size 0`
6. **No OOM messages** in `journalctl -b -1 | grep -i oom` and `dmesg | grep -i oom`.

### OOM kill indicators

1. `journalctl -b -1 | grep -i "oom\|killed process"` shows OOM killer activity.
2. `systemd-oomd` is enabled (`systemctl status systemd-oomd`).
3. Machine has limited RAM or no swap (`free -h`, `swapon --show`).

### Snakemake-level error indicators

1. The log file (`--log` output) contains `Error in rule` / `CalledProcessError` /
   `WorkflowError` / `Exiting because a job execution failed`.
2. The snakemake process exited with non-zero code but the system did NOT reboot.
3. Individual rule log files contain tool-level error messages.

## What to clean up before rerunning

### 1. Incomplete STAR indexes

STAR `genomeGenerate` writes SA files sequentially. If killed mid-write, the
index is unusable. Delete the ENTIRE index directory and tmp_star:

```bash
rm -rf /path/to/output/common/3_raw_bam/index
rm -rf /path/to/output/common/3_raw_bam/tmp_star
rm -rf /path/to/output/common/6_fusion_bam/index
rm -rf /path/to/output/common/6_fusion_bam/tmp_star
```

**Do NOT partially clean** (e.g. removing only 0-byte SA files). STAR index is
an atomic unit -- if any part is incomplete, the whole index must be rebuilt.

Detection checklist:
- `find index/ -name "SA_*" -size 0` -- 0-byte SA files
- `python3 -c "..."` on Log.out -- trailing null bytes
- Missing `SA_<N>` files (compare SA count between the two indexes if both exist)
- Log.out does NOT contain a "finished" / success line

### 2. Snakemake locks

```bash
rm -f /path/to/output/.snakemake/locks/0.input.lock
rm -f /path/to/output/.snakemake/locks/0.output.lock
```

### 3. Snakemake incomplete markers

```bash
rm -f /path/to/output/.snakemake/incomplete/*
```

These are base64-encoded path markers that prevent snakemake from using partial
outputs. They must be removed after cleanup.

### 4. Zero-byte output files

Any output file that was created (touched) but never written to because the
process was killed:

```bash
find /path/to/output/transcripts/raw/ -name "*_TE_chimeric_transcripts.txt" -size 0 -delete
```

Check all output directories for 0-byte files that should have content.

## Rerunning with --rerun-triggers mtime

The Omics workflow's `run.sh` already includes `--rerun-triggers mtime`. This
means snakemake will skip any output file that exists and has a newer mtime than
its inputs. Only the cleaned-up (deleted) outputs will be regenerated.

```bash
cd /path/to/workflow/Omics
export PATH="/home/luosg/miniconda3/envs/smk/bin:$PATH"
bash run.sh
```

The `smk` conda environment has snakemake 9.x installed. The run.sh calls
`run.py` which builds the snakemake command with `--sdm apptainer` and
auto-generated `--singularity-args`.

## Verification after rerun

1. Check snakemake process is running: `ps aux | grep snakemake | grep -v grep`
2. Check log file for errors: `tail -20 /path/to/log/4RNAseq.log`
3. Verify STAR index completion: Log.out should have no null bytes, SA files
   should all be non-zero.
4. Verify all expected outfiles exist:
   ```python
   import json, os
   with open('raw.json') as f:
       cfg = json.load(f)
   missing = [f for f in cfg['outfiles'] if not os.path.exists(f)]
   print(f'Missing: {len(missing)} / {len(cfg["outfiles"])}')
   ```
