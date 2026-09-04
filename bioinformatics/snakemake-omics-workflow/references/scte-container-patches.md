# scTE container patches: M<->MT mitochondrial naming

scTE has a systematic bug where mitochondrial chromosome naming is not handled
bidirectionally. This affects three separate code paths and requires patches in
both the installed package and the build tool.

## Background

Different reference genomes use different mitochondrial chromosome names:
- UCSC style: `chrM` (or `M` after stripping `chr`)
- Ensembl style: `chrMT` (or `MT` after stripping `chr`)

scTE's code assumes one convention and silently drops reads/genes from the other.

## Affected files (3 patches needed)

### 1. `scTE/base.py` — `splitAllChrs()` (BAM processing)

**Bug:** Only maps `MT→M`, not `M→MT`. BAM reads on chrM when index has MT
are silently dropped.

**Location in installed file:** Search for `# Force chrMT -> chrM`

**Fix:** Replace the single-direction check with bidirectional mapping:
```python
# Old (single direction):
if chrom == 'MT':
    chrom = 'M'
else:
    continue

# New (bidirectional):
if chrom == 'M' and 'MT' in chromosome_list:
    chrom = 'MT'
elif chrom == 'MT' and 'M' in chromosome_list:
    chrom = 'M'
else:
    continue
```

### 2. `bin/scTE_build` — `chr_list` (index building)

**Bug:** `chr_list` hardcodes `'M'` but Ensembl GTFs use `'MT'`. All MT genes
are skipped during index building.

**Location in installed file:** Search for `chr_list = [str(k)`

**Fix:** Add `'MT'` to chr_list:
```python
# Old:
chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M']

# New:
chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M', 'MT']
```

### 3. `bin/scTE_build` — `readGtf()` and TE processing (index building)

**Bug:** Chromosome check `chrom.replace('chr','') not in chr_list` doesn't
handle M<->MT mismatch. GTF genes on MT are skipped when chr_list has M.

**Location in installed file:** Search for `chrom.replace('chr','') not in chr_list`

**Fix:** Add M<->MT normalization before the chr_list check:
```python
# Old:
if chrom.replace('chr','') not in chr_list:
    continue

# New:
_chr = chrom.replace('chr','')
if _chr not in chr_list:
    if _chr == 'M' and 'MT' in chr_list:
        pass
    elif _chr == 'MT' and 'M' in chr_list:
        pass
    else:
        continue
```

## Pitfall: match INSTALLED content, not source

The installed `scTE_build` binary may have DIFFERENT formatting than the source
code in the git repo. For example:
- Source: `chr_list = [ str(k) for k in  list(range(1,50))] + ['X','Y', 'M']`
  (extra spaces)
- Installed: `chr_list = [str(k) for k in list(range(1,50))] + ['X','Y','M']`
  (no extra spaces)

The `str.replace()` in the post.sh patch does exact string matching. If the
old text doesn't match character-for-character, the patch silently fails.

**Rule:** Always verify the exact content inside the container BEFORE writing
patches:
```bash
apptainer exec <sif> grep -n "target_pattern" /opt/conda/envs/<env>/bin/<tool>
```

## GTF mitochondrial gene naming (downstream impact)

Even after fixing scTE to include MT genes in the index, downstream QC analysis
has a separate problem:

- Standard Scanpy/Seurat QC: `adata.var_names.str.startswith('MT-')`
- Human/mouse GTFs: genes named `MT-ND1`, `MT-CO1` → QC works
- Macaque (Mmul_10) GTF: genes named `ND1`, `COX1` (no `MT-` prefix) → QC fails

CellRanger uses GTF gene_names as-is. If the GTF doesn't have `MT-` prefix,
the output BAM/h5 will also lack it.

**Ribosomal genes:** Standard QC uses `^RPS|^RPL` (cytoplasmic ribosomal).
Macaque GTF has 4090 RPS/RPL genes (correct) plus 2017 MRPS/MRPL genes
(mitochondrial ribosomal, different naming).

**Options:**
1. Pre-process GTF to add `MT-` prefix to mitochondrial genes
2. Use a GTF that follows standard naming conventions
3. In downstream analysis, manually specify mitochondrial gene list
