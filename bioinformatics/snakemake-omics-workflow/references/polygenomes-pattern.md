# Polygenomes sub-module pattern

When a workflow needs multiple genomes (e.g., mouse GRCm39 + human GRCh38 in one DAG), each genome-referencing module needs a `polygenomes/` sub-module. This adds a `{genome}` wildcard to rules so samples route to the correct reference.

## Architecture

```
modules/hisat2/
  hisat2.smk              # single-genome (original)
  polygenomes/
    hisat2.smk            # multi-genome ({genome} wildcard)
    hisat2.json           # nested genome config template
```

The subworkflow references the polygenomes version:
```python
module hisat2_align:
    snakefile: "../modules/hisat2/polygenomes/hisat2.smk"
    config: hisat2_config
```

## Transformation rules (single → polygenomes)

1. **Include path**: add one `../` prefix
   - `"../common/common.smk"` → `"../../common/common.smk"`
   - `"../../common/common.smk"` → `"../../../common/common.smk"`

2. **YAML/container path**: add one `../` prefix
   - `"hisat2.yaml"` → `"../hisat2.yaml"`
   - `"../gatk.yaml"` → `"../../gatk.yaml"`

3. **Genome config access**: lazy lookup via `wildcards.genome`
   - Module-level `fasta = config.get('genome',{}).get('fasta')` → REMOVE (no longer at module level)
   - In rule input/params: `lambda wildcards: config["genome"][wildcards.genome]["fasta"]`
   - In get_index functions: `config.get('genome',{}).get(wildcards.genome,{}).get('index_prefix')`

4. **Output paths**: insert `{genome}` wildcard
   - `outdir + "/{sample_id}/{sample_id}.bam"` → `outdir + "/{genome}/{sample_id}/{sample_id}.bam"`
   - Index: `outdir + "/index/genome.{ext}"` → `outdir + "/index/{genome}/{genome}.{ext}"`

5. **Log paths**: add `{genome}` for disambiguation
   - `logdir + "/{sample_id}/hisat2.log"` → `logdir + "/{genome}/{sample_id}/hisat2.log"`

6. **Params**: index prefix becomes lambda
   - `prefix = outdir + "/index/genome"` → `prefix = lambda wildcards: outdir + f"/index/{wildcards.genome}/{wildcards.genome}"`

7. **Config structure**: flat → nested per genome
   - Original: `{"genome": {"fasta": "...", "gtf": "..."}}`
   - Polygenomes: `{"genome": {"GRCm39": {"fasta": "...", "gtf": "..."}, "GRCh38": {"fasta": "...", "gtf": "..."}}}`

## Pitfalls

