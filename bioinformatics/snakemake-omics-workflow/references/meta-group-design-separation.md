# Meta grouping vs comparison design

## Rule
Keep `design` as the comparison role/tag (`ctr_X` / `exp_X`) and add a separate `group` column for biological grouping.

## Recommended semantics
- `group`: sample membership for group-based workflows (e.g. DESeq2, StringTie summaries)
- `design`: pairwise contrast encoding for workflows that need one-to-one comparison

## Parsing pattern
- Prefer `sample_info.group` when building `sample_groups`
- Fall back to the legacy `sample_id` prefix only when `group` is missing
- Preserve `design` unchanged for pair builders

## Why
This avoids overloading a single field for two different concepts and keeps pairwise workflows backward compatible while enabling group-aware workflows.

## Helper-script rule
Scripts executed via `shell()` inside a conda environment should receive explicit CLI args; do not depend on `from snakemake import config` unless the script is actually run by Snakemake as a script/workflow context.
