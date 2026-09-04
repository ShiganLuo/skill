# star_3pass Gene-Specific Alignment

The gene-specific three-pass alignment (`gene_specific_align.py`) must mirror the
canonical `three_pass_align.py` structure -- NOT a simple unmapped-reads chain.

## Correct three-pass structure (per gene)

| Pass | Index | Mode | Input | Output |
|------|-------|------|-------|--------|
| pass1 | per-gene index | EndToEnd | all gene FASTQ | BAM |
| pass2 | per-gene index | EndToEnd + clip5p/clip3p | all gene FASTQ (same as pass1) | mapped BAM + unmapped FASTQ |
| pass3a | per-gene index | Local | pass2 **mapped** reads (re-extracted as FASTQ) | BAM |
| pass3b | per-gene index | Local | pass2 **unmapped** reads | BAM |
| merge | - | - | pass3a + pass3b | gene merged BAM -> Tailer |

### Why this structure

The paper's three-pass is:
1. Whole-genome E2E -> extract small-RNA reads
2. Small-RNA reference E2E + clip -> split mapped/unmapped
3. Genome Local re-alignment of both groups -> merge

In gene-specific mode, the per-gene index replaces both the genome index and the
small-RNA reference (they are the same single-gene sequence). But the three-pass
**structure** is identical: pass1 E2E all reads, pass2 E2E+clip all reads (split),
pass3 Local on both groups, merge.

### Key implementation details

- pass2 MUST have `--outReadsUnmapped Fastx` to produce unmapped FASTQ outputs.
- pass2 mapped reads re-extracted as FASTQ via `samtools sort -n` + `samtools fastq`.
- pass2 unmapped reads (`Unmapped.out.mate1/mate2`) are plain text; gzip before
  feeding to pass3b (STAR expects `.gz` with `--readFilesCommand zcat`).
- Tailer runs on the per-gene merged BAM (pass3a + pass3b), NOT individual pass BAMs.
- `--pass2-clip5p-nbases` and `--pass2-clip3p-nbases` CLI args exist for passing
  STAR clip parameters. Default: "20 0" / "0 20" for PE, "20" / "0" for SE.

## Config (ncRNAseq.json)

```json
"star_3pass_gene": {
    "ambiguous": "exclude",
    "flank": 50,
    "index": {
        "genomeSAindexNbases": 3
    },
    "passes": {
        "pass1": {
            "alignEndsType": "EndToEnd",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 1,
            "outFilterMismatchNoverLmax": 0.2,
            "alignIntronMin": 9999999
        },
        "pass2": {
            "alignEndsType": "EndToEnd",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 0,
            "outFilterMismatchNoverLmax": 0.2,
            "outFilterMismatchNoverReadLmax": 0.05,
            "clip5pNbases": "20 0",
            "clip3pNbases": "0 20",
            "alignIntronMin": 9999999,
            "alignMatesGapMax": 500
        },
        "pass3": {
            "alignEndsType": "Local",
            "outFilterMultimapNmax": 1000,
            "outFilterMultimapScoreRange": 0,
            "outFilterMismatchNoverLmax": 0.025,
            "alignIntronMin": 9999999,
            "alignMatesGapMax": 500
        }
    }
}
```

- pass1/pass2: `EndToEnd`. pass3: `Local`. Non-negotiable.
- `genomeSAindexNbases` lives under `star_3pass_gene.index`, NOT under
  `passes.pass1`. It is a `genomeGenerate` (index-build) parameter, not an
  alignment parameter -- keep index-build params and alignment params
  separated. The .smk reads it via
  `params.get("index", {}).get("genomeSAindexNbases", 3)` and passes
  `--index-genome-sa-index-nbases` to `gene_specific_align.py`.
- pass2 clip params and `outFilterMismatchNoverReadLmax` must be passed from
  .smk config to CLI. The .smk needs explicit `if "clip5pNbases" in p2:` lines.
- `mode` and `batch` config fields removed -- do not re-add.
- `hard_clip_5p` REMOVED -- it was a redundant duplicate of `clip5pNbases`.
  See pitfalls below.

