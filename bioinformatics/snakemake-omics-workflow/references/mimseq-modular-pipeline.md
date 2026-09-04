# mimseq Modular Pipeline — Pitfalls & Code Patterns

## Architecture

mimseq was split from a monolith into 6 independent Snakemake modules:
```
tRNAtools → align → clusters → mods → coverage → deseq
```

State passes between modules via pickle files in `state/` directory.
Each module has: `<name>/<name>.smk` (rules) + `bin/<name>/run.py` (wrapper).

## Critical Pitfalls

### P1: ssAlign.stkname global is empty in new processes

`ssAlign.py` line 11: `stkname = ''` — set by `aligntRNA()` during tRNAtools.
In modular pipeline, each module runs in a separate process → stkname is empty.

Functions affected: `tRNAclassifier()`, `structureParser()`, `clusterAnticodon()`

**Fix**: In wrappers that call ssAlign-dependent functions (clusters, mods):
```python
import mimseq.ssAlign as ssAlign_module
import glob
stk_files = glob.glob(os.path.join(out, "*_align.stk"))
ssAlign_module.stkname = stk_files[0]
```

### P2: mmQuant.unknownMods crashes on empty anticodon

`clusterAnticodon()` returns `[]` when cluster name doesn't match stk records.
Line 90/93: `min(anticodon)` → `ValueError: min() arg is an empty sequence`.

**Fix**: Add `anticodon and` guard:
```python
if (... and anticodon and pos-1 == min(anticodon)):       # line 90
elif (... and not (anticodon and pos-1 == min(anticodon))):  # line 93
```

### P3: _coverage.txt lifecycle — created by mods, DELETED by coverage

- Created: `bamMods_mp()` in mmQuant.py line 341 (during mods)
- Read+Deleted: `getCoverage()` in getCoverage.py line 70+89 (during coverage)

If coverage fails mid-way, some files are deleted. Re-running coverage fails.
**Fix**: Delete `mods.done` and re-run both mods + coverage.

### P4: remap=True only does discovery, not final output

`generateModsTable(remap=True)` discovers new mods but does NOT generate:
- `mods/` directory (predictedMods.csv, mod tables)
- `CCAanalysis/` outputs
- `counts/` outputs

`_coverage.txt` IS generated regardless of remap flag.

Full mimseq needs TWO passes: remap=True → re-alignment → remap=False.
Our modular approach only does remap=True → downstream modules need graceful fallbacks.

### P5: control_cond empty string breaks multiple things

- argparse: `--control-cond ""` causes next flag consumed as value
- getCoverage.py: filtering by `condition == ""` returns empty DataFrame
- deseq.R: `if (mito_trnas == "")` fails with NA

**Fix**: Conditionally add `--control-cond` only when non-empty. Use `default=""` not `required=True`.
In getCoverage.py, fallback to first available condition.

### P6: tRNAtools modsToSNPIndex is a function, not a submodule

```python
tRNAtools_module.modsToSNPIndex(...)           # ✅
tRNAtools_module.modsToSNPIndex_module.xxx()   # ❌ AttributeError
```

## Code Patterns

### Per-sample output directory

All per-sample files (BAM, _coverage.txt, _predictedModstemp.csv) go to `samples/{sample}/`.

Changes in 3 files:
1. **tRNAmap.py**: `mapReads(sample_dir=None)` — `mainAlign()` creates `{out_dir}/samples/{sample}/`
2. **mmQuant.py**: `_coverage.txt` → `os.path.dirname(inputs) + "/" + basename`
3. **getCoverage.py**: read/delete from `os.path.dirname(bam)`

`_predictedModstemp.csv` uses `inputs + "_predictedModstemp.csv"` (relative to BAM) — no change needed.

### .smk file PATH export pattern

Every sub-module .smk must add to generated bash script:
```python
f.write("#!/bin/bash\n")
f.write("export PATH=/path/to/conda/env/bin:$PATH\n")
f.write(" ".join(cmd) + "\n")
```

### Full python path in .smk

```python
"/path/to/conda/env/bin/python", params.script,  # ✅
"python", params.script,                          # ❌ multiprocessing workers fail
```

## Coverage Output Format

### coverage_byaa.txt
TSV: `aa, bin, condition, bam, pos, cov, cov_norm`
- `aa`: amino acid family (Gln, Arg, mitoSer, Ala, Leu, mitoPro, etc.)
- `condition`: sample condition (GV, MII, 4C, 8C, E2C, L2C, Morula, Blastocyst, PN5)
- `cov_norm`: normalized coverage (used for heatmaps, PPTs, Excel exports)
- Contains ALL samples (embryo + control like Liver-1ng, MEF-100cell)

Per-condition mean for heatmap: `df.groupby(['aa','condition'])['cov_norm'].mean().unstack('condition')`

Typical AA ordering for presentation: sort by mean cov_norm descending, pick top 12 with biological significance (mix of canonical + mito tRNAs).

### coverage_bygene.txt
Same structure, per-tRNA-transcript instead of per-amino-acid.

## User Preference: File Export

When user says "导出为excel", do a **direct format conversion** (TSV→XLSX) without aggregation, pivoting, or filtering. If they want a transformed view, they'll specify explicitly.

## Testing Strategy

1. Back up original results: `cp -r mimseq mimseq_bak`
2. Create test output directory with symlinked fastq
3. Update raw.json: `outdir`, `outfiles`, `logdir` to test dir
4. Run full pipeline in test dir
5. Verify `samples/` structure and all `.done` files
