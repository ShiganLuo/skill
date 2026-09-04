# Converting shell: rules to run: blocks

## When to use

Batch-converting legacy `shell:` rules to the unified `run:` block style. Each rule needs: `include:` replacement, `conda:` directive, `run:` block with standard template, and `os.makedirs` for script output directories.

## Conversion checklist (per rule)

1. **Replace manual imports with `include:`**
   - Remove `from snakemake.logging import logger`, `import os`, `import time` at file top
   - Add `include: "../common/common.smk"` (provides all three + `setup_logger`, `ROOT_DIR`)
   - Only do this ONCE per file, not per rule

2. **Add `conda:` directive** (if missing)
   - Place before `run:`, after `params:`
   - Use `"<tool>.yaml"` relative path

3. **Convert `shell:` block to `run:` block**
   - Replace `shell: """..."""` with the standard template (see skill main doc)
   - Key elements: `log_path = str(log)`, `setup_logger()`, `cmd` list, `shell(f"bash {script} >> {log_path} 2>&1")`, `try/except/finally`

4. **Add `os.makedirs` before writing the shell script**
   - The script output directory may not exist yet — Snakemake only auto-creates `output:` paths
   - Pattern: `os.makedirs(os.path.dirname(script), exist_ok=True)` before `open(script, "w")`
   - This pitfall (#9 in main skill) is easy to miss during conversion

5. **Handle multi-command shell blocks**
   - Original `shell:` may have multiple commands (e.g. `mkdir -p` + tool invocation)
   - In `run:` block: build `cmd_str` by concatenating multiple command strings, or use multiple `shell()` calls
   - Example: `mkdir -p` + `hisat2-build` → two lines in the script file

6. **Redirect stdout correctly**
   - Original `shell:` uses `> {log} 2>&1` (overwrite)
   - Standard `run:` template uses `>> {log_path} 2>&1` (append) — matches `open(log_path, "w").close()` that clears first
   - If original uses `> {output.report} 2>> {log}` (split stdout/stderr), preserve that pattern in the `run:` block

## Common pitfalls

### Snakemake version requirement
`conda:` + `run:` requires Snakemake 9.x+. Version 8.x rejects with:
```
RuleException: Conda environments are only allowed with shell, script, notebook, or wrapper directives
```
Upgrade: `pip install --upgrade snakemake>=9.0`

### Undefined output references in original shell:

The original `shell:` block may reference `{output.summary}` or similar outputs that are NOT declared in the rule's `output:` section. This was a bug in the original code that happened to work because Snakemake didn't validate shell template strings strictly.

**When converting:** Replace undefined output references with `{log_path}` or the appropriate declared output. Document the change.

**Example (neodisambiguate):**
```python
# Original (bug — output.summary not declared)
shell: """... > {output.summary} 2> {log}"""

# Converted (fixed — redirect to log)
shell(f"bash {script} >> {log_path} 2>&1")
```

### Script directory doesn't exist

When `run:` block writes a shell script to a sample-specific directory, that directory may not exist yet. Snakemake only creates directories for declared `output:` paths.

**Fix:** Always add `os.makedirs(os.path.dirname(script), exist_ok=True)` before `open(script, "w")`.

### Preserving conditional logic

`shell:` blocks with inline conditionals (e.g. `if params.adapters: cmd += ["--adapter", ...]`) must be preserved exactly in the `run:` block. The conversion only changes the outer structure, not the command-building logic.

## Verification script pattern

After batch conversion, verify with an ad-hoc Python script using regex-based structural checks (NOT `py_compile` — .smk files are not valid Python):

```python
import re, sys

FILES = {
    "module/smk": {"run": N, "shell": 0, "rules": ["rule1", "rule2"]},
}
BASE = "/path/to/modules"

for rel, expect in FILES.items():
    text = open(f"{BASE}/{rel}").read()
    run_count = len(re.findall(r'^\s+run:', text, re.M))
    shell_count = len(re.findall(r'^\s+shell:', text, re.M))
    assert run_count == expect["run"], f"{rel}: expected {expect['run']} run:, got {run_count}"
    assert shell_count == expect["shell"], f"{rel}: expected {expect['shell']} shell:, got {shell_count}"
    for rule in expect["rules"]:
        assert f'setup_logger("{rule}"' in text, f"{rel}: rule '{rule}' missing setup_logger"
    assert 'include: "../common/common.smk"' in text
    assert "try:" in text and "except Exception" in text
    print(f"OK: {rel}")
```

Also use `scripts/verify-smk-structure.py` for single-module structural checks.

## try/except without finally is acceptable

The template shows `try/except/finally`, but `try/except` alone works when the `except` block logs the error and re-raises. The `finally` block is only needed for completion logging regardless of outcome. In practice, most conversions use `try/except` only (no `finally`):

```python
run:
    log_path = str(log)
    try:
        open(log_path, "w").close()
        rule_logger = setup_logger("rule_name", log_file=log_path)
        current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        rule_logger.info(f"Start rule_name at {current_time}")
        script = os.path.join(sample_outdir, f"rule_name_{current_time}.sh")
        os.makedirs(os.path.dirname(script), exist_ok=True)
        with open(script, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"command args\n")
        shell(f"bash {script} > {log_path} 2>&1")
    except Exception as e:
        with open(log_path, "a") as f:
            f.write(f"rule_name failed: {e}\n")
        logger.error(f"rule_name failed: {e}")
        raise e
```

Key differences from `shell:` redirect semantics:
- `> {log_path} 2>&1` — overwrite (original shell: style, clears on start)
- `>> {log_path} 2>&1` — append (use with `open(log_path, "w").close()` pre-clear)

Both work. Match the original shell block's intent. If the original used `> {log}`, use `>`. If it used `>> {log}`, use `>>`.

## Multi-line shell commands with pipes and continuations

When the original `shell:` block has multi-line commands with `\` continuations and pipes, write them as separate `f.write()` lines in the script file. Do NOT try to `" ".join(cmd)` these — the pipes and continuations break the list-join pattern.

### Pattern A: Simple command (use cmd list + join)

```python
# Original shell:
#   {params.tool} --arg1 {input.x} --arg2 {output.y} > {log} 2>&1

cmd = [params.tool, "--arg1", input.x, "--arg2", output.y]
with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(" ".join(cmd) + "\n")
```

### Pattern B: Multi-line with pipes/continuations (use f.write per line)

```python
# Original shell:
#   {BEDTOOLS} intersect -abam {input.bam} -b {input.bed} -u \
#       | {SAMTOOLS} sort -n -@ {threads} -T {tmpdir} \
#       -o {output.bam}
#   {SAMTOOLS} fastq -@ {threads} {output.bam} \
#       | gzip > {output.fq}

with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(f"{BEDTOOLS} intersect -abam {input.bam} -b {input.bed} -u \\\n")
    f.write(f"    | {SAMTOOLS} sort -n -@ {threads} -T {tmpdir} \\\n")
    f.write(f"    -o {output.bam}\n")
    f.write(f"{SAMTOOLS} fastq -@ {threads} {output.bam} \\\n")
    f.write(f"    | gzip > {output.fq}\n")
```

### Pattern C: sed with embedded regex (use f.write per line)

```python
# Original shell:
#   sed '1s/unique species A pairs/unique species {params.speciesA} pairs/; \
#       1s/unique species B pairs/unique species {params.speciesB} pairs/' \
#       {input.summary} > {output.clean_summary}

with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(f"sed '1s/unique species A pairs/unique species {params.speciesA} pairs/; \\\n")
    f.write(f"    1s/unique species B pairs/unique species {params.speciesB} pairs/' {input.summary} > {output.clean_summary}\n")
```

### Pattern D: Multi-command with sequential steps

```python
# Original shell:
#   python {params.combineTE} -p TEcount -i {params.indir} -o {output.outfile_id} > {log} 2>&1
#   python {params.geneId2Name} -c {output.outfile_id} -g {params.gtf} -o {output.outfile_name} >> {log} 2>&1

with open(script, "w") as f:
    f.write("#!/bin/bash\n")
    f.write(f"python {params.combineTE} -p TEcount -i {params.indir} -o {output.outfile_id}\n")
    f.write(f"python {params.geneId2Name} -c {output.outfile_id} -g {params.gtf} -o {output.outfile_name}\n")
```

Note: The individual `> {log} 2>&1` redirects from the original are removed — the outer `shell(f"bash {script} > {log_path} 2>&1")` captures all output.

## Imports that survive conversion

`include: "../common/common.smk"` provides: `setup_logger`, `time`, `os`, `shutil`, `sys`, `tempfile`, `ROOT_DIR`, `logger` (from snakemake.logging).

**Remove:** `import os`, `import time` (provided by common.smk)

**Keep `from snakemake.logging import logger`** when the file has helper functions (e.g. `get_alignment_input`, `get_bwaMem2_index`) that reference `logger` directly. common.smk imports it at module scope so it's technically redundant, but the explicit import makes the dependency clear and avoids confusion when reading the file in isolation.

**Keep:** `from typing import ...` (not provided by common.smk), `import logging` if the module uses its own logger configuration, any module-specific imports.

## Batch verification script

After converting multiple files in one session, run an ad-hoc verification script to catch structural mismatches:

```python
#!/usr/bin/env python3
"""Verify converted .smk files: syntax, structure, and pattern compliance."""
import re, sys

FILES = [
    "/path/to/modules/TEtranscripts/TEtranscripts.smk",
    "/path/to/modules/disambiguate/disambiguate.smk",
    # ... all converted files
]

EXPECTED_RULES = {
    "TEtranscripts/TEtranscripts.smk": ["TEcount", "combine_TEcount", "TElocal", "combine_TElocal"],
    "disambiguate/disambiguate.smk": ["ngs_disambiguate", "disambiguate_sort_rename", "disambiguate_report"],
    # ...
}

errors = []
for fpath in FILES:
    short = "/".join(fpath.split("/modules/")[-1].split("/"))
    content = open(fpath).read()

    # 1. Must have include common.smk
    if 'include: "../common/common.smk"' not in content:
        errors.append(f"{short}: MISSING include common.smk")

    # 2. No bare shell: blocks
    bare_shell = re.findall(r'^\s+shell:\s*$', content, re.MULTILINE)
    run_blocks = re.findall(r'^\s+run:\s*$', content, re.MULTILINE)
    if len(bare_shell) > len(run_blocks):
        errors.append(f"{short}: bare shell: blocks found ({len(bare_shell)} shell vs {len(run_blocks)} run)")

    # 3. setup_logger count == run: count
    setup_count = content.count("setup_logger(")
    run_count = len(run_blocks)
    if run_count != setup_count:
        errors.append(f"{short}: run ({run_count}) != setup_logger ({setup_count})")

    # 4. Check expected rules exist
    expected = EXPECTED_RULES.get(short, [])
    for rule_name in expected:
        if f"rule {rule_name}:" not in content:
            errors.append(f"{short}: missing rule {rule_name}")

    # 5. try/except in each run block
    try_count = len(re.findall(r'^\s+try:\s*$', content, re.MULTILINE))
    except_count = len(re.findall(r'except Exception as e:', content))
    if try_count != run_count:
        errors.append(f"{short}: try ({try_count}) != run ({run_count})")
    if except_count != run_count:
        errors.append(f"{short}: except ({except_count}) != run ({run_count})")

    # 6. log_path = str(log) in each run block
    log_path_count = content.count('log_path = str(log)')
    if log_path_count != run_count:
        errors.append(f"{short}: log_path ({log_path_count}) != run ({run_count})")

    # 7. shell(f"bash {script}") in each run block
    shell_exec = len(re.findall(r'shell\(f"bash \{script\}', content))
    if shell_exec != run_count:
        errors.append(f"{short}: shell exec ({shell_exec}) != run ({run_count})")

    # 8. Logger import — keep if helper functions reference logger directly
    # (common.smk provides it, but explicit import aids readability)

    print(f"✓ {short}: {run_count} run blocks, {setup_count} setup_logger, {try_count} try, {except_count} except")

if errors:
    print(f"\n❌ {len(errors)} ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"\n✅ All {len(FILES)} files passed verification")
```

Key checks:
- `run:` count = `setup_logger(` count = `try:` count = `except` count (all must match)
- No bare `shell:` blocks (only `shell()` calls inside `run:` blocks)
- `include: "../common/common.smk"` present
- `from snakemake.logging import logger` — acceptable when helper functions reference `logger`
- All expected rule names present
- `log_path = str(log)` present in every run block
- `shell(f"bash {script}")` execution in every run block

## Named log outputs (log.log)

When a rule declares `log: log = logdir + "/{sample_id}/tool.txt"`, the log is a named attribute. In `run:` blocks, `str(log)` resolves correctly — no need for `str(log.log)`. The original `shell:` uses `{log.log}` for interpolation, but `str(log)` in `run:` works for both named and unnamed logs.

## Batch conda: addition for run: blocks (no shell→run conversion needed)

When rules already have `run:` blocks but are missing `conda:`, a simple regex insertion suffices:

```python
# Find rules with run: but no conda:
pattern = rf'(rule {rule_name}:(?:.*?\n)*?)(    run:)'
match = re.search(pattern, content)
# Insert conda: before run:
conda_line = f'    conda:\n        "{yaml_ref}"\n'
new_content = content[:match.start()] + match.group(1) + conda_line + match.group(2) + content[match.end():]
```

This handles the common case where 40+ rules need `conda:` added without any logic changes.

## Batch verification after conversion

```bash
# Count run: vs shell: vs conda: per file
for f in $(find modules -name "*.smk"); do
    run=$(grep -c "    run:" "$f")
    shell=$(grep -c "    shell:" "$f")
    conda=$(grep -c "conda:" "$f")
    if [ "$shell" -gt 0 ] || [ "$conda" -eq 0 ]; then
        echo "$f: run=$run shell=$shell conda=$conda"
    fi
done
```

## Verification: search the ENTIRE run: block, not a fixed window

When writing ad-hoc verification scripts, do NOT assume a fixed line count between `run:` and `except Exception`. Large rules (8+ commands like exomePeak, cnvkit_batch) can span 50+ lines. Use the next `run:` or EOF as the block boundary:

```python
# CORRECT: find block boundary dynamically
run_blocks = [i for i, l in enumerate(lines) if re.match(r'\s+run:\s*$', l)]
for idx, rb in enumerate(run_blocks):
    end = run_blocks[idx+1] if idx+1 < len(run_blocks) else len(lines)
    block = "\n".join(lines[rb:end])
    # check patterns in block

# WRONG: fixed 30-line window
block = "\n".join(lines[rb:rb+30])  # misses patterns in large rules
```

## Use write_file for full rewrites, patch for surgical edits

When converting multiple rules in a single file, `write_file` (full file rewrite) is safer than `patch` because:
- `patch` uses fuzzy matching — if `shell:` appears multiple times, it can't disambiguate
- Full rewrite guarantees the file is exactly what you intend
- For single-rule edits in a file with many rules, `patch` with enough context lines works

Rule of thumb: if converting >50% of the rules in a file, rewrite the whole file.

## Example: complete conversion

### Before (hisat2_index):
```python
from snakemake.logging import logger
import os
import time

rule hisat2_index:
    input:
        fasta = fasta
    output:
        index = expand(outdir + "/index/genome.{idx}.ht2", idx=[1,2,3,4,5,6,7,8])
    threads: 8
    params:
        prefix = outdir + "/index/genome",
        HISAT2_BUILD = config.get('Procedure',{}).get('hisat2-build') or 'hisat2-build'
    log:
        logdir + "/index/hisat2_build.log"
    shell:
        """
        mkdir -p $(dirname {params.prefix})
        {params.HISAT2_BUILD} -p {threads} {input.fasta} {params.prefix} > {log} 2>&1
        """
```

### After:
```python
include: "../common/common.smk"

rule hisat2_index:
    input:
        fasta = fasta
    output:
        index = expand(outdir + "/index/genome.{idx}.ht2", idx=[1,2,3,4,5,6,7,8])
    threads: 8
    params:
        prefix = outdir + "/index/genome",
        HISAT2_BUILD = config.get('Procedure',{}).get('hisat2-build') or 'hisat2-build'
    log:
        logdir + "/index/hisat2_build.log"
    conda:
        "hisat2.yaml"
    run:
        log_path = str(log)
        try:
            open(log_path, 'w').close()
            logger = setup_logger(logger_name="hisat2_index", log_file=log_path)
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            logger.info(f"Start hisat2 index at {current_time}")
            script = os.path.join(outdir, f"index/hisat2_index_{current_time}.sh")
            os.makedirs(os.path.dirname(script), exist_ok=True)
            cmd = ["mkdir", "-p", os.path.dirname(str(params.prefix))]
            cmd_str = " ".join(cmd) + "\n"
            cmd2 = [str(params.HISAT2_BUILD), "-p", str(threads), str(input.fasta), str(params.prefix)]
            cmd_str += " ".join(cmd2) + "\n"
            with open(script, 'w') as f:
                f.write(cmd_str)
            shell(f"bash {script} >> {log_path} 2>&1")
        except Exception as e:
            with open(log_path, 'a') as f:
                f.write(f"Error: {e}\n")
            logger.error(f"Error: {e}")
            raise e
        finally:
            current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            logger.info(f"Completed at {current_time}")
```
