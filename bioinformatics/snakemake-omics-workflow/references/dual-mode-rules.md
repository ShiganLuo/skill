# Dual-mode rules: resource-based vs download-based

When a tool can build an index from local files OR download from remote URLs,
design the smk rule to branch on config presence of resource paths.

## Pattern

```python
# Module-level: compute output path (output: cannot use functions)
_genome = config.get("Params", {}).get("module", {}).get("genome", "hg38")
_mode = config.get("Params", {}).get("module", {}).get("mode", "exclusive")
_index_path = f"{outdir}/index/{_genome}.{_mode}.idx"

rule build_index:
    output:
        index = _index_path
    params:
        gene_gtf = config.get("Params", {}).get("module", {}).get("gene_gtf"),
        te_bed   = config.get("Params", {}).get("module", {}).get("te_bed"),
        genome   = _genome,
        mode     = _mode,
    run:
        if params.gene_gtf and params.te_bed:
            # Resource-based: local files → binary with resource flags
            cmd = [binary, "-gene", params.gene_gtf, "-te", params.te_bed, "-g", "other", ...]
        else:
            # Download-based: binary downloads from hardcoded URLs per genome
            cmd = [binary, "-g", params.genome, ...]
```

## Key decisions

1. **No wrapper script for simple CLI calls**: If the binary's CLI is
   straightforward (just a few flags), inline the call directly in the
   smk `run:` block. Only create a wrapper script when the logic is
   non-trivial (file validation, format conversion, multi-step).
   User explicitly corrected: "既然是简单调用,不需要单独脚本,直接在规则里面用就行".

2. **Snakemake output cannot be a function**. Compute the output path as a
   module-level variable and reference it directly. Functions are only valid
   in `input:` (with wildcards), not in `output:`.

3. **Config fields**: add `gene_gtf: null` and `te_bed: null` to the module's
   JSON defaults. `null` means "use download mode". Non-null paths trigger
   resource mode.

4. **shlex.quote**: use for user-provided resource paths (they may contain
   spaces/special chars). Not needed for hardcoded genome names.

5. **Mode param**: expose the tool's counting mode (e.g. `exclusive`/`inclusive`)
   in config so users don't need to edit the rule.

6. **Output as single file**: when the tool produces a single index file
   (not a directory), use the exact file path rather than `directory()`.
   Better for Snakemake dependency tracking.

## Example: scTE module

- `scTE_build` CLI: `-gene <gtf> -te <bed> -g other` for local, `-g hg38` for download
- Inline in smk rule run block (no wrapper script)
- Config: `Params.scTE.gene_gtf` / `Params.scTE.te_bed` (null = download)
- Rule branches on `params.gene_gtf and params.te_bed`

## Pitfalls

- **scTE_build `-te` flag only accepts uncompressed files** (uses `open()`,
  not `gzip.open()`). The `-gene` flag accepts both `.gz` and plain text.
  Always decompress TE BED before passing to `-te`.
- **TE BED format**: 4 columns `chr start end subfamily_name`. Convert from
  rmsk TE GTF with: `awk '{match($0, /gene_id "([^"]+)"/, m); print $1, $4-1, $5, m[1]}'`
- **scTE index is a single `.idx` file**, not a directory. Output path should
  be the file itself (e.g. `{outdir}/index/{genome}.{mode}.idx`).
- **Snakemake output: cannot use a function**. Use a module-level variable.
- **`from time import time` shadows the module**. When `time.strftime()` or
  `time.localtime()` is needed, use `import time` (not `from time import time`).
  The function import shadows the module, causing `AttributeError: 'builtin_function_or_method'
  object has no attribute 'strftime'`.