- **YAML path must have `../` prefix** in polygenomes/ — the .smk file is one directory deeper. Subagents consistently miss this; always verify.
- **Config key must be `genome` (singular)**, NOT `genomes`. Subagents sometimes typo this.
- **Don't transform module-level variables that aren't genome-related** — only fasta, gtf, fai, index_prefix, and genome-specific annotation files become lazy.
- **`include:` does NOT propagate** into `module` + `use rule` — each polygenomes .smk must independently include common.smk.
- **JSON config templates are mandatory** — each polygenomes/ dir needs a `<mod>.json` with nested genome structure. Batch-generate with a script; don't rely on subagents to remember.
- **Modules with subdirectories** (gatk/gatk_RNAseq, openms/searchengine) need deeper include path adjustment.
- **TEtranscripts already uses lambda wildcards** in the original — the polygenomes version needs to add one more nesting level for genome lookup.
- **Batch generation via subagents**: subagents consistently miss yaml `../` prefix. After subagent batch, always run the yaml path verification (step 2 in checklist) and fix with a script. This is the #1 most common bug.
- **Config dict completeness**: when a subworkflow builds a config dict for `module ... config: ...`, ALL keys the module's `.smk` reads via `config.get()` must be present. Missing keys silently fall back to the module's hardcoded default, producing wrong paths or behavior with no error. Example: `hisat2_config_for_StringTie` omitted `logdir_combine`, so the hisat2 module used its default `"log/combine"` instead of the intended `os.path.join(logdir, "group")`. Verify by comparing the config dict keys against every `config.get()` in the module .smk.
- **Trailing comma creates tuple**: `x = config.get(...).get('gtf'),` (trailing comma) makes `x` a tuple `(value,)`, not a string. `os.path.exists()` then raises `TypeError: path should be string, bytes, os.PathLike or integer, not tuple`. Remove the comma. Check all `config.get(...)` lines in input functions for trailing commas.
- **sample_groups must be filtered by genome**: `sample_groups` in config contains ALL genomes mixed together (e.g., mouse + human samples in one dict). When writing per-genome files (group_tsv, sample lists) inside a polygenomes rule, filter by `genome_samples[wildcards.genome]`, not `sample_groups` directly. Otherwise the downstream tool receives cross-genome samples and fails with `FileNotFoundError` when it looks for files under the wrong genome's directory. Pattern:
  ```python
  # WRONG — writes ALL genomes' samples, each repeated N times (once per group)
  for group, sample_list in sample_groups.items():
      for sample_id in sample_list:
          f.write(f"{sample_id}\t{group}\n")
  # ALSO WRONG — filters by genome but iterates groups, repeating each sample per group
  for group, sample_list in sample_groups.items():
      for sample_id in genome_samples.get(wildcards.genome, []):
          f.write(f"{sample_id}\t{group}\n")
  # CORRECT — only samples that are in current genome AND in current group
  genome_sample_set = set(genome_samples.get(wildcards.genome, []))
  for group, sample_list in sample_groups.items():
      for sample_id in sample_list:
          if sample_id in genome_sample_set:
              f.write(f"{sample_id}\t{group}\n")
  ```
- **Defensive dedup in report modules**: when a report module loads TSV output from a tool that received `sample_groups`-derived input, the TSV may contain duplicate rows (one per group membership). Always `drop_duplicates(subset=["sample"], keep="first")` after loading, before using `set_index("sample")` + `.loc[]`. Otherwise `.loc[sample]` returns a Series instead of a scalar, causing `ValueError: The truth value of a Series is ambiguous` in pandas boolean context.

## Modules with polygenomes support (47 total)

| Category | Modules |
|----------|---------|
| Aligners | hisat2, star (+ star_3pass, star_3pass_gene), bowtie2, bwa-mem2, cellranger, pbmm2 |
| Variant calling | deepvariant, gatk (prepare/germline/somatic/RNAseq/population), manta, hiphase, pbsv, cnvkit, msisensor-pro (tumor-normal/tumor-only), sv, spectrum, trgt |
| Quantification | DESeq2, featureCounts, StringTie, TEtranscripts, RmrRNA, function |
| Peak/CLIP | arriba, bedtools, homer, deeptools_heatmap, PureCLIP, peak_te_overlap, macs3 |
| Reports | RNAseq_report (reuses parent bin/generate_report.py, genome-specific contrasts via input function) |
| Other | openms (decoydatabase/searchengine), tailer, scTE, fibertools, genome, samtools/sort, mimseq (coverage/tRNAtools/deseq) |

### Edge cases
- **msisensor-pro**: uses `config["genome_version"]` + `config["reference"]` instead of standard `config["genome"]` pattern. Polygenomes version only adjusts include paths; does NOT add standard `{genome}` wildcard routing.
- **RNAseq_report**: reuses parent's `bin/generate_report.py` (do NOT copy into polygenomes/bin/ or create polygenomes/bin/). The .smk passes `{outdir}/{genome}` as `--analysis-dir` so the script works without modification. Uses `genome_paired_samples` / `genome_single_samples` dicts (keyed by genome name) instead of flat sample lists — params use `lambda wildcards: genome_paired_samples.get(wildcards.genome, [])` to resolve per-genome. **Contrasts must also be genome-specific** — use input function + `Params.DESeq2.group_pairs[genome]` instead of `expand(..., contrast=contrasts)`. See "Genome-specific contrasts" section above. **Path ordering must match upstream** — see "Output path ordering consistency" section above.
- **bwa-mem2**: has two .smk files — `bwa-mem2/bwa-mem2.smk` (standard) and `bwa-mem2/bwa-mem2/bwa-mem2.smk` (already has `{genome}`). Only the former needs polygenomes.

