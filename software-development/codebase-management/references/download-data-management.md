# Download Data Management Notes

## Review outcomes

- The user explicitly wants one-to-many sample/file modeling.
- A file must belong to exactly one sample.
- Avoid introducing many-to-many sample/file exceptions.
- The user asked for file-name IDs, not object-model IDs, when discussing prefix choice.
- The user rejected opaque hash-style IDs for this workflow; use human-auditable sequential IDs.

## DFQ naming/layout specification

- File prefix: `DFQ`
- ID format: `DFQ` + 7 digits
- Example: `DFQ0000001`
- Sharded storage path:
  - `{output_root}/fastq/{x7}/{x3}/...`
  - `x7` = first 7 characters of the ID
  - `x3` = last 6 digits of the ID
- Example target path:
  - `{output_root}/fastq/DFQ0000/000001/DFQ0000001.fastq.gz`

## Allocation notes

- Persist the last assigned numeric ID in SQLite to avoid reuse.
- On startup, continue from `max(existing_numeric_id) + 1` unless an explicit `--start-index` is larger.
- Record the original filename as `origin_id` in the registry.
- Keep source files immutable; only write into the managed output tree.
- Use `copy` as the safest default mode; `move` should be explicit.

## Operational cautions

- Do not test mutating file workflows on the source directory.
- If the user asks for a rerun, create a fresh temporary output directory rather than deleting prior artifacts.
- If grouping logic is ambiguous, fail fast and ask for a naming rule rather than guessing pairing semantics.
