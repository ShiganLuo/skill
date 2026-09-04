# Heterogeneous metadata registry pattern

Use this when data files are scattered across multiple directories and each metadata source uses different column names.

## Goal

Normalize many metadata tables plus a file scan into a small set of machine-readable outputs:
- `sample_registry.tsv`: one row per logical sample
- `file_registry.tsv`: one row per physical file
- `conflicts.tsv`: same `sample_id` but contradictory metadata values
- `issues.tsv`: metadata rows that could not be matched to files
- `unmatched_files.tsv`: scanned files with no metadata mapping

## Minimal standard sample fields

- `sample_id`
- `data_id`
- `project_id`
- `assay_type`
- `organism`
- `condition`
- `group`
- `replicate`
- `source_name`
- `match_key`

## Minimal standard file fields

- `file_id`
- `sample_id`
- `data_id`
- `project_id`
- `source_name`
- `match_key`
- `file_type`
- `layout`
- `mate`
- `file_path`

## Per-source mapping pattern

For each metadata table, define:
- `source_name`: human-readable source label
- `match_key_field`: source column used to join to scanned files
- `field_map`: source-column -> standard-field mapping
- `constants`: fixed values to stamp onto every row from that source

Example:

```json
{
  "source_name": "lab_a",
  "match_key_field": "Run",
  "field_map": {
    "sample_id": "SampleName",
    "data_id": "Run",
    "condition": "Treatment",
    "replicate": "Replicate"
  },
  "constants": {
    "project_id": "PRJ001",
    "assay_type": "RNAseq",
    "organism": "human"
  }
}
```

## Matching strategy

Preferred join key order:
1. explicit stable run/accession key from metadata (`SRR`, `Run`, lane id, etc.)
2. `data_id`
3. `sample_id` only if filenames truly use sample_id stably

Avoid manual filename-to-sample notes when the relationship can be encoded once in a mapping file.

## Operational pattern

1. Scan all data roots for FASTQ/BAM/CRAM.
2. Parse filename structure into `match_key`, `layout`, `mate`, `file_type`.
3. Load each metadata table.
4. Normalize source columns into standard fields.
5. Join metadata rows to scanned files by `match_key`.
6. Write registries and QA reports.
7. Optionally build a symlink tree for downstream workflows.

## Practical output for pipelines

If downstream tools expect a centralized input tree, build symlinks from `file_registry.tsv` rather than copying raw files. This keeps raw data in place while presenting a clean, workflow-friendly layout.

## User-style lesson

When a user asks how to centrally manage scattered data and inconsistent metadata, they may be asking for a working ingestion path, not a design lecture. Start from concrete tables, a mapping file, and a runnable builder script.