## Verification checklist after batch generation

```bash
# 1. Check all polygenomes .smk files exist
find modules/ -path "*/polygenomes/*.smk" | wc -l

# 2. Verify yaml paths have ../ prefix (most common bug)
grep -rn '"[a-zA-Z].*\.yaml"' modules/*/polygenomes/*.smk | grep -v '../'

# 3. Verify config key is 'genome' not 'genomes'
grep -rn "config\['genomes'\]" modules/*/polygenomes/*.smk

# 4. Verify all have {genome} wildcard in output
for f in modules/*/polygenomes/*.smk; do
  if ! grep -q '{genome}' "$f"; then echo "MISSING {genome}: $f"; fi
done

# 5. Verify include paths are adjusted
grep -rn 'include:.*common.smk' modules/*/polygenomes/*.smk

# 6. Verify all polygenomes dirs have JSON templates
for smk in $(find modules/ -path "*/polygenomes/*.smk"); do
  json="${smk%.smk}.json"
  [ ! -f "$json" ] && echo "MISSING JSON: $json"
done

# 7. Count total polygenomes files
echo "SMK: $(find modules/ -path '*/polygenomes/*.smk' | wc -l)"
echo "JSON: $(find modules/ -path '*/polygenomes/*.json' | wc -l)"
```

## Batch yaml path fix script

After subagent-generated polygenomes files, batch-fix missing `../` prefixes:

```python
import os, re

fix_files = ["arriba/polygenomes/arriba.smk", "bedtools/polygenomes/bedtools.smk", ...]  # all subagent-generated

for f in fix_files:
    with open(f) as fh:
        content = fh.read()
    mod_name = os.path.basename(f).replace('.smk', '')
    content = content.replace(f'"{mod_name}.yaml"', f'"../{mod_name}.yaml"')
    with open(f, 'w') as fh:
        fh.write(content)
```

## Species alias → genome version mapping

`src/common/util/type.py` defines `SPECIES_TO_GENOME` dict and `resolve_genome()` function
for mapping organism aliases (case-insensitive) to canonical genome version keys used in
`config["genome"]`:

```python
from src.common.util.type import resolve_genome
resolve_genome("mouse")    # → "GRCm39"
resolve_genome("human")    # → "GRCh38"
resolve_genome("rhesus")   # → "Mmul_10"
resolve_genome("GRCh38")   # → "GRCh38" (pass-through)
resolve_genome("zebrafish") # → ValueError
```

Add new species by extending the `SPECIES_TO_GENOME` dict. Each species needs ALL common
aliases (short name, latin name, genome version lowercase, common abbreviations).

## Genome-specific sample lists (report/aggregation modules)

When a module aggregates across samples (e.g. RNAseq_report, DESeq2), `paired_samples` and
`single_samples` must be genome-scoped dicts, not flat lists:

```python
# Config
{
    "genome_paired_samples": {
        "GRCm39": ["ciTotiSC1-1", "mESC1"],
        "GRCh38": ["WIBR3_E8_hESC1", "WIBR3_E8_hTBLC1"]
    },
    "genome_single_samples": {
        "GRCm39": [],
        "GRCh38": []
    }
}
```

```python
# In .smk params
genome_paired_samples = config.get("genome_paired_samples", {})
genome_single_samples = config.get("genome_single_samples", {})

params:
    samples = lambda wildcards: genome_paired_samples.get(wildcards.genome, []) + genome_single_samples.get(wildcards.genome, []),
    paired_samples = lambda wildcards: genome_paired_samples.get(wildcards.genome, []),
    single_samples = lambda wildcards: genome_single_samples.get(wildcards.genome, []),
```

## CRITICAL: Output path ordering consistency

When adding `{genome}` wildcard to a workflow, ALL rules must use the SAME `{genome}`
position in their paths. A mismatch between upstream output paths and downstream
input paths causes `MissingInputException`.

