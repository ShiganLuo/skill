# deeptools_heatmap Module Patterns

## TE GTF gene_id Matching

TE names in config must match exact `gene_id` in the TE GTF. Colloquial names don't work:

| User writes | GTF gene_id | Match type |
|---|---|---|
| L1MdTf | L1MdTf_I, L1MdTf_II, L1MdTf_III | PREFIX (wrong) |
| LINE1 | NOT FOUND | (wrong) |
| GSAT_MM | GSAT_MM | EXACT (correct) |

**Always verify** gene_id names against the actual GTF before adding to config:
```python
python3 -c "
import re
gtf = '/path/to/rmsk_TE.gtf'
te = 'L1MdTf'
exact = prefix = 0
with open(gtf) as f:
    for line in f:
        m = re.search(r'gene_id \"([^\"]+)\"', line)
        if m:
            if m.group(1) == te: exact += 1
            elif m.group(1).startswith(te): prefix += 1
print(f'{te}: exact={exact}, prefix={prefix}')
"
```

## Mode Selection for Heatmap Types

| regions config | computeMatrix mode | referencePoint | Why |
|---|---|---|---|
| `"tss"` | reference-point | TSS | TSS ± flank |
| `"peaks"` | reference-point | center | peaks have no directionality |
| `genes` (gene GTF) | scale-regions | TSS | shows TSS and TES labels on x-axis |
| `genes` (TE GTF) | scale-regions | TSS | each locus has independent strand |

**Pitfall: `.get()` returns config value, not default.** If config has `"mode": "reference-point"`, then `cm_params.get("mode", "scale-regions")` returns `"reference-point"`. For genes mode, hardcode the override:
```python
# ❌ Wrong: config value overrides the default
mode = cm_params.get("mode", "scale-regions")  # returns "reference-point" from config!

# ✅ Correct: hardcode for genes mode
mode, ref_point = "scale-regions", "TSS"
```

## `--merge` in generate_genes_bed()

`--merge` combines all exons of a gene into one BED interval (min_start, max_end), including introns. This is correct for gene GTF (one row per gene body).

For TE GTF, `--merge` is WRONG — different loci are on different chromosomes/strands. Each locus should be an independent BED row.

**Decision logic:**
- gene GTF + merge → gene body (includes introns) → one row per gene
- TE GTF + no merge → each locus independent → correct strand per row

## plotHeatmap Parameter Names (verify with `--help`)

**Always run `plotHeatmap --help` in the SIF before writing parameters.** Gotchas:
- `--samplesLabel` for track labels (NOT `--labels` or `--labelName`)
- `--whatToShow` valid choices: `"plot, heatmap and colorbar"`, `"plot and heatmap"`, `"heatmap only"`, `"heatmap and colorbar"` (NOT `"heatmap, colorbar, metagene"`)
- `--dpi` for resolution (default 72, use 300 for publication)
- `--startLabel` / `--endLabel` for scale-regions mode labels
- `--refPointLabel` for reference-point mode label

## bigwigCompare for IP/Input Ratio

Use `bigwigCompare` to generate ratio bigwig before heatmap. Should be a **separate reusable rule** (not inline in script) because multiple heatmap rules can reuse the same ratio bigwig:

```bash
bigwigCompare -b1 IP.bigwig -b2 Input.bigwig --operation ratio --pseudocount 1 -o ratio.bigwig -p 4
```

Pattern: `bigwig_ratio` rule → ratio bigwig → `heatmap`/`heatmap_gene` rules depend on it.

## DPI

Must pass `--dpi 300` to plotHeatmap. Default is 72 in deeptools (too low for publication).

## matrix.gz Naming for Parallel Jobs

When running multiple heatmap_gene jobs in parallel (one per TE name), temp matrix.gz files must have unique names:
```python
matrix_label = args.gene_names[0] if args.gene_names else args.region_mode or "regions"
matrix_path = args.keep_matrix or tempfile.mktemp(suffix=f"_{matrix_label}_matrix.gz")
```

## shlex.quote() in .sh Scripts

When writing commands to .sh scripts, MUST use `shlex.quote()` for arguments with spaces:
```python
# ✅ Correct
f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")

# ❌ Wrong: --title "Rpp14IP ORR1C1 vs Rpp14Input" gets split by shell
f.write(" ".join(cmd) + "\n")
```

## Shell Script Standard

All .sh scripts must start with:
```bash
#!/bin/bash
set -euo pipefail
```
Without `set -euo pipefail`, the "completed successfully" echo runs even on failure, misleading the user.

## computeMatrix.samples Filtering

node.py controls which samples generate heatmap outputs via `Params.computeMatrix.samples`:
```python
cm_heatmap_samples = datajson.get("Params", {}).get("computeMatrix", {}).get("samples", None) or ip_samples
```
Schema should include `samples` field with `items: {"type": "str"}` and `default: []`.

## Reuse _build_heatmap_cmd() with gene_names Override

`_build_heatmap_cmd()` must accept `gene_names` parameter. heatmap_gene passes only the wildcard's gene_name, NOT all genes from config:

```python
def _build_heatmap_cmd(wildcards, input, output, threads, title, gene_names=None):
    ...
    names = gene_names if gene_names is not None else _get_gene_names()
    for name in names:
        cmd += ["--gene-names", name]
```

heatmap_gene call:
```python
cmd = _build_heatmap_cmd(wildcards, input, output, threads, title, gene_names=[wildcards.gene_name])
```

**Pitfall:** Without this, heatmap_gene extracts ALL TE names from config (e.g., 31 TEs → 287,045 regions), then top_n selects from the combined pool. Every heatmap looks identical.

## bigwig_ratio Rule Architecture

bigwig_ratio is a **separate reusable rule** — ratio bigwig is NOT deleted after use:

```
bigwig_ratio rule → {sample}_IP_over_Input.bigwig (persistent)
heatmap rule ──────→ depends on ratio_bigwig
heatmap_gene rule ─→ depends on ratio_bigwig
```

After switching to ratio bigwig:
- Remove `--input-bigwig` from `_build_heatmap_cmd` (ratio already has the ratio)
- `run_heatmap.py` labels: use sample name from ratio bigwig filename, strip `_IP_over_Input`
- `get_ratio_bigwig()` function returns the ratio bigwig path
- PeakCalling.smk needs `use rule bigwig_ratio` and `use rule bigwig_ratio_result`

## PeakCalling_report Heatmap Integration

Add heatmap PNGs to report PPT:
- `--heatmap-dir` arg in generate_report.py
- `build_heatmap_slide()` — 2×3 grid per sample, up to 6 heatmaps per slide
- PeakCalling_report.smk: `heatmap_dir` config, expand heatmap PNGs as input deps, pass `--heatmap-dir`

## Snakemake Principle: Output Determines Flow

Added to modules.md: **输出决定流程走向，输入被动。**

- node.py registers output files → Snakemake back-chains to determine which rules to run
- Input functions prepare data, never control flow
- If deleting an input function's conditional branch changes behavior, you're using input to control flow — that's wrong

## Testing Rule

**铁律：先实际测试(run.sh) → 确认无误 → 再 git commit+push。绝不能先推再测。不能只 dry-run，必须实际运行。**
