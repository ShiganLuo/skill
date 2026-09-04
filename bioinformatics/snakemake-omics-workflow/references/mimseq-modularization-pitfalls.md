# mimseq modularization pitfalls

The mimseq tool was split into 6 independent Snakemake sub-modules (tRNAtools, align, clusters, mods, coverage, deseq). Key pitfalls when working with this modular architecture:

## Global state lost between modules
When a monolithic tool is split into separate Snakemake rules (each running in its own Python process), module-level globals are NOT shared. Example: `ssAlign.py` has a global `stkname = ''` that gets set during alignment. The mods module calls `tRNAclassifier()` → `structureParser()` which reads `stkname` — if not re-set, `FileNotFoundError: ''`. **Fix**: In each wrapper `run.py`, import the module and set the global explicitly:
```python
import mimseq.ssAlign as ssAlign_module
stk_files = glob.glob(os.path.join(out, "*_align.stk"))
ssAlign_module.stkname = stk_files[0]
```

## Function calls need module prefix
When importing `import mimseq.mmQuant as mmQuant_module`, bare `generateModsTable(...)` won't work — must use `mmQuant_module.generateModsTable(...)`. Common mistake when splitting monolithic scripts.

## anticodon empty sequence guard
In `mmQuant.py` `unknownMods()`, `clusterAnticodon()` can return `[]` for isodecoders not in the stk file. `min(anticodon)` then raises `ValueError: min() arg is an empty sequence`. **Fix**: Guard with `anticodon and pos-1 == min(anticodon)`.

## empty --control-cond breaks argparse
When `control_cond` is empty string, `"--control-cond", ""` in the generated bash script causes argparse to consume the next argument as its value. **Fix**: Only add `--control-cond` when non-empty in .smk, and make it `default=""` (not `required=True`) in run.py.

## Bash script PATH and python path
All sub-module .smk files must:
1. Use full conda python path: `/data/pub/zhousha/env/mutation_0.1/eda061b3f191779ad16ff11ee6fe53b4_/bin/python` (not bare `python`)
2. Add `export PATH=/data/pub/zhousha/env/mutation_0.1/eda061b3f191779ad16ff11ee6fe53b4_/bin:$PATH` after `#!/bin/bash`
3. Ensure `outdir` has trailing `/` in `--out` parameter

## Pickle state file naming
When modules save state with `_new` suffix (e.g. `splitBool_new.pkl`), downstream modules must load using the same key names. Verify pickle filenames match between writer and reader.

## Verify .stk file availability
The `*_align.stk` file is produced by the align module and consumed by clusters/mods/coverage. If a module can't find it, check:
- File exists in output directory
- Module imports `ssAlign` and sets `ssAlign_module.stkname`
- Glob pattern matches the actual filename

## _coverage.txt lifecycle — mods generates, getCoverage deletes
In `mmQuant.py` `bamMods_mp()`, `_coverage.txt` files are written at line 341 (unconditional, regardless of `remap` flag). But `getCoverage.py` line 89 **deletes** each file after reading (`os.remove(...)`). If the coverage module fails mid-processing, all previously-read `_coverage.txt` files are gone. Re-running coverage without re-running mods causes `FileNotFoundError` on the remaining files.
**Fix**: Delete `mods.done` and re-run mods to regenerate `_coverage.txt` files before retrying coverage. Alternatively, check if `coverage_byaa.txt` already exists and skip the read+delete loop.

## getCoverage empty control_cond fallback
`getCoverage()` uses `control_cond` to select a condition for 5'/3' coverage ratio calculation (line 118). When `control_cond` is empty, `cov_mean_aa[cov_mean_aa.condition == '']` returns empty DataFrame → `IndexError` at line 119. **Fix**: Add fallback to use first available condition:
```python
if control_cond:
    cov_mean_aa_controlcond = cov_mean_aa[cov_mean_aa.condition == control_cond]
else:
    first_cond = cov_mean_aa['condition'].unique()[0]
    cov_mean_aa_controlcond = cov_mean_aa[cov_mean_aa.condition == first_cond]
```

## Two-pass generateModsTable (remap flow)
Original mimseq calls `generateModsTable` twice:
1. `remap=True` — discovers new modifications, returns `new_mods`/`new_Inosines`
2. After `newModsParser` + re-alignment, `remap=False` — generates final output tables (modTable, counts, CCA, `_coverage.txt` reads+deletes)
In the modular approach, the first pass still writes `_coverage.txt` files (unconditional at line 341). The second pass reads and deletes them. For the modular pipeline, a single pass with `remap=True` suffices since `_coverage.txt` is always written.

## CCA and modPlot.R graceful fallback with remap=True
When mods runs with `remap=True` only (no second pass), these outputs are NOT generated:
- `CCAanalysis/AlignedDinucProportions.csv` — only produced when `remap=False` (line 963)
- `mods/` directory content — mod table CSVs only produced when `remap=False` (line 351)

Coverage module calls `plotCCA(out, double_cca)` and `modPlot.R` which require these files.
**Fix**: Guard with existence checks in coverage/run.py:
```python
# CCA plot
cca_file = os.path.join(out, "CCAanalysis", "AlignedDinucProportions.csv")
if os.path.exists(cca_file):
    mmQuant_module.plotCCA(out, double_cca)
else:
    log.warning(f"CCA data not found, skipping CCA plot")

# Mod plots
mods_dir = os.path.join(out, "mods")
if os.path.isdir(mods_dir) and os.listdir(mods_dir):
    subprocess.check_call(["Rscript", "modPlot.R", ...])
else:
    log.warning("Mods directory empty, skipping modification plots")
```

## deseq.smk same --control-cond fix
`deseq.smk` and `deseq/run.py` need the same conditional `--control-cond` pattern as coverage:
- Only add `--control-cond` to cmd when `params.control_cond` is non-empty
- Make argparse `default=""` not `required=True`

## Backup before destructive testing
When modifying pipeline code that could overwrite existing results, **always backup first**:
```bash
cp -r output/mimseq output/mimseq_bak
```
Then test in a separate output directory to avoid clobbering the backup.
User explicitly corrected: "先备份结果，再修改代码，免得测试覆盖原有结果".

## Early-run leftover cleanup
Iterative debugging (fix→rerun cycles) leaves stale files from early buggy runs:
- Empty directories from failed early runs (e.g., `mimseqMmus_tRNAgenome/` with only `.` and `..`)
- Files with wrong prefixes from misconfigured outdir (e.g., `mimseqtRNAseq_*` instead of `tRNAseq_*`)
- Nested `tRNAseq/tRNAseq/` from double-pathed outdir
- Orphaned `.sh` scripts from Snakemake run blocks
```bash
rm mimseq/mimseq_*.sh  # orphaned scripts
ls output/tRNAseq/ | grep -v "^mimseq$\|^fastq$\|^log$\|^raw\."  # stray files
```