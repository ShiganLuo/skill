# QuantMS DAG path-contract debugging

Use this when `subworkflow/QuantMS.smk` fails with `MissingInputException` at `rule all` even though the filenames "look right".

## Core rule

Do not debug only from the final missing targets. Trace the producer/consumer contract across three layers:

1. `node.py` / generated `raw.json` `outfiles`
2. subworkflow `*_config` wiring (`indir`, `outdir`, explicit upstream file paths)
3. module `input` / `output` filename patterns

A mismatch at any layer will surface as `rule all` missing files.

## Common QuantMS failure patterns

### 1) `outfiles` target name does not equal module output name

Bad pattern:
- `outfiles`: `search_engine/{sample}/{sample}.idXML`

Actual module outputs:
- comet: `search_engine/{sample}/{sample}_comet.idXML`
- msgf: `search_engine/{sample}/{sample}_msgf.idXML`
- sage: `search_engine/{sample}/{sample}_sage.idXML`

Lesson: `rule all` targets must exactly match the selected module output.

### 2) Downstream module reads predecessor from `outdir` instead of `indir`

Example seen in `psmrescoring.smk`:
- wrong: read `{sample}_comet.idXML` from the rescoring module `outdir`
- right: read it from the configured upstream `indir`

Lesson: in Omics subworkflow wiring, `indir` is the upstream handoff path; `outdir` is the current module's outputs.

### 3) `search_engine_config['indir']` points to the wrong upstream directory

`searchengine.smk` expects:
- `{indir}/{sample}/{sample}.mzML`

Therefore `search_engine_config['indir']` must point to the `raw2mzml` output directory, not the `decoy_database` output directory.

Lesson: decoy FASTA and mzML come from different upstream producers; do not collapse them into one directory variable.

### 4) `decoy_fasta` is hand-built instead of using the real upstream output path

If `decoydatabase.smk` emits:
- `decoy_database/genome_decoy.fasta`

then `search_engine_config['genome']['decoy_fasta']` should point to that exact file, not to a basename-derived path such as `{basename(fasta)}_decoy.fasta` unless the module really emits that name.

Lesson: prefer explicit upstream output paths over re-derived filenames.

## Practical debugging order

1. Read `raw.json` and inspect `outfiles`.
2. Check the selected search engine (`Params.search_engine.engine`) and verify the target suffix matches it.
3. In the subworkflow, verify each module `indir` points at the previous module's `outdir`.
4. For non-sample shared artifacts like decoy FASTA, verify the exact filename emitted by the upstream module.
5. Only after the path contracts are correct, look for missing source data or tool/runtime errors.

## Interpretation rule

If Snakemake reports many downstream affected files (`search_engine`, `psm_rescoring`, `psm_fdr`, `protein_inference`, `quantification`, `msstats`), first suspect the earliest upstream contract break, not six independent missing files.
