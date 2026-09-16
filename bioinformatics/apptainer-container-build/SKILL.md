---
name: apptainer-container-build
description: Build Apptainer SIF containers from conda YAML via EnvUtil — PyPI detection, post hooks, verification, pitfalls.
tags: [apptainer, conda, container, bioinformatics, omics]
triggers:
  - apptainer build
  - SIF container
  - EnvUtil.py
  - .def file generation
  - conda env create in container
---

# Apptainer Container Build via EnvUtil

## EnvUtil Workflow

`EnvUtil.py` at `workflow/Omics/src/common/util/EnvUtil.py` generates `.def` files from conda YAML and builds SIF images.

```bash
# Generate .def only
python EnvUtil.py apptainer gen -y <yaml>

# Full pipeline: YAML -> .def -> SIF
python EnvUtil.py apptainer all -y <yaml> -o <output_dir> [--force]
```

## PyPI-Only Detection

When a conda YAML has **only pip dependencies** (plus python/pip meta-packages), EnvUtil auto-generates a `python:3.11-slim` + `uv pip install` template instead of conda.

Detection logic in `is_pypi_only()`:
- **If conda channels are specified** (conda-forge, bioconda, etc.) → **always use conda** (not pypi-only)
- Filters out `python*` and `pip*` from conda dependencies
- If no remaining conda deps → pypi-only if there are pip deps
- If remaining conda deps exist → not pypi-only

**Pitfall**: Old logic checked if all conda deps were available on PyPI via `_all_on_pypi()`. This was too aggressive — packages like scanpy, anndata exist on PyPI but should be installed via conda for proper C extension handling. Fixed: channels presence is now the primary determinant. If channels are specified, use conda regardless of PyPI availability.

**Conda→pip version conversion**: When conda deps are promoted to pip packages, `=` (exact version) is converted to `==`. Other specifiers (`>=`, `<=`, `>`, `<`, `~=`) are unchanged.