## .smk parameter passing

The .smk must pass pass2 clip/read-mismatch params:

```python
if "outFilterMismatchNoverReadLmax" in p2:
    cmd += ["--pass2-out-filter-mismatch-nover-read-lmax", str(p2["outFilterMismatchNoverReadLmax"])]
if "clip5pNbases" in p2:
    cmd += ["--pass2-clip5p-nbases", str(p2["clip5pNbases"])]
if "clip3pNbases" in p2:
    cmd += ["--pass2-clip3p-nbases", str(p2["clip3pNbases"])]
```

## Pitfalls

- **WRONG: unmapped chain**: If pass2/pass3 take pass1/pass2 unmapped reads as
  input (instead of all reads), pass2/pass3 will always be 0 reads because pass1
  Local mode on a short per-gene reference maps everything. This was the original
  bug. Fix: use the mapped/unmapped split structure above.
- **Missing clip params in .smk**: If the .smk doesn't pass clip5pNbases /
  clip3pNbases, pass2 becomes identical to pass1 and the three-pass is meaningless.
- **STAR Log.out in cwd**: STAR writes Log.out to the current working directory
  when --genomeDir is on a different filesystem. Clean up stray Log.out files.
- **gene_inputs subdirectory**: Per-gene inputs go directly to `outdir/<sample>/`,
  not `outdir/gene_inputs/<sample>/`.
- **Tailer on wrong BAM**: Tailer should run on the per-gene merged BAM
  (pass3a + pass3b), not on individual pass BAMs. The old code walked backwards
  from pass3 to find the last pass with reads -- this is wrong.
- **hard_clip_5p removed (was redundant with clip5pNbases)**: The old
  `hard_clip_5p` config field (under `Params.star_3pass_gene`) was a separate
  integer that `three_pass_align.py` converted to `--clip5pNbases` at runtime,
  overriding the pass2 `clip5pNbases` config value for ALL passes. This was
  redundant -- `clip5pNbases` already controls 5' clipping via the per-pass
  config. The field was removed from: ncRNAseq.json, ncRNAseq.schema.json,
  ncRNAseq.smk (subworkflow config dict), star_3pass.smk (variable + CLI arg),
  three_pass_align.py (argparse param, function param, override logic).
  `clip5pNbases` is now the sole control for 5' clipping. If pass1/pass3 need
  5' clipping, add `clip5pNbases` to those pass configs (currently only pass2
  supports it in the .smk parameter passing).
- **force_end_to_end fully removed**: The `force_end_to_end` parameter
  previously existed in three places: (1) `ncRNAseq.smk` subworkflow config dict
  (`"force_end_to_end": True`), (2) `star_3pass.smk` module (variable definition +
  `--force-end-to-end` CLI arg), (3) `three_pass_align.py` (argparse param,
  `_star_pass_options` function param, override logic that forced `alignEndsType`
  to `EndToEnd` for all passes). It was removed from ALL three locations because
  it defeated the three-pass algorithm design -- pass3 must be `Local` but
  `force_end_to_end=True` overrode it to `EndToEnd`. Each pass now honors its
  configured `alignEndsType` exclusively. Do NOT re-add `force_end_to_end` --
  if a pass needs `EndToEnd`, set `alignEndsType: "EndToEnd"` in its config.
  `_star_pass_options` signature is now `(pass_name, paired, args)` -- 3 params.
- **genomeSAindexNbases moved from passes.pass1 to index**: The
  `genomeSAindexNbases` parameter is a STAR `genomeGenerate` (index-build)
  setting, not an alignment parameter. It was previously nested under
  `star_3pass_gene.passes.pass1`, which was semantically wrong -- the pass1
  alignment step never uses it; only the `genomeGenerate` step does. It now
  lives under `star_3pass_gene.index` as a sibling of `passes`/`ambiguous`/
  `flank`. The CLI arg was renamed from `--pass1-genome-sa-index-nbases` to
  `--index-genome-sa-index-nbases` in both `star_3pass_gene.smk` and
  `gene_specific_align.py`. Do NOT put index-build params inside `passes`.
