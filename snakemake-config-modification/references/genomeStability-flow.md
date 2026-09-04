# genomeStability Pipeline Config Flow

Project root: `/home/luosg/Data/genomeStability`

## Architecture

```
config/<workflow>.json          # Source of truth - user edits this
    ↓
workflow/Omics/run.py           # Loads JSON, sets defaults (ROOT_DIR, data_dir, etc.), writes raw.json
    ↓
workflow/Omics/subworkflow/<wf>.smk   # Reads config, constructs module-specific config dicts
    ↓
workflow/Omics/modules/<mod>/<mod>.smk  # Reads from module config dict, passes to scripts
    ↓
workflow/Omics/modules/<mod>/bin/<sub>/run.py  # Final consumer
```

## Key Paths

- Config JSONs: `workflow/Omics/config/{CoCulture,MERIP,RNAseq,CLIP,Mutation,PacVar,KARRseq,PeakCalling,QuantMS,tRNAseq,ncRNAseq}.json`
- Schema JSONs: `workflow/Omics/config/<workflow>.schema.json` (JSON schema for validation)
- Module templates: `workflow/Omics/modules/<name>/<name>.json` (schema only, NOT runtime config)
- Entry point: `workflow/Omics/run.py` with `WORKFLOW_DISPATCH` dict mapping workflow names to runner functions
- Subworkflows: `workflow/Omics/subworkflow/<name>.smk`

## Conventions

- Module config values go under `Params.<module_name>` namespace (e.g., `Params.mimseq.species`)
- `ROOT_DIR` is set by `run.py` to `os.path.dirname(__file__)` (= `workflow/Omics/`)
- When adding a new config field: update source JSON, schema JSON, run.py default setter, subworkflow passthrough, module smk reader
- When removing a config field: clean the FULL chain -- source JSON, schema JSON, subworkflow passthrough, module smk variable+CLI arg, Python argparse def, function signature, all call sites
- Index-building params go under `Params.<module>.index` sub-key, not mixed with alignment params

## ncRNAseq STAR Module Config Structure

The ncRNAseq workflow supports 4 aligner routes. Their config flows:

### star route
- Index: built via `modules/star/star.smk:star_index`, reads `Params.STAR.index.sjdbOverhang`
- Align: `modules/star/star.smk:star_align`, reads `Params.STAR.*` (flat alignment params)

### star_3pass route
- Index: same `star.smk:star_index` (genome + smallRNA indexes)
- Align: `modules/star/star_3pass/star_3pass.smk` -> `bin/three_pass_align.py`
  - `_star_pass_options(pass_name, paired, args)` -- 3 args, assembles STAR flags per pass
  - pass2 clip5p/clip3p defaults: PE="20 0"/"0 20", SE="20"/"0"
  - alignEndsType fully controlled by per-pass config (no force_end_to_end override)

### star_3pass_gene route
- Index: genome/smallRNA via `star.smk:star_index`; per-gene via `gene_specific_align.py` genomeGenerate
  - `Params.star_3pass_gene.index.genomeSAindexNbases` (per-gene index, CLI: `--index-genome-sa-index-nbases`)
- Align upstream: reuses `star_3pass.smk` (same as star_3pass route)
- Align gene-specific: `star_3pass_gene.smk` -> `bin/gene_specific_align.py`
  - Per-gene: build index, pass1 E2E, pass2 E2E+clip, pass3a/3b Local, merge, Tailer

### Removed fields (do NOT re-add)
- `hard_clip_5p` -- was redundant with `clip5pNbases`, overridden in three_pass_align.py
- `force_end_to_end` -- was overriding pass3 alignEndsType to EndToEnd; now config controls directly