**Pitfall**: `generate_def_file()` only used `pip_dependencies` (the `pip:` subsection) for the uv install list. If `is_pypi_only()` returns True because conda deps are on PyPI (but there's no `pip:` section), the install list was empty. Fixed: when `pypi_only` and no `pip_packages`, conda deps (excluding python/pip) are used as pip packages with `=` → `==` conversion.

**Pitfall**: scTE.yaml had `python>=3.6` + `pip` + `pip: scte-quant`. This was detected as PyPI-only, but `scte-quant` needs `samtools` and `zstd` (system/conda packages). Always check runtime dependencies, not just the YAML.

**Pitfall**: Regex word boundary in `is_pypi_only()`. The pattern `r"^(python|pip)\\\\b"` (four backslashes) becomes `^(python|pip)\\b` in the raw string — literal backslash + b, NOT a word boundary. This caused `python=3.11` and `pip` to NOT be filtered out, making all YAMLs with conda channels appear as PyPI-only. Fix: use `r"^(python|pip)\b"` (two backslashes = word boundary `\b` in raw string).

## Post-Install Hooks

For module-specific patches (e.g., scTE mitochondrial fix), create `<env_name>.post.sh` next to the YAML. EnvUtil auto-reads it and injects into `%post`.

```bash
# workflow/Omics/modules/scTE/scTE.post.sh
    # Fix scTE bug: M<->MT mitochondrial naming mismatch
    SCTE_BASE=$(find /opt/conda/envs/scTE -path "*/site-packages/scTE/base.py" | head -1) && \
        python3 -c "..."
```

**Pitfall**: `find ... -path "*/scTE/*"` matches too broadly (e.g., `email/mime/base.py`). Use precise path: `*/site-packages/scTE/base.py`.

## Build Verification

`apptainer build --fakeroot` may return 0 even when `%post` fails. EnvUtil now does two post-build checks:

1. **SIF size**: < 350 MB → RuntimeError (base image is ~300 MB)
2. **conda env check**: `apptainer exec <sif> conda env list` → verify env name exists

## Runtime Verification

After build, validate the container actually works by running Python inside it. Always `cd /tmp` first to avoid CWD contamination.

```bash
# 1. Check core package imports
cd /tmp && apptainer exec <sif> python3 -c "
import scanpy as sc; print(f'scanpy: {sc.__version__}')
import anndata as ad; print(f'anndata: {ad.__version__}')
"

# 2. Run a minimal workflow (filter→normalize→PCA→neighbors→UMAP→leiden)
cd /tmp && apptainer exec <sif> python3 -c "
import scanpy as sc, numpy as np
from scipy.sparse import csr_matrix
adata = sc.AnnData(csr_matrix(np.random.poisson(1, (100, 200))))
sc.pp.filter_cells(adata, min_genes=5)
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=50)
sc.pp.pca(adata, n_comps=20)
sc.pp.neighbors(adata, n_neighbors=15)
sc.tl.umap(adata, min_dist=0.1)
sc.tl.leiden(adata, resolution=0.8)
print('Workflow PASSED')
"
```

**Pitfall**: PyPI-only containers (uv template) have no `conda` command. Use `python3 -c "import pkg"` instead of `conda env list` to verify those.

See `references/scrna-package-mapping.md` for R→Python package name translations when adding scRNA-seq packages to conda YAML.
See `references/r-script-pdf-output.md` for adding `--format` flag to R scripts with ggsave or explicit device calls.
See `references/snakefile-configurable-paths.md` for making hardcoded BAM paths configurable in Snakemake modules.

## Cell Ranger GTF Biotype Compatibility

Cell Ranger mkref filters GTF by biotype using `gene_type`/`transcript_type` (GENCODE format). Ensembl GTFs use `gene_biotype`/`transcript_biotype` instead, causing 0 genes to pass the filter. See `references/cellranger-gtf-biotype.md` for the fix.

## Runtime Execution Pitfalls

**`--no-home` prevents host environment pollution** — By default, Apptainer bind-mounts the host's `$HOME` into the container. This means the host's R library (`~/R/library`), Python user packages (`~/.local/lib`), conda configs (`~/.conda`), and other per-user state leak into the container. For R containers, this causes `BiocGenerics`/`MatrixGenerics` version conflicts where packages exist in the container but `requireNamespace()` returns FALSE because the host's stale library is searched first.

**Symptom**: `requireNamespace("DESeq2")` fails with `object 'colMeans' is not exported by 'namespace:MatrixGenerics'` even though DESeq2 IS installed in the container. Check `Rscript -e 'cat(.libPaths(), sep="\n")'` — if the host's R library path appears before the container's, that's the cause.

**Rule**: Always use `--no-home` when running Apptainer containers for bioinformatics workflows:
```bash
apptainer exec --no-home \
  -B /home/luosg/Data:/home/luosg/Data \
  -B /home/luosg/Database:/home/luosg/Database \
  /path/to/container.sif \
  bash /path/to/script.sh
```

**Do NOT rebuild the container** when seeing "missing package" errors — always check `.libPaths()` and host pollution first. If the container has been used successfully before, the issue is almost certainly host environment leakage, not a broken container.

## Key Pitfalls

1. **SIF is read-only at runtime** — cannot patch files inside a built container. All patches must be baked into `.def` before build.

2. **Classic solver is slow** — conda-forge + bioconda dual-channel with classic solver can take 10+ minutes. `libmamba` solver requires `conda install -n base -c conda-forge -y conda-libmamba-solver` which may fail in container build context. Stick with classic for reliability.

3. **`--force` flag** — Added to EnvUtil CLI. Default is `False`. When set, implies `--no-skip-existing` (rebuilds even if SIF exists).

6. **EnvUtil overwrites .def** — Running `apptainer gen` regenerates .def from template, losing manual edits. Use `.post.sh` hooks for custom patches.

7. **Don't fix what isn't broken** — When the user asks to change a conda YAML (e.g., pin a package version), only change the YAML and rebuild. Do NOT modify EnvUtil.py templates to "fix" build issues that weren't reported. If the build fails after a YAML change, the problem is likely the new dependency, not the build template. Revert EnvUtil changes and investigate the actual failure.

5. **`%post` uses `/bin/sh` by default** — Apptainer runs `%post` with `/bin/sh`, which does NOT support `set -euo pipefail`. The build fails with `/.post.script: 1: set: Illegal option -o pipefail` or `/bin/sh: 0: Illegal option --`.

   **Fixes** (in order of preference):
   - `%post --shell /bin/bash` directive (Apptainer ≥1.6 only; 1.5.3 does NOT support this)
   - **`/bin/bash << 'ENDOFSCRIPT'`** heredoc pattern — **recommended for all Apptainer versions**. Wraps entire script in bash, `set -euo pipefail` works reliably.
   - `#!/bin/bash` as the very first line inside `%post` — only works when fakeroot maps `/bin/sh` to bash (unreliable).
   - `exec /bin/bash` — **DOES NOT WORK** in Apptainer 1.5.3 `%post`. Causes SIF to be tiny (~181 MB) because process replacement fails silently. Avoid.
   - Replace `set -euo pipefail` with `set -e` — **NOT recommended** because errors won't be caught and builds may silently fail.

   **Recommended `.def` format** (heredoc pattern):
   ```
   %post
       /bin/bash << 'ENDOFSCRIPT'
       set -euo pipefail
       export PATH="/opt/conda/bin:$PATH"
       conda env create -f /opt/conda/env.yaml && \
           conda clean -afy
       ENDOFSCRIPT
   ```

   **Pitfall**: Removing `set -euo pipefail` to "fix" the build error is WRONG — it masks real failures. The conda install may fail silently, producing a broken container that passes the SIF size check. Always use the heredoc pattern to enable proper error handling.

   **Pitfall**: `exec /bin/bash` appears to work (no error) but causes silent failure — the SIF is built but tiny (~181 MB vs expected ~300+ MB). The `exec` replaces the shell process but Apptainer doesn't execute the remaining commands. Use heredoc instead.

## Multi-Backend Support (--solver)

EnvUtil supports multiple build backends via `--solver` parameter:

```bash
# Auto-detect (default): uv for PyPI-only, micromamba otherwise
python EnvUtil.py apptainer all -y <yaml> -o <dir>

# Explicit backend
python EnvUtil.py apptainer all -y <yaml> -o <dir> --solver micromamba
python EnvUtil.py apptainer all -y <yaml> -o <dir> --solver conda
```

**Backend choices:**
- `auto` (default): PyPI-only → `uv`, otherwise → `micromamba`
- `micromamba`: Fastest, lightest (~30 MB base image)
- `mamba`: Fast conda replacement
- `conda`: Slowest, most compatible
- `uv`: PyPI-only packages (auto-selected when `is_pypi_only()` returns True)

**BACKENDS dictionary** in EnvUtil.py:
```python
BACKENDS = {
    "micromamba": {
        "apptainer_from": "docker.1ms.run/mambaorg/micromamba:latest",
        "docker_from": "docker.1ms.run/mambaorg/micromamba:latest",
        "verify_cmd": ["micromamba", "env", "list"],
    },
    "mamba": {
        "apptainer_from": "docker.1ms.run/condaforge/miniforge3:latest",
        "verify_cmd": ["mamba", "env", "list"],
    },
    "conda": {
        "apptainer_from": "docker.1ms.run/condaforge/miniforge3:latest",
        "verify_cmd": ["conda", "env", "list"],
    },
    "uv": {
        "apptainer_from": "docker.1ms.run/python:3.11-slim",
        "verify_cmd": ["python3", "-c", "import sys; print(sys.version)"],
    },
}
```

**Backend-specific verification**: The def file includes `# Backend: <name>` comment. Verification reads this to choose the correct command (`micromamba env list` vs `conda env list`).

**micromamba template**:
```
%post
    /bin/bash << 'ENDOFSCRIPT'
    set -euo pipefail
    export MAMBA_ROOT_PREFIX="/opt/conda"
    micromamba env create -f /opt/conda/env.yaml && \
        micromamba clean -afy
    ENDOFSCRIPT
```

**Pitfall**: micromamba uses `MAMBA_ROOT_PREFIX` instead of `PATH` for conda detection. Don't set `PATH` to conda bin — it's not needed and may cause issues.

## Installed vs Source Code Mismatch (CRITICAL)

The installed package inside a container may differ from the source repo:
- Different variable names (`chrom` vs `chr`)
- Different spacing (`[str(k)` vs `[ str(k)`)
- Different line numbers
- Different function signatures

**Rule**: Always check the ACTUAL installed file inside the container before writing patches:
```bash
apptainer exec <sif> bash -c 'grep -n "target_pattern" /opt/conda/envs/scTE/bin/scTE_build'
```
Don't assume the source repo matches what's installed. Patches that work on source code but fail on installed code produce silent failures — the build succeeds but the fix isn't applied.

**Pattern**: When a post.sh patch fails silently, verify by grepping the container:
```bash
apptainer exec <sif> bash -c 'grep -c "expected_patch_text" /path/to/installed/file'
```

## Comparing Container Code with PyPI Original

When debugging whether post.sh patches caused unexpected behavior, download the original PyPI package and diff against the container's installed version:

```bash
# Download original package
pip download <package>==<version> --no-deps -d /tmp/fresh_pkg
# Extract
unzip /tmp/fresh_pkg/*.whl -d /tmp/fresh_pkg_extracted
# Get container's installed version
apptainer exec <sif> cat <path/to/installed/file> > /tmp/container_file.py
# Diff
diff /tmp/fresh_pkg_extracted/<module>/file.py /tmp/container_file.py
```

This reveals exactly what the post.sh patches changed vs the original. If the diff shows only unrelated changes (e.g., M/MT naming), the patches didn't affect the behavior in question.

**Pitfall**: Don't compare with local source code in the workflow directory — it may be a separately modified version, not the source for the container. Always compare with the actual PyPI package. When the user says "the code was modified by post.sh", verify by downloading the ORIGINAL PyPI package and diffing against the container's installed code. Don't assume the local workflow source is the baseline.

## scTE Quantification Flow (for debugging cell count issues)

The scTE multi-thread quantification pipeline:

1. **Bam2bed**: `samtools view | awk (extract CR/CB + UR/UB) | sed (strip prefixes) | sed (strip chr) | awk '!x[$4$5]++' (dedup by barcode+UMI) | compress`
2. **split_chr** (per chromosome): `grep ^<chr> | count per barcode → .count.gz`
3. **filter_crs**: Sum counts across all chromosomes per barcode, filter ≥ `2 * min_genes` (default 400)
4. **align** (per chromosome): Match reads to gene/TE annotations using bucket index
5. **count_expression**: Filter barcodes with ≥ `min_genes` (default 200) unique annotations, take top `cellnumber` (default 10000)

**Key insight**: M/MT patches only affect `splitAllChrs` (single-thread path) and index building. They don't change the multi-thread quantification logic. If cell counts differ between versions, the cause is NOT the M/MT patches.

**Debugging low cell count**: Check `filter_crs` output: "Before filter N / After filter M". If M is very low, the issue is in the Bam2bed dedup or the barcode/UMI tag extraction. If M is reasonable but final count is low, check `count_expression` gene filtering.

**CRITICAL — samtools vs pysam fallback in Bam2bed**: scte-quant 1.6.1 has two Bam2bed paths:
- `_bam2bed_cmd` (samtools path): `samtools view | awk | sed | awk '!x[$4$5]++' | compress` — includes UMI dedup by barcode+UMI
- `_bam2bed_pysam` (pysam fallback): iterates reads with pysam, writes every read to BED — **NO dedup**

The pysam path writes ALL 120M reads to BED (no `awk '!x[$4$5]++'`), while the samtools path deduplicates to ~29M unique barcode+UMI pairs. This causes each barcode to have ~4x more counts in the pysam path, dramatically increasing the number of barcodes that pass the `filter_crs` threshold.

**Impact**: If the container has samtools but the test environment doesn't, results will differ massively (e.g., 110 cells vs 20K cells). Always ensure samtools is available when reproducing container results outside the container.

**Check which path was used**:
```bash
grep "samtools" <log_file>
# "samtools found" → samtools path (with dedup)
# "samtools not found — falling back to pysam" → pysam path (NO dedup)
```

## Container File Inspection

```bash
# List installed package files
apptainer exec <sif> find /opt/conda/envs/<env> -path "*/site-packages/<module>/*.py"

# Read a specific file
apptainer exec <sif> cat $(apptainer exec <sif> find /opt/conda/envs/<env> -path "*/site-packages/<module>/base.py" | head -1)

# Run Python inside container (avoid local source contamination)
cd /tmp && apptainer exec <sif> /opt/conda/envs/<env>/bin/python3 -c "import <module>; print(<module>.__file__)"

# Check what a module actually imports from (avoid CWD contamination)
cd /tmp && apptainer exec <sif> /opt/conda/envs/<env>/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/conda/envs/<env>/')
import <module>.base; print(<module>.base.__file__)
"
```

**Pitfall**: Apptainer bind-mounts CWD by default. If CWD contains a local copy of the same package, Python may import the local version instead of the container's installed version. Always `cd /tmp` (or another neutral directory) before running Python inside the container.

## Annotation Standardization

Macaque Ensembl GTF (Mmul_10) uses non-standard mitochondrial gene names:
- GTF: `ND1`, `COX1`, `ATP6` (no `MT-` prefix)
- Standard (human/mouse): `MT-ND1`, `MT-COX1`, `MT-ATP6`
- Downstream QC tools (Scanpy/Seurat) match `^MT-` → macaque MT genes missed

Created `workflow/Omics/src/annotation/standardize_annotations.py`:
- Normalizes chromosome names (strip `chr`, M/chrM → MT)
- Adds `MT-` prefix to gene_name on mitochondrial chromosomes (by chromosome, not gene list)
- Supports gzipped GTF/BED
- `--dry-run` for preview, `--scan` to find all annotation files
- Species-agnostic — no `--species` parameter needed

**Rule**: Before building scTE index, always standardize annotations first:
```bash
python3 workflow/Omics/src/annotation/standardize_annotations.py \
  --gtf <gene.gtf> --te <te.bed> --dry-run  # preview
python3 workflow/Omics/src/annotation/standardize_annotations.py \
  --gtf <gene.gtf> --te <te.bed>             # execute
```

## scRNA-seq QC Gene Categories

Standard downstream QC checks these gene categories:
1. **MT-** (mitochondrial): high % → cell death/damage
2. **RPS/RPL** (ribosomal): high % → cell stress/activation
3. **HB-** (hemoglobin): red blood cell contamination
4. **PPBP/PF4** (platelet): platelet contamination
5. **MALAT1**: lncRNA affecting clustering

Naming conventions vary by GTF source. Always verify after standardization.

## scTE-Specific Notes

Exact patch text patterns: see `references/scte-patch-patterns.md`

- scTE needs: samtools, zstd (conda), scte-quant (pip)
- M<->MT patch: bidirectional fix in `splitAllChrs()` for UCSC chrM vs Ensembl MT
- scTE_build has hardcoded `chr_list = [..., 'M']` — does NOT include 'MT'. Ensembl GTF uses 'MT', so MT genes are silently skipped during index building. **Fix**: post.sh patches chr_list to add 'MT', and adds M<->MT normalization in readGtf() and TE processing.
- scTE_build `readGtf()` skips exon lines without `gene_name` — Mt_tRNA/Mt_rRNA from RefSeq lack gene_name and are silently dropped. This is expected behavior.
- **post.sh patches vs stock scte-quant 1.6.1**: The M/MT fixes are already built into scte-quant 1.6.1 from PyPI. The post.sh patches are effectively no-ops — they look for old text patterns that don't exist in the current version. Verified by downloading the original PyPI wheel and diffing against the container's installed code. The ONLY difference between stock and container is the M/MT fix in `splitAllChrs`, which only affects the single-thread path and has no impact on multi-thread quantification results.
