# STAR Alignment Pitfalls (scRNAseq / scTE)

## limitSjdbInsertNsj (junction insertion limit)

STAR's `--limitSjdbInsertNsj` defaults to 1,000,000. For large genomes with many
novel junctions (e.g., macaque, human), twopassMode Basic can discover 2M+ junctions
in pass 1, causing:

```
Fatal LIMIT error: the number of junctions to be inserted on the fly =2115807 is larger than the limitSjdbInsertNsj=1000000
SOLUTION: re-run with at least --limitSjdbInsertNsj 2115807
```

**Fix**: Set `"limitSjdbInsertNsj": 3000000` in config. Must be added to:
1. `config/scRNAseq.json` under `Params.star`
2. `subworkflow/scRNAseq.smk` in the `star_config` explicit dict
3. `modules/star/star.smk` — param read + cmd construction

## soloBarcodeReadLength (barcode length mismatch)

10X Chromium data varies by chemistry version. If STAR reports:
```
FATAL ERROR: the total length of barcode sequence is 150 not equal to expected 98
SOLUTION: specify --soloBarcodeReadLength 0
```

**Fix**: Set `"soloBarcodeReadLength": 0` to skip the check entirely.
The value `98` only works for certain 10X v2 datasets.

## Debugging STAR failures

STAR errors appear in per-sample logs, NOT in the Snakemake main log.
The main log only shows `CalledProcessError` / `SpawnedJobError`.

**Debug path**:
1. Read Snakemake main log → find failed sample ID and log path
2. Read `log/sample/<sample_id>/star_align.log` → STAR's actual error
3. If param seems correct in JSON but STAR shows wrong value:
   Check `.snakemake/metadata/` for serialized params to verify propagation

## scRNAseq.smk Config Flow (explicit manual mapping)

The scRNAseq subworkflow constructs star_config with explicit per-field calls.
As of 2026-08-24, the star_config includes:
- outSAMattributes, outFilterMultimapNmax, winAnchorMultimapNmax
- outMultimapperOrder, runRNGseed, outSAMmultNmax
- soloType, soloCBwhitelist, soloBarcodeReadLength
- limitSjdbInsertNsj

When adding a new STAR param, add it to BOTH:
1. `config/scRNAseq.json` → `Params.star.<new_param>`
2. `subworkflow/scRNAseq.smk` → `star_config["Params"]["star"]` dict
