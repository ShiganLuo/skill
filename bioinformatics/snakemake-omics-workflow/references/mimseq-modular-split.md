# Splitting mimseq into Snakemake sub-modules

Reference for splitting monolithic Python bioinformatics tools into independent Snakemake modules.
Derived from the mimseq → 6 sub-modules split (tRNAtools/align/clusters/mods/coverage/deseq).

## Architecture pattern

```
modules/mimseq/
├── bin/
│   ├── serialize.py          # pickle/JSON state transfer
│   ├── utils.py              # shared utilities
│   └── <module>/run.py       # wrapper per sub-module
├── <module>/<module>.smk     # Snakemake rules per sub-module
├── mimseq/                   # original library source (modified)
└── mimseq.smk                # master module (use rule imports)
```

Key design decisions:
- Pickle files for inter-module state transfer (serialize.py)
- `.done` touch files as Snakemake rule outputs for dependency tracking
- Each sub-module can be independently re-run after fixing

## Wrapper `run.py` pitfalls

### 1. Bare function calls without module prefix
```python
# WRONG — NameError: name 'generateModsTable' is not defined
import mimseq.mmQuant as mmQuant_module
generateModsTable(...)

# CORRECT
mmQuant_module.generateModsTable(...)
```
Every imported module uses `as X_module` alias; all calls must use `X_module.func()`.

### 2. Broken multi-module import lines
```python
# WRONG — SyntaxError
import mimseq.getCoverage as getCoverage_module plotCoverage

# CORRECT — two separate lines
import mimseq.getCoverage as getCoverage_module
import mimseq.mmQuant as mmQuant_module
```

### 3. Function signature mismatch
Always check original signatures before calling:
```bash
grep "^def plotCoverage" mimseq/getCoverage.py
# def plotCoverage(out_dir, mito_trnas, sorted_aa)  ← 3 args, not 2
```

### 4. State file name mismatches
If upstream saves `splitBool_new.pkl`, downstream must load `splitBool_new` (not `splitBool`).
Verify with: `ls state/*.pkl` and `grep "state\[" bin/<module>/run.py`

### 5. MIMSEQ_PARENT vs MIMSEQ_DIR
All wrappers use `MIMSEQ_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))` for sys.path.
Do NOT use `MIMSEQ_DIR` (points to wrong level).

## `.smk` rule pitfalls

### 6. Bare `python` instead of conda env path
```python
# WRONG
cmd = ["python", params.script, ...]

# CORRECT
cmd = ["/data/pub/zhousha/env/.../bin/python", params.script, ...]
```

### 7. Missing `export PATH` in generated bash scripts
```python
# WRONG — samtools/bedtools/usearch won't be found
f.write("#!/bin/bash\n")
f.write(" ".join(cmd) + "\n")

# CORRECT
f.write("#!/bin/bash\n")
f.write("export PATH=/data/pub/zhousha/env/.../bin:$PATH\n")
f.write(" ".join(cmd) + "\n")
```

### 8. Missing trailing `/` on `--out` parameters
```python
# WRONG — mimseq functions expect trailing /
"--out", outdir,

# CORRECT
"--out", outdir + "/",
```

## Verification checklist
```bash
# All .smk files have PATH export
grep -c "export PATH" modules/mimseq/*/\*.smk

# All .smk use full python path
grep "python" modules/mimseq/*/\*.smk

# All wrapper calls use module prefix
grep "_module\." modules/mimseq/bin/*/run.py

# All --out params have trailing /
grep "outdir" modules/mimseq/*/\*.smk

# Function signatures match
grep "^def " mimseq/*.py
```

## Dependency chain (mimseq)
```
prepare_sample_data → tRNAtools → align → clusters → mods → coverage → deseq → result
```

## Tool version requirements
- usearch: MUST be v10 (v12 removed `-sortbysize`)
- gsnap: MUST be 2024+ (genome index format changed, removed `--md-lowercase-snp` and `--ignore-trim-in-filtering`)
- Python: conda env at `/data/pub/zhousha/env/mutation_0.1/eda061b3f191779ad16ff11ee6fe53b4_/bin/python`

## Cross-module global state

When a library uses module-level globals (e.g., `ssAlign.stkname`), each sub-module
that calls functions depending on those globals MUST set them explicitly:

```python
import mimseq.ssAlign as ssAlign_module
import glob

stk_files = glob.glob(os.path.join(out, "*_align.stk"))
if not stk_files:
    raise FileNotFoundError(f"No *_align.stk file found in {out}")
ssAlign_module.stkname = stk_files[0]
```

Globals do NOT persist across separate Python processes. Verify with:
```bash
grep -n "global\|stkname" mimseq/ssAlign.py
```

## Empty sequence guards in bioinformatics code

Functions like `clusterAnticodon()` return `[]` when the cluster name doesn't
match any record in the stk file. Guard all `min()`/`max()` calls:

```python
# WRONG — ValueError: min() arg is an empty sequence
if pos-1 == min(anticodon):

# CORRECT
if anticodon and pos-1 == min(anticodon):
```

Apply the same guard in `elif` branches:
```python
elif (condition and not (anticodon and pos-1 == min(anticodon))):
```

## Optional argparse params from config

When config values can be empty strings, conditionally add args to the command:
```python
# WRONG — argparse treats --misinc-thresh as value of --control-cond
cmd = ["--control-cond", params.control_cond, "--misinc-thresh", "0.1"]

# CORRECT
if params.control_cond:
    cmd += ["--control-cond", params.control_cond]
```

Also change `required=True` to `default=""` in the argparse definition.

## Temporary files deleted by downstream steps

Some library functions delete input files after processing (e.g., `getCoverage`
calls `os.remove()` on `_coverage.txt` files at line 89). If a later step fails,
these files are lost and the module must be re-run from scratch.

Detection: if a module fails with `FileNotFoundError` for files that should have
been created by an upstream step, check if the upstream step's output files exist.
If not, the downstream step already deleted them.

Fix: delete the downstream `.done` file and re-run both modules.

## Two-pass modules (remap pattern)

Original mimseq runs `generateModsTable` twice:
1. `remap=True` — discovers new modifications, generates `_coverage.txt`
2. `remap=False` — generates final output (CCA, mod tables, counts)

With only `remap=True`:
- `_coverage.txt` files ARE generated (used by getCoverage)
- CCA analysis data (`CCAanalysis/AlignedDinucProportions.csv`) is NOT generated
- `mods/` directory remains empty

Fix: make CCA and modPlot calls conditional on input file existence:
```python
cca_file = os.path.join(out, "CCAanalysis", "AlignedDinucProportions.csv")
if os.path.exists(cca_file):
    mmQuant_module.plotCCA(out, double_cca)
else:
    log.warning(f"CCA data not found, skipping CCA plot")
```

## Empty control_cond fallback

When `control_cond` is empty, `getCoverage.py` filters for `condition == ""`
which returns empty DataFrame → `IndexError`. Add fallback:

```python
if control_cond:
    cov_mean_aa_controlcond = cov_mean_aa[cov_mean_aa.condition == control_cond]
else:
    first_cond = cov_mean_aa['condition'].unique()[0]
    cov_mean_aa_controlcond = cov_mean_aa[cov_mean_aa.condition == first_cond]
```

## Orphan files from early runs

If the outdir path changes between runs (e.g., adding `mimseq/` suffix), early-run
files remain at the old location. Without trailing `/`, path concatenation produces:
```
out_dir = "tRNAseq/mimseq"  + "Mmus_tRNAgenome" → "tRNAseq/mimseqMmus_tRNAgenome"  # WRONG
out_dir = "tRNAseq/mimseq/" + "Mmus_tRNAgenome" → "tRNAseq/mimseq/Mmus_tRNAgenome"  # correct
```

Detection: check for empty directories or files outside the expected output path.
```bash
ls -la /path/to/tRNAseq/ | grep -v "^mimseq$\|^fastq$\|^log$\|^raw\."
```

## Post-hoc per-sample file organization

mimseq writes all per-sample files flat in one directory. To organize into
`samples/{sample}/` subdirectories (purely cosmetic, does not affect pipeline):

```bash
cd /path/to/mimseq
mkdir -p samples
for sample in $(ls *.single.fq.gz.* 2>/dev/null | sed 's/\.single\.fq\.gz.*//' | sort -u); do
    mkdir -p samples/$sample
    mv ${sample}.single.fq.gz.* samples/$sample/
done
```

NOTE: This is post-processing only. Pipeline code still writes flat. Re-running
recreates the flat structure. To make permanent, modify tRNAmap.py and mmQuant.py
path concatenation logic.