**Upstream rules (node.py injected)**:
```
outdir/diff_expression/{genome}/{contrast}/DESeq2.done
outdir/transcripts/{genome}/raw/{sample_id}/...
outdir/fusion/{genome}/{sample_id}/...
```

**Report module expects** (WRONG if mismatched):
```
{indir}/{genome}/diff_expression/{contrast}/...   ← WRONG if upstream uses diff_expression/{genome}/
```

**Root cause**: node.py builds outfiles with `{subdir}/{genome}/...` ordering, but the
polygenomes report .smk was written with `{genome}/{subdir}/...` ordering. The two must match.

**Fix**: The report module's input paths MUST mirror the upstream rules' output path structure.
Read node.py's `outfiles` construction to determine the correct ordering before writing
the report .smk. If upstream uses `outdir/diff_expression/{genome}/{contrast}/`, the report
must use `indir + "/diff_expression/{genome}/{contrast}/..."` — NOT `indir + "/{genome}/diff_expression/{contrast}/..."`.

**Verification**: After writing the polygenomes report .smk, compare its input paths against
node.py's outfiles:
```bash
# Extract path patterns from node.py outfiles
grep "outfiles.append" node.py | head -20
# Compare against report .smk input patterns
grep "indir.*genome" modules/RNAseq_report/polygenomes/RNAseq_report.smk
```

## Genome-specific contrasts (expand vs input function)

When contrasts differ per genome (e.g., mouse has `mESC_vs_ciTotiSC`, human has `hESC_vs_hTBLC`),
the report module CANNOT use `expand(..., contrast=contrasts)` with a flat contrast list.
It must use an **input function** that resolves contrasts per `wildcards.genome`.

**Config structure** (from node.py via `Params.DESeq2.group_pairs`):
```json
{
    "Params": {
        "DESeq2": {
            "group_pairs": {
                "GRCm39": {
                    "mESC_vs_ciTotiSC": {...},
                    "mESC_vs_TLSC": {...}
                },
                "GRCh38": {
                    "hESC_vs_hTBLC": {...},
                    "prEpiSC_vs_ci8CLC": {...}
                }
            }
        }
    }
}
```

**Pattern**: Replace `expand()` with input function:
```python
def get_report_inputs(wildcards):
    genome = wildcards.genome
    contrasts = list(config.get("Params", {}).get("DESeq2", {}).get("group_pairs", {}).get(genome, {}).keys())
    inputs = {
        "te_sample_summary": indir + f"/transcripts/{genome}/TE_chimeric/TE_chimeric_sample_summary.tsv",
        # ... non-contrast inputs ...
    }
    # Add contrast-specific inputs
    for contrast in contrasts:
        inputs[f"group_{contrast}"] = indir + f"/diff_expression/{genome}/{contrast}/group.tsv"
        inputs[f"pca_{contrast}"] = indir + f"/diff_expression/{genome}/{contrast}/PCA/{contrast}.cpmPCA.png"
        # ... more contrast files ...
    return inputs

rule generate_report:
    input:
        unpack(get_report_inputs),
    output:
        report = outdir + "/{genome}/RNAseq_report.pptx",
    params:
        contrasts = lambda wildcards: list(config.get("Params", {}).get("DESeq2", {}).get("group_pairs", {}).get(wildcards.genome, {}).keys()),
        # ... other params ...
```

**Pitfall**: If `control_group_name_vs_experimental_group_name` appears as a contrast name,
it means node.py's `group_pairs` key was built from uninitialized template values. Check
`MetaUtil.build_design_pairs` for proper group name resolution.

## Legacy pattern (iterate genomes in subworkflow)

The old approach iterated genomes in the subworkflow itself. This works but creates N module instances per genome and doesn't scale:
```python
genomes = config.get("genomes", ["mm"])
for genome in genomes:
    bowtie2_config = {...}
    module bowtie2_align:
        snakefile: "../modules/bowtie2/bowtie2.smk"
        config: bowtie2_config
    use rule bowtie2_align_paired from bowtie2_align as DIPseq_bowtie2_align_paired
```

The polygenomes pattern is preferred: one module instance, `{genome}` wildcard handles routing.
