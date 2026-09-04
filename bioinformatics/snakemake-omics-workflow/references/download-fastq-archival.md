# FASTQ archival utility pattern for `src/download`

Use this pattern when adding a data-ingest / archival helper under `workflow/Omics/src/download/`.

## When this applies
- User wants a standalone archival/indexing script, not a Snakemake rule
- Input files arrive from heterogeneous sources and need a local business ID
- Retrieval must be fast by ID and single-directory fanout must stay bounded

## Conventions
- Keep the script in `src/download/` and add Omics-root import bootstrap:
  - `_SRC_DIR = Path(__file__).resolve().parent.parent.parent`
  - `sys.path.insert(0, str(_SRC_DIR))` if missing
- Import shared helpers via `from src.common.util.X import Y`
- Prefer `typing` names like `Dict`, `List`, `Optional`, `Tuple`
- Expose a direct CLI via `argparse`

## Business ID + storage layout
- Business ID format: fixed 3-letter prefix + 7-digit serial, e.g. `ABC0000001`
- Persist the serial in a counter file so isolated machines can keep their own namespace
- For file placement, hash the business ID and shard by digest prefix:
  - `<archive_root>/<sha256[:2]>/<sha256[2:4]>/<business_id>/...`
- This keeps lookup deterministic and limits single-directory size without needing directory scans

## Metadata registry
- If the user asks for indexed local metadata storage, use SQLite
- Recommended table responsibilities:
  - `business_id`, `prefix`, `serial_number`
  - `source_path`, `archived_path`
  - `sample_name`, `project_id`, `group_key`, `read`
  - `md5`, `size_bytes`, `extra_metadata_json`, `created_at`
- Add at least an index on `business_id`; add group-level indexes only when queried

## Verification pattern when no canonical suite exists
- Add a focused `unittest` module under `workflow/Omics/tests/`
- Also run a temporary `/tmp/hermes-verify-*.py` script that:
  - creates temp FASTQ fixtures
  - archives them into a temp root
  - opens the SQLite registry and asserts the inserted rows
  - checks archived files exist at the computed hash path
- Report this explicitly as ad-hoc verification, not as full suite green
