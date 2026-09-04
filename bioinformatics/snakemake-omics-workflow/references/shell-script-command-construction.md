# Command construction for Snakemake run: blocks and helper scripts

Use this reference when constructing tool commands inside Snakemake `run:` blocks or standalone helper scripts. Prefer list-based command construction over f-string concatenation.

## Two-layer rule: .smk uses shell scripts, bin/ uses direct subprocess

There are TWO distinct command-construction patterns depending on the layer:

### .smk layer: modules.md shell-script pattern (REQUIRED)

The `.smk` `run:` block MUST follow `modules/modules.md` spec: construct `cmd = [...]` list, write `" ".join(cmd)` into a timestamped `.sh` script, execute via `shell(f"bash {script} >> {log_path} 2>&1")`. This is non-negotiable - the user explicitly corrected this: "snakefile还是要用shell记录完整调用命令,遵循module.md规范".

Key elements:
- `open(log_path, "w").close()` - clear old log
- `setup_logger(...)` from common.smk
- `current_time` timestamp for script filename
- `cmd = [...]` list construction
- `with open(script, "w") as f: f.write(" ".join(cmd) + "\n")`
- `shell(f"bash {script} >> {log_path} 2>&1")`
- `try/except` with `raise e`
- Do NOT use `shlex.join` or `import shlex` in the `.smk`
- Do NOT use `shell(shlex.join(cmd))` - this bypasses the `.sh` recording

### bin/ script layer: direct subprocess execution

When logic is extracted to a standalone `bin/` script (see `references/run-block-script-extraction.md`), commands should be executed directly via `subprocess.run(cmd)` - NOT by generating a `.sh` file and running `subprocess.run(["bash", script])`. The user considers the Python->shell->bash indirection "变扭" (convoluted) for the `bin/` layer.

- `shlex.join(cmd)` is still used, but only for **logging** (writing `.cmd.log` for reproducibility), never as the execution path.
- Shell-variable quoting issues (`"$index"`, `$reads` word-splitting) are eliminated because variables are native Python strings in a `list[str]`.

## Why lists, not string concatenation

String concatenation (`f"{STAR} --runThreadN {threads} ..."`) is fragile: paths with spaces break, nested quotes are error-prone, and multi-value options need manual tokenization. Construct each command as a `list[str]` so every token is correctly handled.

## Pattern: all-Python-side commands (direct subprocess)

When every argument is a Python string known at execution time:

```python
cmd = [STAR, "--runThreadN", str(threads),
       "--genomeDir", str(genome_index),
       "--readFilesIn", *fastq_paths,
       "--readFilesCommand", "zcat",
       *star_options("pass1", paired),  # returns list[str]
       "--outSAMtype", "BAM", "SortedByCoordinate",
       "--outFileNamePrefix", pass1_prefix]
subprocess.run(cmd, stdout=log_handle, stderr=subprocess.STDOUT, check=True)
```

Key points:
- Helper functions (e.g. `star_options`) should return `list[str]`, not a joined string. Use `*` to splat into the command list.
- Multi-value options like STAR's `clip5pNbases "20 0"` must be split into separate tokens: `args.extend(str(value).split())`.
- `samtools_fastq`-style helpers should return `list[list[str]]` (one inner list per command).

## Pattern: pipelines (subprocess.Popen)

Replace shell pipes (`cmd1 | cmd2`) with Popen chaining:

```python
p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
p2 = subprocess.Popen(cmd2, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
p1.stdout.close()
stdout, stderr = p2.communicate()
```

## Pattern: stdout redirect

Replace shell redirects (`cmd > file`) with:

```python
with open(outfile, "wb") as out:
    subprocess.run(cmd, stdout=out, stderr=log_handle, check=True)
```

## Pattern: bash loops → Python loops

Replace bash `while IFS=$'\t' read -r ...` loops with Python:

```python
genes = _read_manifest(manifest_path)  # list[dict]
for gene in genes:
    fq2 = gene["fastq2"]
    read_files = [gene["fastq1"]]
    if os.path.getsize(fq2) > 0:  # replaces bash [ -s "$fq2" ]
        read_files.append(fq2)
    subprocess.run([STAR, "--readFilesIn", *read_files, ...], check=True)
```

This eliminates all shell-variable quoting issues because variables are native Python strings.

## Legacy pattern: shell-script generation in bin/ scripts (deprecated)

The previous approach of generating `.sh` files inside `bin/` scripts with `shlex.join` and executing via `subprocess.run(["bash", script])` is deprecated for the `bin/` layer. It was used when `run:` blocks contained bash loops with shell variables. Now that loops are in Python, direct `subprocess.run` is always preferred in `bin/` scripts.

NOTE: This does NOT apply to the `.smk` layer. The `.smk` `run:` block MUST use the shell-script pattern (write `.sh`, `shell(f"bash {script} >> {log} 2>&1")`) per `modules/modules.md`. The deprecation only applies to `bin/` helper scripts that were generating intermediate `.sh` files for their own internal commands.

If a legacy `bin/` script still uses the shell-script pattern internally (writing lines to a `.sh` file and calling `subprocess.run(["bash", script])`), it should be migrated to the direct-execution pattern.

## Parameter passing: explicit typed CLI args, never JSON blobs

When the `run:` block calls a standalone helper script, every tunable tool parameter must be a dedicated CLI argument with a type and a default. Do not pass structured parameters as `--pass-params '{"key": "value"}'` JSON strings — the user considers this a design failure. JSON blobs are undiscoverable in `--help`, cannot be type-checked, and hide the actual parameter values from the command line.

## Verification

Ad-hoc verification script should check:

### .smk layer (modules.md compliance)
1. `open(log_path, "w").close()` present
2. `setup_logger(...)` called
3. `current_time` timestamp used for script filename
4. `cmd = [...]` list construction
5. `with open(script, "w"): f.write(" ".join(cmd) + "\n")` - NOT `shlex.join`
6. `shell(f"bash {script} >> {log_path} 2>&1")` - NOT `shell(shlex.join(cmd))`
7. `try/except` with `raise e`
8. No `import shlex` in `.smk`
9. No `shlex.join` anywhere in `.smk`

### bin/ script layer (direct subprocess)
1. Helper functions return lists (not strings).
2. Multi-value options split into correct token counts (PE vs SE).
3. `subprocess.run` is used directly - no `["bash", script]` in source.
4. For pipelines: `Popen` chaining produces correct output.
5. For redirects: output file contains expected content.
6. `--help` output shows all parameters as explicit typed args; no JSON blob remains.
7. `.cmd.log` file is written with `shlex.join` for every executed step.
8. No `build_script` function, no `["bash", script]` execution in source.

### Integration
1. Snakemake `--dry-run` reaches "Building DAG of jobs" with no SyntaxError/NameError/AttributeError.
